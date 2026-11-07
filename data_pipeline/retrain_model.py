"""
Reentrenamiento y calibración periódica del clasificador de ausentismo (Gradient Boosting).

Por defecto, este script no reemplaza el modelo productivo ni modifica los reportes
académicos documentados en data/processed/ml_metrics_summary.json.

Uso:
    docker compose run --rm tools python data_pipeline/retrain_model.py [--source csv] [--promote]
"""

import argparse
from datetime import datetime
import json
import os
import shutil
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from init_db import get_db_connection
from train_models import (
    BASE_DIR,
    DATA_PATH,
    GB_PARAMS,
    MODELS_DIR,
    build_final_pipeline,
    prepare_features,
)

PRODUCTION_MODEL_NAME = 'gradient_boosting_model.joblib'
RISK_BANDS = [('BAJO', 0.0, 0.20), ('MEDIO', 0.20, 0.50), ('ALTO', 0.50, 1.0000001)]  # [lo, hi)
MIN_ROWS = 50
MIN_PER_CLASS = 5

TRAINING_QUERY = """
    SELECT a.id, a.shop_id, a.barber_id, a.client_hashed, a.is_self_booked,
           a.day_of_week, a.hour_of_day, a.month,
           a.lead_time_hours::float AS lead_time_hours, a.target,
           a.price::float AS price, s.price::float AS service_price, s.duration,
           TO_CHAR(a.start_time, 'YYYY-MM-DD HH24:MI:SS') AS appointment_start
    FROM appointments a
    LEFT JOIN services s ON a.shop_id = s.shop_id AND a.service_id = s.id
    WHERE a.target IS NOT NULL
    ORDER BY a.id;
"""

ERASED_QUERY = "SELECT DISTINCT shop_id, client_hashed FROM client_privacy_requests WHERE request_type = 'erasure';"


def _to_rel_path(path: str | None) -> str | None:
    """Convierte una ruta a relativa de BASE_DIR si se encuentra dentro del repositorio."""
    if not path:
        return path
    abs_path = os.path.abspath(path)
    abs_base = os.path.abspath(BASE_DIR)
    if abs_path.startswith(abs_base):
        return os.path.relpath(abs_path, abs_base)
    return path


def fetch_training_frame_from_db(conn) -> pd.DataFrame:
    """Obtiene los turnos con target no nulo desde la base de datos PostgreSQL."""
    cur = conn.cursor()
    try:
        cur.execute(TRAINING_QUERY)
        rows = cur.fetchall() or []
        col_names = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=col_names)
    finally:
        cur.close()


def fetch_erased_clients(conn) -> set[tuple[str, str]]:
    """Obtiene el conjunto de clientes con solicitud de supresión de datos registrada."""
    cur = conn.cursor()
    try:
        cur.execute(ERASED_QUERY)
        rows = cur.fetchall() or []
        return {(str(r[0]).lower(), str(r[1])) for r in rows}
    finally:
        cur.close()


def exclude_erased(df: pd.DataFrame, erased: set[tuple[str, str]]) -> tuple[pd.DataFrame, int]:
    """Excluye del conjunto los turnos de clientes que hayan solicitado supresión de datos."""
    if not erased or df.empty:
        return df.copy().reset_index(drop=True), 0
    mask = df.apply(
        lambda r: False if pd.isna(r['client_hashed']) else (str(r['shop_id']).lower(), str(r['client_hashed'])) in erased,
        axis=1,
    )
    excluded_count = int(mask.sum())
    filtered_df = df[~mask].copy().reset_index(drop=True)
    return filtered_df, excluded_count


def load_training_frame(source: str, csv_path: str = DATA_PATH) -> tuple[pd.DataFrame, dict]:
    """Carga los datos de entrenamiento desde PostgreSQL o archivo CSV según la fuente."""
    src = source.lower()
    if src == 'postgres':
        conn = get_db_connection()
        try:
            raw_df = fetch_training_frame_from_db(conn)
            raw_df['client_hashed'] = raw_df['client_hashed'].replace(
                {'nan': np.nan, 'None': np.nan, '': np.nan, None: np.nan}
            )
            erased = fetch_erased_clients(conn)
            filtered_df, excluded = exclude_erased(raw_df, erased)
            privacy = {
                'filter': 'applied',
                'erased_clients': len(erased),
                'excluded_appointments': excluded,
            }
            return filtered_df, privacy
        finally:
            conn.close()
    elif src == 'csv':
        df = pd.read_csv(csv_path)
        privacy = {
            'filter': 'not_applied_csv_source',
            'erased_clients': None,
            'excluded_appointments': 0,
        }
        return df, privacy
    else:
        raise ValueError(f"Fuente no soportada: '{source}'. Usar 'postgres' o 'csv'.")


def validate_dataset(y: np.ndarray) -> None:
    """Valida que el dataset tenga un tamaño y balance de clases mínimo para reentrenar."""
    if len(y) < MIN_ROWS:
        raise ValueError(
            f"Dataset insuficiente: se requieren al menos {MIN_ROWS} filas, pero se recibieron {len(y)}."
        )
    unique, counts = np.unique(y, return_counts=True)
    counts_by_class = dict(zip(unique, counts))
    for cls in (0, 1):
        c = counts_by_class.get(cls, 0)
        if c < MIN_PER_CLASS:
            raise ValueError(
                f"Clase {cls} insuficiente: se requieren al menos {MIN_PER_CLASS} casos, pero se encontraron {c}."
            )


def cross_validate_candidate(
    X: pd.DataFrame, y: np.ndarray, features_num: list, features_cat: list
) -> tuple[dict, np.ndarray]:
    """Evalúa el clasificador candidato mediante validación cruzada estratificada de 5 pliegues."""
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    f1_scores = []
    recall_scores = []
    precision_scores = []
    roc_auc_scores = []
    accuracy_scores = []
    oof_proba = np.zeros(len(y), dtype=float)

    for train_idx, test_idx in skf.split(X, y):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        pipe = build_final_pipeline(features_num, features_cat)
        pipe.fit(X_train, y_train)

        y_pred = pipe.predict(X_test)
        y_proba = pipe.predict_proba(X_test)[:, 1]
        oof_proba[test_idx] = y_proba

        f1_scores.append(f1_score(y_test, y_pred))
        recall_scores.append(recall_score(y_test, y_pred))
        precision_scores.append(precision_score(y_test, y_pred, zero_division=0))
        roc_auc_scores.append(roc_auc_score(y_test, y_proba))
        accuracy_scores.append(accuracy_score(y_test, y_pred))

    brier_oof = float(np.mean((oof_proba - y) ** 2))
    metrics = {
        'f1_mean': float(np.mean(f1_scores)),
        'f1_std': float(np.std(f1_scores)),
        'recall_mean': float(np.mean(recall_scores)),
        'recall_std': float(np.std(recall_scores)),
        'precision_mean': float(np.mean(precision_scores)),
        'precision_std': float(np.std(precision_scores)),
        'roc_auc_mean': float(np.mean(roc_auc_scores)),
        'roc_auc_std': float(np.std(roc_auc_scores)),
        'accuracy_mean': float(np.mean(accuracy_scores)),
        'accuracy_std': float(np.std(accuracy_scores)),
        'brier_oof': brier_oof,
    }
    return metrics, oof_proba


def calibration_summary(y, proba) -> dict:
    """Calcula las métricas de calibración y distribución por bandas de riesgo."""
    y_arr = np.asarray(y, dtype=float)
    p_arr = np.asarray(proba, dtype=float)
    n = int(len(y_arr))
    if n == 0:
        return {
            'n': 0,
            'observed_rate': None,
            'predicted_rate': None,
            'calibration_gap': None,
            'brier': None,
            'bands': [
                {
                    'band': band_name,
                    'n': 0,
                    'predicted_rate': None,
                    'observed_rate': None,
                }
                for band_name, lo, hi in RISK_BANDS
            ],
        }

    observed_rate = float(np.mean(y_arr))
    predicted_rate = float(np.mean(p_arr))
    calibration_gap = float(predicted_rate - observed_rate)
    brier = float(np.mean((p_arr - y_arr) ** 2))

    bands = []
    for band_name, lo, hi in RISK_BANDS:
        mask = (p_arr >= lo) & (p_arr < hi)
        band_n = int(np.sum(mask))
        if band_n == 0:
            bands.append({
                'band': band_name,
                'n': 0,
                'predicted_rate': None,
                'observed_rate': None,
            })
        else:
            bands.append({
                'band': band_name,
                'n': band_n,
                'predicted_rate': float(np.mean(p_arr[mask])),
                'observed_rate': float(np.mean(y_arr[mask])),
            })

    return {
        'n': n,
        'observed_rate': observed_rate,
        'predicted_rate': predicted_rate,
        'calibration_gap': calibration_gap,
        'brier': brier,
        'bands': bands,
    }


def calibration_report(shop_ids, y, proba) -> dict:
    """Genera el reporte de calibración global y por cada comercio."""
    y_arr = np.asarray(y, dtype=float)
    p_arr = np.asarray(proba, dtype=float)
    shops = list(shop_ids)

    by_shop = {}
    for shop in sorted(set(shops)):
        mask = [s == shop for s in shops]
        sub_y = y_arr[mask]
        sub_p = p_arr[mask]
        by_shop[shop] = calibration_summary(sub_y, sub_p)

    return {
        'global': calibration_summary(y_arr, p_arr),
        'by_shop': by_shop,
    }


def risk_band(p: float) -> str:
    """Devuelve el nombre de la banda de riesgo según el valor de probabilidad."""
    for name, lo, hi in RISK_BANDS:
        if lo <= p < hi:
            return name
    return 'ALTO'


def compare_with_production(candidate, X: pd.DataFrame, production_path: str) -> dict | None:
    """Compara las probabilidades y clasificaciones del candidato con el modelo productivo."""
    if not os.path.exists(production_path):
        return None
    prod_model = joblib.load(production_path)
    cand_proba = candidate.predict_proba(X)[:, 1]
    prod_proba = prod_model.predict_proba(X)[:, 1]

    diff = np.abs(cand_proba - prod_proba)
    max_abs_proba_diff = float(np.max(diff))

    cand_bands = [risk_band(p) for p in cand_proba]
    prod_bands = [risk_band(p) for p in prod_proba]
    risk_level_changes = int(sum(c != p for c, p in zip(cand_bands, prod_bands)))

    cand_high = cand_proba >= 0.5
    prod_high = prod_proba >= 0.5
    threshold_crossings = int(np.sum(cand_high != prod_high))

    return {
        'max_abs_proba_diff': max_abs_proba_diff,
        'risk_level_changes': risk_level_changes,
        'threshold_crossings': threshold_crossings,
    }


def promote_candidate(candidate_path: str, models_dir: str, timestamp: str) -> str:
    """Promueve el candidato a productivo resguardando una copia de backup del anterior."""
    backups_dir = os.path.join(models_dir, 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    prod_path = os.path.join(models_dir, PRODUCTION_MODEL_NAME)
    backup_path = ''
    if os.path.exists(prod_path):
        backup_path = os.path.join(backups_dir, f'gradient_boosting_model_{timestamp}.joblib')
        shutil.copy2(prod_path, backup_path)

    tmp_path = os.path.join(models_dir, '.gradient_boosting_model.tmp')
    shutil.copy2(candidate_path, tmp_path)
    os.replace(tmp_path, prod_path)
    return backup_path


def run_retraining(
    source='postgres',
    promote=False,
    models_dir=MODELS_DIR,
    report_dir=None,
    csv_path=DATA_PATH,
    now=None,
) -> dict:
    """Ejecuta el ciclo de reentrenamiento, validación, calibración y reporte."""
    if report_dir is None:
        report_dir = os.path.join(BASE_DIR, 'data', 'processed', 'retraining')

    timestamp = (now or datetime.now()).strftime('%Y%m%d-%H%M%S')

    raw_df, privacy = load_training_frame(source=source, csv_path=csv_path)
    X, y, features_num, features_cat = prepare_features(raw_df)
    validate_dataset(y)

    cv_metrics, oof_proba = cross_validate_candidate(X, y, features_num, features_cat)
    cal_report = calibration_report(X['shop_id'].tolist(), y, oof_proba)

    # Entrenar candidato final
    candidate = build_final_pipeline(features_num, features_cat)
    candidate.fit(X, y)

    candidates_dir = os.path.join(models_dir, 'candidates')
    os.makedirs(candidates_dir, exist_ok=True)
    candidate_filename = f'gradient_boosting_candidate_{timestamp}.joblib'
    candidate_path = os.path.join(candidates_dir, candidate_filename)
    joblib.dump(candidate, candidate_path)

    prod_path = os.path.join(models_dir, PRODUCTION_MODEL_NAME)
    comparison = compare_with_production(candidate, X, prod_path)

    backup_path = None
    if promote:
        promoted_backup = promote_candidate(candidate_path, models_dir, timestamp)
        backup_path = _to_rel_path(promoted_backup) if promoted_backup else promoted_backup

    os.makedirs(report_dir, exist_ok=True)
    report_filename = f'retrain_report_{timestamp}.json'
    report_path = os.path.join(report_dir, report_filename)

    report_dict = {
        'timestamp': timestamp,
        'source': source,
        'n_appointments': int(len(y)),
        'class_counts': {'0': int(np.sum(y == 0)), '1': int(np.sum(y == 1))},
        'privacy': privacy,
        'hyperparameters': GB_PARAMS,
        'cv_metrics': cv_metrics,
        'calibration': cal_report,
        'comparison_with_production': comparison,
        'candidate_path': _to_rel_path(candidate_path),
        'promoted': bool(promote),
        'backup_path': backup_path,
        'note': (
            'Reporte de reentrenamiento. No reemplaza las métricas documentadas en '
            'data/processed/ml_metrics_summary.json.'
        ),
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    result = dict(report_dict)
    result['report_path'] = _to_rel_path(report_path)
    return result


def main(argv=None) -> int:
    """Punto de entrada de línea de comandos para el reentrenamiento."""
    parser = argparse.ArgumentParser(
        description="Reentrenamiento y calibración periódica del modelo predictivo."
    )
    parser.add_argument(
        '--source',
        choices=['postgres', 'csv'],
        default='postgres',
        help="Fuente de datos de entrenamiento (default: postgres)",
    )
    parser.add_argument(
        '--promote',
        action='store_true',
        help="Promueve el modelo entrenado a productivo (reemplaza gradient_boosting_model.joblib con backup previo)",
    )
    parser.add_argument(
        '--models-dir',
        default=MODELS_DIR,
        help="Directorio de modelos (default: backend/app/models)",
    )
    parser.add_argument(
        '--report-dir',
        default=os.path.join(BASE_DIR, 'data', 'processed', 'retraining'),
        help="Directorio de reportes (default: data/processed/retraining)",
    )

    args = parser.parse_args(argv)

    try:
        res = run_retraining(
            source=args.source,
            promote=args.promote,
            models_dir=args.models_dir,
            report_dir=args.report_dir,
        )
    except Exception as exc:
        print(f"[!] Error durante el reentrenamiento: {exc}", file=sys.stderr)
        return 1

    print("\n========================================================================================")
    print("                      REPORTE DE REENTRENAMIENTO Y CALIBRACIÓN                         ")
    print("========================================================================================")
    print(f"Fuente de datos: {res['source']}")
    print(f"Turnos utilizados: {res['n_appointments']} (Clase 0: {res['class_counts']['0']}, Clase 1: {res['class_counts']['1']})")
    print(f"Filtro de privacidad: {res['privacy']['filter']} (Excluidos: {res['privacy']['excluded_appointments']})")
    print("----------------------------------------------------------------------------------------")
    cv = res['cv_metrics']
    print(f"CV 5-Fold: F1={cv['f1_mean']:.4f}±{cv['f1_std']:.2f} | Recall={cv['recall_mean']:.4f} | Precisión={cv['precision_mean']:.4f} | ROC-AUC={cv['roc_auc_mean']:.4f} | Brier={cv['brier_oof']:.4f}")
    print("----------------------------------------------------------------------------------------")
    print("Calibración por comercio:")
    for shop, cal in res['calibration']['by_shop'].items():
        obs = f"{cal['observed_rate']:.4f}" if cal['observed_rate'] is not None else "N/A"
        pred = f"{cal['predicted_rate']:.4f}" if cal['predicted_rate'] is not None else "N/A"
        br = f"{cal['brier']:.4f}" if cal['brier'] is not None else "N/A"
        print(f"   - {shop:12s}: N={cal['n']:5d} | Tasa observada={obs} | Tasa predicha={pred} | Brier={br}")
    print("----------------------------------------------------------------------------------------")
    comp = res['comparison_with_production']
    if comp:
        print(f"Comparación con productivo actual:")
        print(f"   - Máxima diferencia absoluta de probabilidad: {comp['max_abs_proba_diff']:.4f}")
        print(f"   - Cambios de nivel de riesgo (banda): {comp['risk_level_changes']}")
        print(f"   - Cruces del umbral de decisión (0.50): {comp['threshold_crossings']}")
    else:
        print("No se encontró modelo productivo previo para comparar.")
    print("----------------------------------------------------------------------------------------")
    print(f"Candidato guardado en: {res['candidate_path']}")
    print(f"Reporte JSON guardado en: {res['report_path']}")

    if res['promoted']:
        print(f"[✔] El modelo candidato fue promovido a productivo.")
        if res['backup_path']:
            print(f"    Backup resguardado en: {res['backup_path']}")
        print("    Reiniciá el backend para usar el modelo nuevo: docker compose restart backend")
    else:
        print("El modelo productivo no se modificó. Para promover el candidato: agregá la opción --promote")

    return 0


if __name__ == '__main__':
    sys.exit(main())
