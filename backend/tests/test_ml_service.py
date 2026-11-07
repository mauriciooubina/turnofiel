import os
import time
import statistics
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch
from app.services.ml_service import (
    get_ml_model,
    predict_appointment_risk,
    clean_lead_time_for_inference,
    LEAD_TIME_MEDIAN_STAFF,
    LEAD_TIME_MEDIAN_SELF_BOOKED,
)

def test_get_ml_model_success():
    model = get_ml_model()
    assert model is not None
    assert hasattr(model, "predict_proba")

def test_predict_inactive_barber():
    row = pd.Series({"barber_active": False})
    risk, color, prob = predict_appointment_risk(row)
    assert risk == "ALTO"
    assert color == "#ef4444"
    assert prob == 0.99

def test_predict_standard_appointment():
    row = pd.Series({
        "barber_active": True,
        "lead_time_hours": 24.0,
        "service_price": 8500.0,
        "duration": 30,
        "hour_of_day": 15,
        "shop_id": "hellfish",
        "is_self_booked": 1,
        "day_of_week": 3,
        "month": 4,
        "barber_id": "1",
        "client_hashed": "client_abc",
        "appointment_start": "2026-04-10 15:00:00"
    })
    risk, color, prob = predict_appointment_risk(row)
    assert risk in ["ALTO", "MEDIO", "BAJO"]
    assert color in ["#ef4444", "#f59e0b", "#10b981"]
    assert 0.0 <= prob <= 1.0

def test_predict_with_historical_context():
    historical_df = pd.DataFrame([
        {
            "client_hashed": "repeat_client",
            "appointment_start": "2026-03-01 10:00:00",
            "target": 1
        },
        {
            "client_hashed": "repeat_client",
            "appointment_start": "2026-03-15 10:00:00",
            "target": 1
        },
        {
            "client_hashed": "loyal_client",
            "appointment_start": "2026-03-01 10:00:00",
            "target": 0
        },
        {
            "client_hashed": "loyal_client",
            "appointment_start": "2026-03-15 10:00:00",
            "target": 0
        }
    ])
    
    bad_row = pd.Series({
        "barber_active": True,
        "lead_time_hours": 120.0,
        "service_price": 12000.0,
        "duration": 45,
        "hour_of_day": 18,
        "shop_id": "hellfish",
        "is_self_booked": 1,
        "day_of_week": 5,
        "month": 3,
        "barber_id": "1",
        "client_hashed": "repeat_client",
        "appointment_start": "2026-03-20 10:00:00"
    })
    risk_bad, _, prob_bad = predict_appointment_risk(bad_row, all_appointments_df=historical_df)
    
    good_row = pd.Series({
        "barber_active": True,
        "lead_time_hours": 2.0,
        "service_price": 5000.0,
        "duration": 30,
        "hour_of_day": 11,
        "shop_id": "hellfish",
        "is_self_booked": 0,
        "day_of_week": 2,
        "month": 3,
        "barber_id": "1",
        "client_hashed": "loyal_client",
        "appointment_start": "2026-03-20 10:00:00"
    })
    risk_good, _, prob_good = predict_appointment_risk(good_row, all_appointments_df=historical_df)
    
    assert prob_bad > prob_good

def test_predict_fallback_when_model_is_none():
    with patch("app.services.ml_service.get_ml_model", return_value=None):
        row_high = pd.Series({"lead_time_hours": 100.0, "is_self_booked": 1, "barber_active": True})
        risk, color, prob = predict_appointment_risk(row_high)
        assert risk == "ALTO"
        assert color == "#ef4444"
        assert prob == 0.75
        
        row_short = pd.Series({"lead_time_hours": 3.0, "is_self_booked": 1, "barber_active": True})
        risk, color, prob = predict_appointment_risk(row_short)
        assert risk == "MEDIO"
        assert color == "#f59e0b"
        assert prob == 0.35
        
        row_other = pd.Series({"lead_time_hours": 24.0, "is_self_booked": 0, "barber_active": True})
        risk, color, prob = predict_appointment_risk(row_other)
        assert risk == "BAJO"
        assert color == "#10b981"
        assert prob == 0.10

def test_predict_fallback_when_exception_in_prediction():
    mock_model = patch("app.services.ml_service.get_ml_model").start()
    mock_model.return_value.predict_proba.side_effect = RuntimeError("Inference failed")
    
    row = pd.Series({"lead_time_hours": 100.0, "is_self_booked": 1, "barber_active": True})
    risk, color, prob = predict_appointment_risk(row)
    assert risk == "ALTO"
    assert prob == 0.75
    patch.stopall()

@pytest.mark.parametrize("prob,expected", [
    (0.19, "BAJO"),
    (0.20, "MEDIO"),
    (0.49, "MEDIO"),
    (0.50, "ALTO"),
])
def test_predict_risk_bands_thresholds(prob, expected):
    with patch("app.services.ml_service.get_ml_model") as mock_get_model:
        mock_get_model.return_value.predict_proba.return_value = np.array([[1 - prob, prob]])
        row = pd.Series({"lead_time_hours": 24.0, "is_self_booked": 0, "barber_active": True})
        risk, _, return_prob = predict_appointment_risk(row)
        assert risk == expected
        assert return_prob == round(prob, 4)


def test_predict_documented_high_risk_case():
    history = pd.DataFrame([{
        "client_hashed": "repeat_noshow_client",
        "appointment_start": "2026-04-01 18:00:00",
        "date": "2026-04-01",
        "target": 1,
        "shop_id": "hellfish",
    }])
    row = pd.Series({
        "client_hashed": "repeat_noshow_client",
        "appointment_start": "2026-05-15 18:00:00",
        "date": "2026-05-15",
        "shop_id": "hellfish",
        "lead_time_hours": 96.0,
        "hour_of_day": 18,
        "day_of_week": 4,
        "month": 5,
        "barber_id": "1",
        "barber_active": True,
        "service_price": 18000.0,
        "duration": 30,
        "is_self_booked": 0,
    })
    assert get_ml_model() is not None

    risk, color, prob = predict_appointment_risk(row, all_appointments_df=history)
    assert risk == "ALTO"
    assert color == "#ef4444"
    assert prob == pytest.approx(0.68, abs=0.01)

    predict_appointment_risk(row, all_appointments_df=history)
    timings_ms = []
    for _ in range(20):
        start = time.perf_counter()
        predict_appointment_risk(row, all_appointments_df=history)
        timings_ms.append((time.perf_counter() - start) * 1000)
    assert statistics.median(timings_ms) < 5.0


def test_clean_lead_time_for_inference():
    # −5 con canal 0 → 22.214066666666668
    assert clean_lead_time_for_inference(-5, 0) == pytest.approx(22.214066666666668, abs=1e-9)
    # −5 con canal 1 → 24.238278888888892
    assert clean_lead_time_for_inference(-5, 1) == pytest.approx(24.238278888888892, abs=1e-9)
    # NaN → mediana de autogestión
    assert clean_lead_time_for_inference(np.nan, 0) == pytest.approx(24.238278888888892, abs=1e-9)
    assert clean_lead_time_for_inference(None, 0) == pytest.approx(24.238278888888892, abs=1e-9)
    # 30 → 30
    assert clean_lead_time_for_inference(30, 0) == 30.0
    # 1000 → 720
    assert clean_lead_time_for_inference(1000, 0) == 720.0
    # 0 → 0
    assert clean_lead_time_for_inference(0, 0) == 0.0
    # is_self_booked=NaN con −5 → mediana del personal
    assert clean_lead_time_for_inference(-5, np.nan) == pytest.approx(22.214066666666668, abs=1e-9)


def test_lead_time_medians_match_processed_matrix():
    from data_pipeline.train_models import compute_channel_lead_time_medians
    matrix_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "processed_appointments_matrix.csv")
    )
    if not os.path.exists(matrix_path):
        pytest.skip(f"Matriz de datos no encontrada en {matrix_path}")
    df = pd.read_csv(matrix_path)
    med_0, med_1 = compute_channel_lead_time_medians(df)
    assert LEAD_TIME_MEDIAN_STAFF == pytest.approx(med_0, abs=1e-9)
    assert LEAD_TIME_MEDIAN_SELF_BOOKED == pytest.approx(med_1, abs=1e-9)


def test_predict_passes_imputed_clean_lead_time():
    with patch("app.services.ml_service.get_ml_model") as mock_get_model:
        mock_model = mock_get_model.return_value
        mock_model.predict_proba.return_value = np.array([[0.8, 0.2]])
        row = pd.Series({
            "barber_active": True,
            "lead_time_hours": -10.0,
            "is_self_booked": 0,
            "service_price": 10000.0,
            "duration": 30,
            "hour_of_day": 14,
            "shop_id": "hellfish",
            "day_of_week": 2,
            "month": 3,
            "barber_id": "1",
        })
        predict_appointment_risk(row)
        assert mock_model.predict_proba.called
        features_passed = mock_model.predict_proba.call_args[0][0]
        assert features_passed['clean_lead_time'].iloc[0] == pytest.approx(LEAD_TIME_MEDIAN_STAFF, abs=1e-9)


def test_predict_history_by_date_without_appointment_start():
    # Fila sin appointment_start y con date="2026-05-15"
    # Historial con 2 turnos anteriores (1 inasistencia) y 1 posterior
    history = pd.DataFrame([
        {
            "client_hashed": "date_history_client",
            "date": "2026-05-01",
            "target": 0
        },
        {
            "client_hashed": "date_history_client",
            "date": "2026-05-10",
            "target": 1
        },
        {
            "client_hashed": "date_history_client",
            "date": "2026-05-20",
            "target": 0
        }
    ])
    row = pd.Series({
        "barber_active": True,
        "client_hashed": "date_history_client",
        "date": "2026-05-15",
        "appointment_start": None,
        "lead_time_hours": 24.0,
        "is_self_booked": 1,
        "service_price": 10000.0,
        "duration": 30,
        "hour_of_day": 14,
        "shop_id": "hellfish",
        "day_of_week": 2,
        "month": 3,
        "barber_id": "1",
    })
    with patch("app.services.ml_service.get_ml_model") as mock_get_model:
        mock_model = mock_get_model.return_value
        mock_model.predict_proba.return_value = np.array([[0.8, 0.2]])
        predict_appointment_risk(row, all_appointments_df=history)
        assert mock_model.predict_proba.called
        features_passed = mock_model.predict_proba.call_args[0][0]
        assert features_passed['client_past_apps'].iloc[0] == 2
        assert features_passed['client_past_noshows'].iloc[0] == 1
        assert features_passed['client_is_new'].iloc[0] == 0
        assert features_passed['client_noshow_rate'].iloc[0] == 0.5


def test_get_ml_model_nonexistent_and_corrupt(monkeypatch, tmp_path):
    import app.services.ml_service as ml_mod
    monkeypatch.setattr(ml_mod, "_cached_model", None)
    monkeypatch.setattr(ml_mod, "MODEL_PATH", "/nonexistent/path/model.joblib")
    assert ml_mod.get_ml_model() is None

    corrupt_file = tmp_path / "corrupt_model.joblib"
    corrupt_file.write_text("archivo de texto basura que no es joblib")
    monkeypatch.setattr(ml_mod, "_cached_model", None)
    monkeypatch.setattr(ml_mod, "MODEL_PATH", str(corrupt_file))
    assert ml_mod.get_ml_model() is None

