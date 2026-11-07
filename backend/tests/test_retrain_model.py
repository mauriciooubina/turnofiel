import hashlib
import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingClassifier

try:
    from data_pipeline import retrain_model, train_models
except ImportError:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pipeline_dir = os.path.join(root_dir, "data_pipeline")
    if pipeline_dir not in sys.path:
        sys.path.append(pipeline_dir)
    import retrain_model
    import train_models


def _create_synthetic_csv(path: str, n: int = 120, seed: int = 42) -> str:
    """Genera un archivo CSV sintético con n turnos y aproximadamente 25% de ausencias."""
    rng = np.random.RandomState(seed)
    shops = ['hellfish', 'hooligans']
    rows = []
    for i in range(n):
        rows.append({
            'shop_id': shops[i % 2],
            'barber_id': str((i % 3) + 1),
            'client_hashed': f'client_{i % 15}',
            'is_self_booked': int(i % 2),
            'day_of_week': (i % 7),
            'hour_of_day': 9 + (i % 10),
            'month': 5 + (i % 3),
            'lead_time_hours': float(rng.uniform(1.0, 72.0)),
            'target': 1 if (i % 4 == 0) else 0,
            'price': 15000.0,
            'service_price': 15000.0,
            'duration': 30,
            'appointment_start': f'2026-05-{1 + (i % 20):02d} {9 + (i % 10):02d}:00:00',
        })
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return path


def test_load_and_preprocess_data_df_vs_csv(tmp_path):
    csv_file = str(tmp_path / "synthetic_appointments.csv")
    _create_synthetic_csv(csv_file, n=60, seed=123)
    df_raw = pd.read_csv(csv_file)

    X_from_df, y_from_df, num_df, cat_df = train_models.load_and_preprocess_data(df_raw)
    X_from_csv, y_from_csv, num_csv, cat_csv = train_models.load_and_preprocess_data(csv_file)

    pd.testing.assert_frame_equal(X_from_df, X_from_csv)
    np.testing.assert_array_equal(y_from_df, y_from_csv)
    assert num_df == num_csv
    assert cat_df == cat_csv


def test_gb_params_and_pipeline():
    expected_params = {'n_estimators': 150, 'max_depth': 4, 'learning_rate': 0.08, 'random_state': 42}
    assert retrain_model.GB_PARAMS == expected_params
    assert train_models.GB_PARAMS == expected_params

    pipe = retrain_model.build_final_pipeline(['clean_lead_time'], ['shop_id'])
    clf = pipe.named_steps['clf']
    assert isinstance(clf, GradientBoostingClassifier)
    params = clf.get_params()
    assert params['n_estimators'] == 150
    assert params['max_depth'] == 4
    assert params['learning_rate'] == 0.08
    assert params['random_state'] == 42


def test_exclude_erased():
    df = pd.DataFrame([
        {'shop_id': 'Hellfish', 'client_hashed': 'aaa'},
        {'shop_id': 'hooligans', 'client_hashed': 'aaa'},
        {'shop_id': 'hellfish', 'client_hashed': 'bbb'},
    ])

    filtered, excluded = retrain_model.exclude_erased(df, {('hellfish', 'aaa')})
    assert excluded == 1
    assert len(filtered) == 2
    assert list(filtered['client_hashed']) == ['aaa', 'bbb']
    assert list(filtered['shop_id']) == ['hooligans', 'hellfish']

    filtered_empty, excluded_empty = retrain_model.exclude_erased(df, set())
    assert excluded_empty == 0
    assert len(filtered_empty) == 3


def test_calibration_summary_and_report():
    y = [0, 1, 0, 1]
    p = [0.1, 0.9, 0.3, 0.6]

    res = retrain_model.calibration_summary(y, p)
    assert res['n'] == 4
    assert res['observed_rate'] == pytest.approx(0.5)
    assert res['predicted_rate'] == pytest.approx(0.475)
    assert res['brier'] == pytest.approx(0.0675)
    assert res['calibration_gap'] == pytest.approx(-0.025)

    bands = {b['band']: b for b in res['bands']}
    assert bands['BAJO']['n'] == 1
    assert bands['BAJO']['predicted_rate'] == pytest.approx(0.1)
    assert bands['BAJO']['observed_rate'] == pytest.approx(0.0)

    assert bands['MEDIO']['n'] == 1
    assert bands['MEDIO']['predicted_rate'] == pytest.approx(0.3)
    assert bands['MEDIO']['observed_rate'] == pytest.approx(0.0)

    assert bands['ALTO']['n'] == 2
    assert bands['ALTO']['predicted_rate'] == pytest.approx(0.75)
    assert bands['ALTO']['observed_rate'] == pytest.approx(1.0)

    # Banda vacía da None
    res_one = retrain_model.calibration_summary([0], [0.1])
    bands_one = {b['band']: b for b in res_one['bands']}
    assert bands_one['MEDIO']['n'] == 0
    assert bands_one['MEDIO']['predicted_rate'] is None
    assert bands_one['MEDIO']['observed_rate'] is None

    # calibration_report con shops
    rep = retrain_model.calibration_report(['a', 'a', 'b', 'b'], y, p)
    assert rep['by_shop']['a']['brier'] == pytest.approx(0.01)
    assert rep['by_shop']['a']['predicted_rate'] == pytest.approx(0.5)
    assert rep['by_shop']['b']['brier'] == pytest.approx(0.125)
    assert rep['by_shop']['b']['predicted_rate'] == pytest.approx(0.45)


def test_risk_band():
    assert retrain_model.risk_band(0.2) == 'MEDIO'
    assert retrain_model.risk_band(0.5) == 'ALTO'
    assert retrain_model.risk_band(0.1999) == 'BAJO'
    assert retrain_model.risk_band(1.0) == 'ALTO'


def test_validate_dataset():
    with pytest.raises(ValueError):
        retrain_model.validate_dataset(np.zeros(40))

    with pytest.raises(ValueError):
        retrain_model.validate_dataset(np.array([1] * 3 + [0] * 57))


def test_run_retraining_without_production(tmp_path):
    csv_file = str(tmp_path / "train_120.csv")
    _create_synthetic_csv(csv_file, n=120, seed=42)
    models_dir = str(tmp_path / "models")
    report_dir = str(tmp_path / "reports")
    fixed_now = datetime(2026, 11, 7, 3, 0, 0)

    res = retrain_model.run_retraining(
        source='csv',
        csv_path=csv_file,
        models_dir=models_dir,
        report_dir=report_dir,
        now=fixed_now,
    )

    required_keys = [
        'timestamp',
        'source',
        'n_appointments',
        'class_counts',
        'privacy',
        'hyperparameters',
        'cv_metrics',
        'calibration',
        'comparison_with_production',
        'candidate_path',
        'promoted',
        'backup_path',
        'note',
    ]
    for key in required_keys:
        assert key in res

    assert res['comparison_with_production'] is None
    assert res['promoted'] is False

    candidate_file = os.path.join(models_dir, 'candidates', 'gradient_boosting_candidate_20261107-030000.joblib')
    report_file = os.path.join(report_dir, 'retrain_report_20261107-030000.json')
    prod_file = os.path.join(models_dir, 'gradient_boosting_model.joblib')

    assert os.path.exists(candidate_file)
    assert os.path.exists(report_file)
    assert not os.path.exists(prod_file)


def test_run_retraining_with_production_no_promote(tmp_path):
    csv_file = str(tmp_path / "train_120.csv")
    _create_synthetic_csv(csv_file, n=120, seed=42)
    models_dir = str(tmp_path / "models")
    report_dir = str(tmp_path / "reports")
    os.makedirs(models_dir, exist_ok=True)

    # Entrenar modelo previo de producción en models_dir
    raw_df = pd.read_csv(csv_file)
    X, y, fnum, fcat = train_models.prepare_features(raw_df)
    prev_pipe = train_models.build_final_pipeline(fnum, fcat)
    prev_pipe.fit(X, y)
    prod_path = os.path.join(models_dir, retrain_model.PRODUCTION_MODEL_NAME)
    joblib.dump(prev_pipe, prod_path)

    with open(prod_path, 'rb') as f:
        prod_bytes_before = f.read()

    res = retrain_model.run_retraining(
        source='csv',
        csv_path=csv_file,
        models_dir=models_dir,
        report_dir=report_dir,
        promote=False,
        now=datetime(2026, 11, 7, 3, 0, 0),
    )

    with open(prod_path, 'rb') as f:
        prod_bytes_after = f.read()

    assert prod_bytes_before == prod_bytes_after
    assert res['comparison_with_production'] is not None
    comp = res['comparison_with_production']
    assert 'max_abs_proba_diff' in comp
    assert 'risk_level_changes' in comp
    assert 'threshold_crossings' in comp


def test_run_retraining_with_promote(tmp_path):
    csv_file = str(tmp_path / "train_120.csv")
    _create_synthetic_csv(csv_file, n=120, seed=42)
    models_dir = str(tmp_path / "models")
    report_dir = str(tmp_path / "reports")
    os.makedirs(models_dir, exist_ok=True)

    raw_df = pd.read_csv(csv_file)
    X, y, fnum, fcat = train_models.prepare_features(raw_df)
    prev_pipe = train_models.build_final_pipeline(fnum, fcat)
    prev_pipe.fit(X, y)
    prod_path = os.path.join(models_dir, retrain_model.PRODUCTION_MODEL_NAME)
    joblib.dump(prev_pipe, prod_path)

    with open(prod_path, 'rb') as f:
        prod_bytes_before = f.read()

    res = retrain_model.run_retraining(
        source='csv',
        csv_path=csv_file,
        models_dir=models_dir,
        report_dir=report_dir,
        promote=True,
        now=datetime(2026, 11, 7, 3, 0, 0),
    )

    backup_file = os.path.join(models_dir, 'backups', 'gradient_boosting_model_20261107-030000.joblib')
    candidate_file = os.path.join(models_dir, 'candidates', 'gradient_boosting_candidate_20261107-030000.joblib')

    assert os.path.exists(backup_file)
    with open(backup_file, 'rb') as f:
        backup_bytes = f.read()
    assert backup_bytes == prod_bytes_before

    with open(prod_path, 'rb') as f:
        prod_bytes_new = f.read()
    with open(candidate_file, 'rb') as f:
        cand_bytes = f.read()
    assert prod_bytes_new == cand_bytes


def test_load_training_frame_postgres():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    cols = [
        ('id',), ('shop_id',), ('barber_id',), ('client_hashed',), ('is_self_booked',),
        ('day_of_week',), ('hour_of_day',), ('month',), ('lead_time_hours',), ('target',),
        ('price',), ('service_price',), ('duration',), ('appointment_start',)
    ]
    mock_cur.description = cols

    rows_turnos = [
        (1, 'hellfish', 1, 'hash_erased', 1, 1, 10, 5, 24.0, 0, 10000.0, 10000.0, 30, '2026-05-01 10:00:00'),
        (2, 'hellfish', 1, 'hash_kept', 1, 1, 11, 5, 24.0, 1, 10000.0, 10000.0, 30, '2026-05-01 11:00:00'),
        (3, 'hooligans', 2, 'hash_erased', 1, 1, 12, 5, 24.0, 0, 10000.0, 10000.0, 30, '2026-05-01 12:00:00'),
    ]
    rows_erased = [('hellfish', 'hash_erased')]

    mock_cur.fetchall.side_effect = [rows_turnos, rows_erased]

    with patch.object(retrain_model, 'get_db_connection', return_value=mock_conn):
        df, privacy = retrain_model.load_training_frame('postgres')

    assert len(df) == 2
    assert privacy == {'filter': 'applied', 'erased_clients': 1, 'excluded_appointments': 1}
    mock_conn.close.assert_called_once()


def test_load_training_frame_postgres_nan_normalized():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    cols = [
        ('id',), ('shop_id',), ('barber_id',), ('client_hashed',), ('is_self_booked',),
        ('day_of_week',), ('hour_of_day',), ('month',), ('lead_time_hours',), ('target',),
        ('price',), ('service_price',), ('duration',), ('appointment_start',)
    ]
    mock_cur.description = cols

    rows_turnos = [
        (1, 'hellfish', 1, 'nan', 1, 1, 10, 5, 24.0, 0, 10000.0, 10000.0, 30, '2026-05-01 10:00:00'),
    ]
    rows_erased = []
    mock_cur.fetchall.side_effect = [rows_turnos, rows_erased]

    with patch.object(retrain_model, 'get_db_connection', return_value=mock_conn):
        df, privacy = retrain_model.load_training_frame('postgres')

    assert len(df) == 1
    assert pd.isna(df['client_hashed'].iloc[0])


def test_main_cli(tmp_path):
    mock_res = {
        'source': 'csv',
        'n_appointments': 100,
        'class_counts': {'0': 80, '1': 20},
        'privacy': {'filter': 'not_applied_csv_source', 'excluded_appointments': 0},
        'cv_metrics': {
            'f1_mean': 0.75,
            'f1_std': 0.05,
            'recall_mean': 0.70,
            'precision_mean': 0.80,
            'roc_auc_mean': 0.85,
            'brier_oof': 0.12,
        },
        'calibration': {
            'by_shop': {
                'hellfish': {'n': 50, 'observed_rate': 0.20, 'predicted_rate': 0.21, 'brier': 0.11},
            }
        },
        'comparison_with_production': {
            'max_abs_proba_diff': 0.02,
            'risk_level_changes': 1,
            'threshold_crossings': 0,
        },
        'candidate_path': 'path/to/cand.joblib',
        'report_path': 'path/to/rep.json',
        'promoted': False,
        'backup_path': None,
    }

    models_dir = str(tmp_path / "models")
    report_dir = str(tmp_path / "reports")

    with patch.object(retrain_model, 'run_retraining', return_value=mock_res) as mock_run:
        exit_code = retrain_model.main(['--source', 'csv', '--models-dir', models_dir, '--report-dir', report_dir])
        assert exit_code == 0
        mock_run.assert_called_once()

    with patch.object(retrain_model, 'run_retraining', side_effect=ValueError("Test error")) as mock_run_err:
        exit_code = retrain_model.main(['--source', 'csv', '--models-dir', models_dir, '--report-dir', report_dir])
        assert exit_code == 1
        mock_run_err.assert_called_once()


@pytest.mark.skipif(not os.path.exists(train_models.DATA_PATH), reason="Requiere matriz real en data/processed")
def test_run_retraining_integration_real_matrix(tmp_path):
    models_dir = str(tmp_path / "models")
    report_dir = str(tmp_path / "reports")

    metrics_path = os.path.join(train_models.BASE_DIR, 'data', 'processed', 'ml_metrics_summary.json')
    prod_path = os.path.join(train_models.MODELS_DIR, 'gradient_boosting_model.joblib')

    with open(metrics_path, 'rb') as f:
        metrics_hash_before = hashlib.sha256(f.read()).hexdigest()
    with open(prod_path, 'rb') as f:
        prod_hash_before = hashlib.sha256(f.read()).hexdigest()

    with open(metrics_path, 'r', encoding='utf-8') as f:
        metrics_doc = json.load(f)
    gb_doc = metrics_doc['Gradient Boosting']

    res = retrain_model.run_retraining(
        source='csv',
        models_dir=models_dir,
        report_dir=report_dir,
    )

    assert res['n_appointments'] == 5320
    cv = res['cv_metrics']
    for metric_key in ['f1_mean', 'f1_std', 'recall_mean', 'recall_std', 'precision_mean', 'precision_std', 'roc_auc_mean', 'roc_auc_std', 'accuracy_mean', 'accuracy_std']:
        assert cv[metric_key] == pytest.approx(gb_doc[metric_key], abs=1e-9)

    with open(metrics_path, 'rb') as f:
        metrics_hash_after = hashlib.sha256(f.read()).hexdigest()
    with open(prod_path, 'rb') as f:
        prod_hash_after = hashlib.sha256(f.read()).hexdigest()

    assert metrics_hash_before == metrics_hash_after
    assert prod_hash_before == prod_hash_after
