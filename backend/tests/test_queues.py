import pytest
from unittest.mock import patch
from fastapi import HTTPException
from app.services.queue_service import get_queue_metrics_data
import app.services.queue_service as queue_service
from app.schemas.calendar import CalendarResponse, AppointmentResponse

def test_get_queues_api(client):
    response = client.get("/api/queues")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    for item in data:
        assert "shop_id" in item
        assert "lambda_rate" in item
        assert "mu_rate" in item
        assert "servers" in item
        assert "metrics" in item
        m = item["metrics"]
        assert "utilization" in m
        assert "p0" in m
        assert "Lq" in m
        assert "Wq_minutes" in m
        assert "stable" in m

def test_queues_service_fallback_on_db_error():
    with patch("app.services.queue_service.fetch_queue_metrics_from_db", side_effect=Exception("DB Down")):
        data = get_queue_metrics_data()
        assert isinstance(data, list)
        assert len(data) >= 1

def test_queues_service_file_not_found():
    with patch("app.services.queue_service.DATA_SOURCE", "CSV"):
        with patch("os.path.exists", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                get_queue_metrics_data()
            assert exc_info.value.status_code == 404

def test_queues_service_generic_error():
    with patch("app.services.queue_service.DATA_SOURCE", "CSV"):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=IOError("Disk error")):
                with pytest.raises(HTTPException) as exc_info:
                    get_queue_metrics_data()
                assert exc_info.value.status_code == 500

def _build_mock_calendar():
    return CalendarResponse(
        shop_id="hooligans",
        date="2026-01-21",
        total_appointments=3,
        appointments=[
            AppointmentResponse(
                id=1,
                barber_id=1,
                barber_name="Barbero 1",
                date="2026-01-21",
                start_time="12:00:00",
                end_time="12:30:00",
                service_name="Corte",
                service_price=1000.0,
                service_duration=30,
                client_hashed="hash1",
                is_self_booked=1,
                target=0,
                ausentismo_risk="BAJO",
                noshow_probability=0.1,
                color_code="#22c55e",
            ),
            AppointmentResponse(
                id=2,
                barber_id=1,
                barber_name="Barbero 1",
                date="2026-01-21",
                start_time="12:30:00",
                end_time="13:00:00",
                service_name="Corte",
                service_price=1000.0,
                service_duration=30,
                client_hashed="hash2",
                is_self_booked=1,
                target=0,
                ausentismo_risk="MEDIO",
                noshow_probability=0.3,
                color_code="#eab308",
            ),
            AppointmentResponse(
                id=3,
                barber_id=1,
                barber_name="Barbero 1",
                date="2026-01-21",
                start_time="18:15:00",
                end_time="18:45:00",
                service_name="Corte",
                service_price=1000.0,
                service_duration=30,
                client_hashed="hash3",
                is_self_booked=1,
                target=0,
                ausentismo_risk="ALTO",
                noshow_probability=0.5,
                color_code="#ef4444",
            ),
        ]
    )

def _build_mock_queue_metrics():
    return [
        {
            "shop_id": "hooligans",
            "lambda_rate": 1.0,
            "mu_rate": 2.0,
            "servers": 2,
            "metrics": {
                "utilization": 0.25,
                "p0": 0.6,
                "Lq": 0.033,
                "Wq_hours": 0.033,
                "Wq_minutes": 2.0,
                "L": 0.533,
                "W_hours": 0.533,
                "W_minutes": 32.0,
                "stable": True,
            }
        }
    ]

def test_queues_cp5_custom_parameters(client):
    response = client.get("/api/queues?lambda_rate=3.5&mu_rate=1.2&servers=4")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    m = data[0]["metrics"]
    assert m["utilization"] == pytest.approx(0.729167, abs=1e-4)
    assert m["Lq"] == pytest.approx(1.278849, abs=1e-4)
    assert m["Wq_minutes"] == pytest.approx(21.923122, abs=1e-4)
    assert m["stable"] is True

def test_queues_custom_unstable_returns_null_waits(client):
    response = client.get("/api/queues?lambda_rate=5&mu_rate=1&servers=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    m = data[0]["metrics"]
    assert m["stable"] is False
    assert m["utilization"] == pytest.approx(2.5)
    assert m["Lq"] is None
    assert m["Wq_minutes"] is None

def test_queues_custom_partial_params_422(client):
    response = client.get("/api/queues?lambda_rate=3.5")
    assert response.status_code == 422

def test_queues_slots_without_walk_ins(client):
    queue_service._SLOT_BASE_CACHE.clear()
    with patch("app.services.queue_service.get_calendar_data", return_value=_build_mock_calendar()), \
         patch("app.services.queue_service.get_queue_metrics_data", return_value=_build_mock_queue_metrics()):
        response = client.get("/api/queues?shop_id=hooligans&date=2026-01-21")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["date"] == "2026-01-21"
        slots = item["slots"]
        assert len(slots) == 10
        slot_map = {s["hour"]: s for s in slots}

        slot12 = slot_map[12]
        assert slot12["scheduled"] == 2
        assert slot12["expected_attendance"] == pytest.approx(1.6, abs=1e-4)
        assert slot12["walk_ins"] == 0
        assert slot12["lambda_rate"] == pytest.approx(1.6, abs=1e-4)
        assert slot12["metrics"]["utilization"] == pytest.approx(0.4, abs=1e-4)
        assert slot12["metrics"]["Wq_minutes"] == pytest.approx(5.714286, abs=1e-4)
        assert slot12["label"] == "12:00\u201313:00"

        slot18 = slot_map[18]
        assert slot18["scheduled"] == 1
        assert slot18["expected_attendance"] == pytest.approx(0.5, abs=1e-4)
        assert slot18["metrics"]["utilization"] == pytest.approx(0.125, abs=1e-4)

        slot10 = slot_map[10]
        assert slot10["lambda_rate"] == 0
        assert slot10["metrics"]["utilization"] == 0

def test_queues_slots_with_walk_ins_recalculates(client):
    queue_service._SLOT_BASE_CACHE.clear()
    with patch("app.services.queue_service.get_calendar_data", return_value=_build_mock_calendar()), \
         patch("app.services.queue_service.get_queue_metrics_data", return_value=_build_mock_queue_metrics()):
        response = client.get("/api/queues?shop_id=hooligans&date=2026-01-21&walk_ins=12:2,18:4")
        assert response.status_code == 200
        data = response.json()
        slot_map = {s["hour"]: s for s in data[0]["slots"]}

        slot12 = slot_map[12]
        assert slot12["lambda_rate"] == pytest.approx(3.6, abs=1e-4)
        assert slot12["metrics"]["utilization"] == pytest.approx(0.9, abs=1e-4)
        assert slot12["metrics"]["Wq_minutes"] == pytest.approx(127.894737, abs=1e-4)
        assert slot12["metrics"]["stable"] is True

        slot18 = slot_map[18]
        assert slot18["lambda_rate"] == pytest.approx(4.5, abs=1e-4)
        assert slot18["metrics"]["utilization"] == pytest.approx(1.125, abs=1e-4)
        assert slot18["metrics"]["stable"] is False
        assert slot18["metrics"]["Wq_minutes"] is None
        assert slot18["metrics"]["Lq"] is None

def test_queues_slots_cache_calls_calendar_once(client):
    queue_service._SLOT_BASE_CACHE.clear()
    with patch("app.services.queue_service.get_calendar_data", return_value=_build_mock_calendar()) as mock_cal, \
         patch("app.services.queue_service.get_queue_metrics_data", return_value=_build_mock_queue_metrics()):
        res1 = client.get("/api/queues?shop_id=hooligans&date=2026-01-21&walk_ins=12:1")
        assert res1.status_code == 200
        res2 = client.get("/api/queues?shop_id=hooligans&date=2026-01-21&walk_ins=12:3")
        assert res2.status_code == 200
        assert mock_cal.call_count == 1

@pytest.mark.parametrize("raw_walk_in", [
    "abc", "12", "12:x", "25:1", "12:21", "12:-1", "12:1,12:2", "9:1"
])
def test_queues_walk_ins_invalid_422(client, raw_walk_in):
    queue_service._SLOT_BASE_CACHE.clear()
    with patch("app.services.queue_service.get_calendar_data", return_value=_build_mock_calendar()), \
         patch("app.services.queue_service.get_queue_metrics_data", return_value=_build_mock_queue_metrics()):
        response = client.get(f"/api/queues?shop_id=hooligans&date=2026-01-21&walk_ins={raw_walk_in}")
        assert response.status_code == 422

def test_queues_walk_ins_without_shop_422(client):
    response = client.get("/api/queues?walk_ins=12:1")
    assert response.status_code == 422

def test_calendar_exposes_noshow_probability(client):
    response = client.get("/api/calendar?shop_id=hooligans&date=2026-01-21")
    assert response.status_code == 200
    data = response.json()
    assert "appointments" in data
    assert len(data["appointments"]) > 0
    for app_item in data["appointments"]:
        prob = app_item.get("noshow_probability")
        assert prob is not None
        assert 0.0 <= prob <= 1.0
