"""
Búsqueda en grilla de hiperparámetros (GridSearchCV) para los 4 clasificadores supervisados.
Usa la misma validación cruzada estratificada que train_models.py (StratifiedKFold, k=5,
random_state=42) con F1 como métrica, compara la configuración en uso de cada modelo con
la mejor de su grilla y exporta los resultados a data/processed/hyperparam_search_results.json.
"""

import os, json, time
import numpy as np
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import xgboost as xgb
from train_models import load_and_preprocess_data, build_preprocessor, DATA_PATH, BASE_DIR

OUTPUT_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'hyperparam_search_results.json')


def _clean_param_value(val):
    """Convierte tipos de NumPy a tipos nativos de Python para serialización JSON."""
    if val is None:
        return None
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return float(val)
    return val


def _clean_params(params_dict):
    """Elimina el prefijo clf__ de los parámetros y normaliza sus valores."""
    cleaned = {}
    for k, v in params_dict.items():
        key = k[len('clf__'):] if k.startswith('clf__') else k
        cleaned[key] = _clean_param_value(v)
    return cleaned


def _clean_grid(grid_dict):
    """Elimina el prefijo clf__ de las listas de grilla y normaliza sus valores."""
    cleaned = {}
    for k, v_list in grid_dict.items():
        key = k[len('clf__'):] if k.startswith('clf__') else k
        cleaned[key] = [_clean_param_value(x) for x in v_list]
    return cleaned


def get_search_spaces(ratio):
    """
    Retorna un diccionario con estimador, grilla de hiperparámetros y configuración actual
    para cada modelo evaluado.
    """
    return {
        'Regresión Logística': (
            LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42),
            {'C': [0.001, 0.01, 0.1, 1.0, 10.0]},
            {'C': 1.0}
        ),
        'Gradient Boosting': (
            GradientBoostingClassifier(random_state=42),
            {
                'n_estimators': [100, 150, 300, 500, 700, 1000],
                'max_depth': [2, 3, 4, 5],
                'learning_rate': [0.02, 0.03, 0.05, 0.08, 0.1]
            },
            {'n_estimators': 150, 'max_depth': 4, 'learning_rate': 0.08}
        ),
        'Random Forest': (
            RandomForestClassifier(class_weight='balanced', random_state=42),
            {
                'n_estimators': [100, 150, 300, 500],
                'max_depth': [6, 8, 12, 16, None],
                'min_samples_leaf': [1, 3]
            },
            {'n_estimators': 150, 'max_depth': 8, 'min_samples_leaf': 1}
        ),
        'XGBoost': (
            xgb.XGBClassifier(scale_pos_weight=ratio, eval_metric='logloss', random_state=42, n_jobs=1),
            {
                'n_estimators': [100, 150, 300, 500],
                'max_depth': [4, 6, 8, 12, 16, 20],
                'learning_rate': [0.08, 0.2, 0.3]
            },
            {'n_estimators': 150, 'max_depth': 4, 'learning_rate': 0.08}
        )
    }


def run_search(name, estimator, grid, current, X, y, features_num, features_cat, cv):
    """
    Ejecuta la búsqueda en grilla (GridSearchCV) para un modelo y compara contra su configuración actual.
    """
    preprocessor = build_preprocessor(features_num, features_cat)
    pipe = Pipeline([
        ('prep', preprocessor),
        ('clf', estimator)
    ])

    param_grid = {f'clf__{k}': v for k, v in grid.items()}
    grid_search = GridSearchCV(pipe, param_grid, scoring='f1', cv=cv, n_jobs=-1, refit=False)

    grid_search.fit(X, y)

    cv_results = grid_search.cv_results_

    current_cleaned = _clean_params(current)
    current_index = None
    for idx, p in enumerate(cv_results['params']):
        if _clean_params(p) == current_cleaned:
            current_index = idx
            break

    if current_index is None:
        raise ValueError(f"No se encontró la configuración actual {current} en cv_results_ para el modelo {name}")

    best_index = int(grid_search.best_index_)
    best_params = _clean_params(cv_results['params'][best_index])

    current_f1_mean = float(cv_results['mean_test_score'][current_index])
    current_f1_std = float(cv_results['std_test_score'][current_index])
    current_rank = int(cv_results['rank_test_score'][current_index])

    best_f1_mean = float(cv_results['mean_test_score'][best_index])
    best_f1_std = float(cv_results['std_test_score'][best_index])

    f1_gain_vs_current = float(best_f1_mean - current_f1_mean)
    gain_below_current_std = bool(f1_gain_vs_current < current_f1_std)

    return {
        "n_combinations": len(cv_results['params']),
        "grid": _clean_grid(grid),
        "current_params": current_cleaned,
        "current_f1_mean": current_f1_mean,
        "current_f1_std": current_f1_std,
        "current_rank": current_rank,
        "best_params": best_params,
        "best_f1_mean": best_f1_mean,
        "best_f1_std": best_f1_std,
        "f1_gain_vs_current": f1_gain_vs_current,
        "gain_below_current_std": gain_below_current_std
    }


def main():
    X, y, features_num, features_cat = load_and_preprocess_data(DATA_PATH)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    ratio = (len(y) - sum(y)) / sum(y)
    search_spaces = get_search_spaces(ratio)

    models_results = {}
    print("\n[+] Iniciando búsqueda de hiperparámetros (GridSearchCV)...")

    start_time = time.time()
    for name, (estimator, grid, current) in search_spaces.items():
        print(f"   -> Evaluando {name}...")
        res = run_search(name, estimator, grid, current, X, y, features_num, features_cat, cv)
        models_results[name] = res
        print(
            f"{name} | F1 actual: {res['current_f1_mean']:.4f} ± {res['current_f1_std']:.4f} (rank {res['current_rank']}) | "
            f"Mejor F1: {res['best_f1_mean']:.4f} ± {res['best_f1_std']:.4f} | Mejores params: {res['best_params']}"
        )
    total_elapsed = round(time.time() - start_time, 1)
    print(f"\n[+] Tiempo total: {total_elapsed} s")

    output_data = {
        "cv": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "scoring": "f1",
        "n_samples": int(len(y)),
        "models": models_results
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"[+] Resultados exportados exitosamente a {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
