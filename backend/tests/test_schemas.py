import pytest
from pydantic import ValidationError
from app.schemas.actions import PreventiveActionRequest
from app.schemas.calendar import (
    SimulateAppointmentRequest,
    AppointmentResponse,
    CalendarResponse,
)
from app.schemas.queues import QueueMetricsResponse, ShopQueueData


# ---------------------------------------------------------------------------
# Tests de app/schemas/actions.py
# ---------------------------------------------------------------------------

def test_preventive_action_request_validation():
    # Válido con mensaje
    req_valid = PreventiveActionRequest(
        appointment_id=1,
        shop_id="hellfish",
        action_type="whatsapp",
        message="Recordatorio de turno"
    )
    assert req_valid.appointment_id == 1
    assert req_valid.shop_id == "hellfish"
    assert req_valid.action_type == "whatsapp"
    assert req_valid.message == "Recordatorio de turno"

    # message omitido → None
    req_no_msg = PreventiveActionRequest(
        appointment_id=2,
        shop_id="hooligans",
        action_type="confirm"
    )
    assert req_no_msg.message is None

    # appointment_id = 0 → error (gt=0)
    with pytest.raises(ValidationError):
        PreventiveActionRequest(appointment_id=0, shop_id="hellfish", action_type="whatsapp")

    # shop_id = "otro" → error (Literal["hellfish", "hooligans"])
    with pytest.raises(ValidationError):
        PreventiveActionRequest(appointment_id=1, shop_id="otro", action_type="whatsapp")

    # action_type = "sms" → error (Literal["whatsapp", "confirm"])
    with pytest.raises(ValidationError):
        PreventiveActionRequest(appointment_id=1, shop_id="hellfish", action_type="sms")

    # message de 1001 caracteres → error (max_length=1000)
    with pytest.raises(ValidationError):
        PreventiveActionRequest(
            appointment_id=1,
            shop_id="hellfish",
            action_type="whatsapp",
            message="a" * 1001
        )


# ---------------------------------------------------------------------------
# Tests de app/schemas/calendar.py
# ---------------------------------------------------------------------------

def test_simulate_appointment_request_defaults_and_validation():
    # Valores por defecto
    req = SimulateAppointmentRequest()
    assert req.shop_id == "hooligans"
    assert req.client_profile == "franco"
    assert req.is_self_booked == 1
    assert req.lead_time_hours is None

    # service_price = "abc" → error de validación
    with pytest.raises(ValidationError):
        SimulateAppointmentRequest(service_price="abc")


def test_appointment_response_validation():
    base_data = {
        "barber_id": 1,
        "barber_name": "Sebastian Fraga",
        "date": "2026-10-25",
        "start_time": "16:00:00",
        "end_time": "16:30:00",
        "service_name": "Corte de Pelo",
        "service_price": 18000.0,
        "service_duration": 30,
        "client_hashed": "hash_test_client",
        "is_self_booked": 1,
        "color_code": "#10b981",
    }

    # Falta ausentismo_risk → error
    with pytest.raises(ValidationError):
        AppointmentResponse(id=1, **base_data)

    # id="12" se convierte a 12 (modo laxo de Pydantic v2)
    resp = AppointmentResponse(id="12", ausentismo_risk="BAJO", **base_data)
    assert resp.id == 12
    assert isinstance(resp.id, int)

    # noshow_probability es opcional (None por defecto)
    assert resp.noshow_probability is None

    # noshow_probability asignado
    resp_prob = AppointmentResponse(
        id=12,
        ausentismo_risk="MEDIO",
        noshow_probability=0.35,
        **base_data
    )
    assert resp_prob.noshow_probability == 0.35


def test_calendar_response_empty_appointments():
    # CalendarResponse con lista vacía de turnos es válido
    cal = CalendarResponse(
        shop_id="hellfish",
        date="2026-05-10",
        total_appointments=0,
        appointments=[]
    )
    assert cal.shop_id == "hellfish"
    assert cal.appointments == []
    assert cal.total_appointments == 0


# ---------------------------------------------------------------------------
# Tests de app/schemas/queues.py
# ---------------------------------------------------------------------------

def test_queue_metrics_response_validation():
    # Falta stable → error
    with pytest.raises(ValidationError):
        QueueMetricsResponse(utilization=0.55, p0=0.45)

    # Lq=None es válido
    qm = QueueMetricsResponse(utilization=0.55, p0=0.45, stable=True, Lq=None)
    assert qm.stable is True
    assert qm.Lq is None


def test_shop_queue_data_without_slots():
    # ShopQueueData sin slots → slots is None
    metrics = QueueMetricsResponse(utilization=0.55, p0=0.45, stable=True)
    shop_data = ShopQueueData(
        shop_id="hellfish",
        lambda_rate=1.8,
        mu_rate=2.0,
        servers=2,
        metrics=metrics
    )
    assert shop_data.slots is None
