import pytest
import pandas as pd
from unittest.mock import patch
from fastapi import HTTPException
from app.services.calendar_service import (
    get_calendar_data,
    simulate_appointment_service,
)
from app.schemas.calendar import SimulateAppointmentRequest


# ---------------------------------------------------------------------------
# Tests del simulador (simulate_appointment_service)
# ---------------------------------------------------------------------------

def test_simulate_profile_matias():
    req = SimulateAppointmentRequest(client_profile="matias")
    result = simulate_appointment_service(req)
    assert result.client_hashed == "Matías Giménez"
    assert "2 inasistencias sobre 4" in result.diagnostic


@pytest.mark.parametrize("profile", ["tomas", "nuevo"])
def test_simulate_profile_tomas_and_nuevo(profile):
    req = SimulateAppointmentRequest(client_profile=profile)
    result = simulate_appointment_service(req)
    assert result.diagnostic.startswith("Cliente nuevo")


def test_simulate_profile_unknown_or_gonzalo():
    req = SimulateAppointmentRequest(client_profile="gonzalo")
    result = simulate_appointment_service(req)
    assert result.diagnostic.startswith("Alerta predictiva")


def test_simulate_past_date_with_lead_time_hours():
    req = SimulateAppointmentRequest(date="2020-01-01", lead_time_hours=48.0)
    with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)) as mock_predict:
        simulate_appointment_service(req)
        assert mock_predict.called
        sim_row = mock_predict.call_args[0][0]
        assert sim_row["lead_time_hours"] == 48.0


def test_simulate_past_date_without_lead_time_hours():
    req = SimulateAppointmentRequest(date="2020-01-01", lead_time_hours=None)
    with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)) as mock_predict:
        simulate_appointment_service(req)
        assert mock_predict.called
        sim_row = mock_predict.call_args[0][0]
        assert sim_row["lead_time_hours"] == 1.0


def test_simulate_invalid_date_without_lead_time_hours():
    req = SimulateAppointmentRequest(date="no-es-fecha", lead_time_hours=None)
    with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)) as mock_predict:
        simulate_appointment_service(req)
        assert mock_predict.called
        sim_row = mock_predict.call_args[0][0]
        assert sim_row["lead_time_hours"] == 24.0
        assert sim_row["day_of_week"] == 2
        assert sim_row["month"] == 10


def test_simulate_invalid_start_time():
    req = SimulateAppointmentRequest(start_time="xx:yy")
    with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)) as mock_predict:
        result = simulate_appointment_service(req)
        assert result.end_time == "16:30:00"
        sim_row = mock_predict.call_args[0][0]
        assert sim_row["hour_of_day"] == 16


def test_simulate_predict_error_raises_http_500():
    req = SimulateAppointmentRequest()
    with patch("app.services.calendar_service.predict_appointment_risk", side_effect=RuntimeError("Engine failure")):
        with pytest.raises(HTTPException) as exc_info:
            simulate_appointment_service(req)
        assert exc_info.value.status_code == 500
        assert "Error en simulación" in exc_info.value.detail


def test_simulate_custom_client_name_with_profile_franco():
    req = SimulateAppointmentRequest(client_profile="franco", client_name="Ana")
    result = simulate_appointment_service(req)
    assert result.client_hashed == "Ana"


def test_simulate_future_date_calculates_positive_delta():
    req = SimulateAppointmentRequest(date="2099-01-01", start_time="10:00:00")
    with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)) as mock_predict:
        res = simulate_appointment_service(req)
        assert res.id >= 9000
        sim_row = mock_predict.call_args[0][0]
        assert sim_row["lead_time_hours"] > 0


# ---------------------------------------------------------------------------
# Tests del calendario (get_calendar_data)
# ---------------------------------------------------------------------------

@pytest.fixture
def calendar_csv_file(tmp_path):
    rows = [
        # client_2_noshows: 2 inasistencias pasadas
        {
            "id": 1, "shop_id": "hellfish", "date": "2026-05-01", "start_time": "10:00:00",
            "end_time": "10:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_2_noshows", "is_self_booked": 1, "target": 1,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-01 10:00:00"
        },
        {
            "id": 2, "shop_id": "hellfish", "date": "2026-05-02", "start_time": "10:00:00",
            "end_time": "10:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_2_noshows", "is_self_booked": 1, "target": 1,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-02 10:00:00"
        },
        {
            "id": 3, "shop_id": "hellfish", "date": "2026-05-10", "start_time": "10:00:00",
            "end_time": "10:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_2_noshows", "is_self_booked": 1, "target": 0,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-10 10:00:00"
        },
        # client_1_noshow: 1 inasistencia pasada
        {
            "id": 4, "shop_id": "hellfish", "date": "2026-05-01", "start_time": "11:00:00",
            "end_time": "11:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_1_noshow", "is_self_booked": 1, "target": 1,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-01 11:00:00"
        },
        {
            "id": 5, "shop_id": "hellfish", "date": "2026-05-10", "start_time": "11:00:00",
            "end_time": "11:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_1_noshow", "is_self_booked": 1, "target": 0,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-10 11:00:00"
        },
        # client_new: sin historial
        {
            "id": 6, "shop_id": "hellfish", "date": "2026-05-10", "start_time": "12:00:00",
            "end_time": "12:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_new", "is_self_booked": 1, "target": 0,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-10 12:00:00"
        },
        # client_loyal: historial con 0 inasistencias
        {
            "id": 7, "shop_id": "hellfish", "date": "2026-05-01", "start_time": "13:00:00",
            "end_time": "13:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_loyal", "is_self_booked": 1, "target": 0,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-01 13:00:00"
        },
        {
            "id": 8, "shop_id": "hellfish", "date": "2026-05-10", "start_time": "13:00:00",
            "end_time": "13:30:00", "barber_id": 1, "barber_name": "Barbero 1", "barber_active": True,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_loyal", "is_self_booked": 1, "target": 0,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-10 13:00:00"
        },
        # Barbero inactivo
        {
            "id": 9, "shop_id": "hellfish", "date": "2026-05-10", "start_time": "14:00:00",
            "end_time": "14:30:00", "barber_id": 2, "barber_name": "Barbero Inactivo", "barber_active": False,
            "service_name": "Corte", "service_price": 10000.0, "duration": 30,
            "client_hashed": "client_inactive_barber", "is_self_booked": 1, "target": 0,
            "lead_time_hours": 24.0, "appointment_start": "2026-05-10 14:00:00"
        },
    ]
    csv_path = tmp_path / "processed_test_calendar.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return str(csv_path)


def test_calendar_high_risk_diagnostics(calendar_csv_file):
    with patch("app.services.calendar_service.DATA_SOURCE", "CSV"):
        with patch("app.services.calendar_service.PROCESSED_FILE", calendar_csv_file):
            with patch("app.services.calendar_service.predict_appointment_risk", return_value=("ALTO", "#ef4444", 0.8)):
                res = get_calendar_data(shop_id="hellfish", date="2026-05-10")
                apps_by_client = {app.client_hashed: app for app in res.appointments}

                # cliente con 2 inasistencias previas
                assert "no se presentó a 2 de sus turnos" in apps_by_client["client_2_noshows"].diagnostic
                # cliente con 1 inasistencia previa
                assert "no se presentó a su último turno" in apps_by_client["client_1_noshow"].diagnostic
                # sin historial
                assert "Primer turno del cliente" in apps_by_client["client_new"].diagnostic
                # con historial y 0 inasistencias
                assert "varios días de anticipación" in apps_by_client["client_loyal"].diagnostic
                # profesional inactivo
                assert "inactivo" in apps_by_client["client_inactive_barber"].diagnostic


def test_calendar_medium_and_low_risk_diagnostics(calendar_csv_file):
    with patch("app.services.calendar_service.DATA_SOURCE", "CSV"):
        with patch("app.services.calendar_service.PROCESSED_FILE", calendar_csv_file):
            # Prueba riesgo MEDIO
            with patch("app.services.calendar_service.predict_appointment_risk", return_value=("MEDIO", "#f59e0b", 0.35)):
                res_med = get_calendar_data(shop_id="hellfish", date="2026-05-10")
                app_med = next(a for a in res_med.appointments if a.client_hashed == "client_new")
                assert "horario concurrido" in app_med.diagnostic

            # Prueba riesgo BAJO
            with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.10)):
                res_low = get_calendar_data(shop_id="hellfish", date="2026-05-10")
                app_loyal = next(a for a in res_low.appointments if a.client_hashed == "client_2_noshows")
                # past_apps >= 2 pero past_noshows > 0 -> "bajo margen"
                assert "bajo margen" in app_loyal.diagnostic


def test_calendar_postgres_mode(tmp_path):
    csv_file = tmp_path / "processed_test.csv"
    df_db = pd.DataFrame([{
        "id": 101,
        "shop_id": "hellfish",
        "date": "2026-07-20",
        "start_time": "10:00:00",
        "end_time": "10:30:00",
        "barber_id": 1,
        "barber_name": "Test Barber",
        "barber_active": True,
        "service_name": "Corte",
        "service_price": 5000.0,
        "duration": 30,
        "client_hashed": "client_pg",
        "is_self_booked": 1,
        "target": 0,
        "lead_time_hours": 24.0,
        "appointment_start": "2026-07-20 10:00:00",
    }])
    df_db.to_csv(csv_file, index=False)

    with patch("app.services.calendar_service.DATA_SOURCE", "POSTGRES"):
        with patch("app.services.calendar_service.PROCESSED_FILE", str(csv_file)):
            with patch("app.services.calendar_service.fetch_appointments_from_db", return_value=df_db):
                with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)):
                    res = get_calendar_data(shop_id="hellfish", date="2026-07-20")
                    assert res.shop_id == "hellfish"
                    assert res.date == "2026-07-20"
                    assert len(res.appointments) == 1


def test_calendar_read_csv_first_failure(tmp_path):
    csv_file = tmp_path / "processed_test.csv"
    df = pd.DataFrame([{
        "id": 201,
        "shop_id": "hellfish",
        "date": "2026-05-10",
        "start_time": "10:00:00",
        "end_time": "10:30:00",
        "barber_id": 1,
        "barber_name": "Test Barber",
        "barber_active": True,
        "service_name": "Corte",
        "service_price": 5000.0,
        "duration": 30,
        "client_hashed": "client_retry",
        "is_self_booked": 1,
        "target": 0,
        "lead_time_hours": 24.0,
        "appointment_start": "2026-05-10 10:00:00",
    }])
    df.to_csv(csv_file, index=False)

    with patch("app.services.calendar_service.DATA_SOURCE", "CSV"):
        with patch("app.services.calendar_service.PROCESSED_FILE", str(csv_file)):
            with patch("pandas.read_csv", side_effect=[Exception("corrupt read"), df]):
                with patch("app.services.calendar_service.predict_appointment_risk", return_value=("BAJO", "#10b981", 0.1)):
                    res = get_calendar_data(shop_id="hellfish", date="2026-05-10")
                    assert res.date == "2026-05-10"
                    assert len(res.appointments) == 1


def test_calendar_generic_error_raises_http_500(tmp_path):
    csv_file = tmp_path / "processed_test.csv"
    df = pd.DataFrame([{
        "id": 301,
        "shop_id": "hellfish",
        "date": "2026-05-10",
        "start_time": "10:00:00",
        "end_time": "10:30:00",
        "barber_id": 1,
        "barber_name": "Test Barber",
        "barber_active": True,
        "service_name": "Corte",
        "service_price": 5000.0,
        "duration": 30,
        "client_hashed": "client_err",
        "is_self_booked": 1,
        "target": 0,
        "lead_time_hours": 24.0,
        "appointment_start": "2026-05-10 10:00:00",
    }])
    df.to_csv(csv_file, index=False)

    with patch("app.services.calendar_service.DATA_SOURCE", "CSV"):
        with patch("app.services.calendar_service.PROCESSED_FILE", str(csv_file)):
            with patch("app.services.calendar_service.predict_appointment_risk", side_effect=ValueError("predict failed")):
                with pytest.raises(HTTPException) as exc_info:
                    get_calendar_data(shop_id="hellfish", date="2026-05-10")
                assert exc_info.value.status_code == 500
