from datetime import date, datetime
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from app.schemas.calendar import AppointmentResponse, CalendarResponse
from app.services.export_service import (
    ExportUnavailable,
    InvalidExportRange,
    appointment_to_row,
    build_export_rows,
    format_actions,
    format_decimal,
    parse_export_range,
    rows_to_csv,
    safe_cell,
    suggested_action,
)
from conftest import auth_headers


def test_parse_export_range():
    # Rango de 31 días exactos: ok
    d_from, d_to = parse_export_range("2026-06-01", "2026-07-01")
    assert d_from == date(2026, 6, 1)
    assert d_to == date(2026, 7, 1)

    # Rango de 32 días: error
    with pytest.raises(InvalidExportRange) as exc_info:
        parse_export_range("2026-06-01", "2026-07-02")
    assert "31 días" in str(exc_info.value)

    # to < from: error
    with pytest.raises(InvalidExportRange):
        parse_export_range("2026-07-01", "2026-06-01")

    # Formato inválido: error
    with pytest.raises(InvalidExportRange):
        parse_export_range("06/01/2026", "07/01/2026")


def test_suggested_action():
    assert suggested_action("ALTO", False) == "Recordatorio priorizado por WhatsApp o confirmación manual"
    assert suggested_action("ALTO", True) == "Confirmación manual (cliente sin contacto por WhatsApp)"
    assert suggested_action("MEDIO", False) == "Monitoreo en la agenda"
    assert suggested_action("MEDIO", True) == "Monitoreo en la agenda"
    assert suggested_action("BAJO", False) == "Sin intervención"
    assert suggested_action("BAJO", True) == "Sin intervención"


def test_formatting_and_safe_cell():
    actions = [
        {"action_type": "confirm", "created_at": datetime(2026, 11, 7, 10, 20)},
        {"action_type": "whatsapp", "created_at": datetime(2026, 11, 7, 10, 15)},
    ]
    formatted = format_actions(actions)
    assert formatted == "WhatsApp 2026-11-07 10:15 | Confirmación 2026-11-07 10:20"

    assert format_decimal(0.9685, 4) == "0,9685"
    assert format_decimal(15000.0, 2) == "15000,00"
    assert format_decimal(None, 2) == ""

    assert safe_cell("=SUM(A1)") == "'=SUM(A1)"
    assert safe_cell("+12345") == "'+12345"
    assert safe_cell("-test") == "'-test"
    assert safe_cell("@admin") == "'@admin"
    assert safe_cell("Normal text") == "Normal text"


def test_appointment_to_row():
    appt = AppointmentResponse(
        id=10,
        barber_id=1,
        barber_name="Facundo (Yayu)",
        date="2026-06-04",
        start_time="10:00:00",
        end_time="10:30:00",
        service_name="Corte",
        service_price=22000.0,
        service_duration=30,
        client_hashed="",
        is_self_booked=1,
        target=None,
        ausentismo_risk="ALTO",
        noshow_probability=0.7523,
        color_code="#ef4444",
        diagnostic="Diagnóstico",
        contact_blocked=True,
        client_erased=True,
    )

    row = appointment_to_row(appt, {})
    assert row['cliente_hash'] == ""
    assert row['datos_suprimidos'] == "sí"
    assert row['contacto_bloqueado'] == "sí"
    assert row['accion_sugerida'] == "Confirmación manual (cliente sin contacto por WhatsApp)"
    assert row['canal'] == "autogestión"
    assert row['asistencia_real'] == ""


def test_rows_to_csv():
    # Sin filas: encabezado con BOM
    csv_empty = rows_to_csv([])
    assert csv_empty.startswith('\ufeff')
    lines_empty = csv_empty.split('\r\n')
    assert len(lines_empty[0].split(';')) == 17

    # Con una fila: 17 campos en la segunda línea
    row = {
        'fecha': '2026-06-04',
        'hora_inicio': '10:00:00',
        'hora_fin': '10:30:00',
        'turno_id': '10',
        'profesional': 'Facundo',
        'servicio': 'Corte',
        'precio_servicio': '22000,00',
        'duracion_min': '30',
        'cliente_hash': 'abc',
        'canal': 'personal',
        'riesgo': 'BAJO',
        'probabilidad_ausencia': '0,1200',
        'accion_sugerida': 'Sin intervención',
        'contacto_bloqueado': 'no',
        'datos_suprimidos': 'no',
        'acciones_registradas': '',
        'asistencia_real': 'asistió',
    }
    csv_with_row = rows_to_csv([row])
    lines = csv_with_row.split('\r\n')
    assert len(lines) >= 2
    assert len(lines[1].split(';')) == 17


def test_export_endpoint(client, anon_client):
    # 1. Sin token -> 401
    res = anon_client.get("/api/export?shop_id=hellfish&date_from=2026-06-01&date_to=2026-06-02")
    assert res.status_code == 401

    # 2. Usuario hooligans pidiendo hellfish -> 403
    hooligans_headers = auth_headers("hooligans", "shop", "hooligans")
    res = anon_client.get(
        "/api/export?shop_id=hellfish&date_from=2026-06-01&date_to=2026-06-02",
        headers=hooligans_headers,
    )
    assert res.status_code == 403

    # 3. Admin pidiendo comercio inexistente -> 404
    res = client.get("/api/export?shop_id=inexistente&date_from=2026-06-01&date_to=2026-06-02")
    assert res.status_code == 404

    # 4. Rango de 32 días -> 422
    res = client.get("/api/export?shop_id=hellfish&date_from=2026-06-01&date_to=2026-07-02")
    assert res.status_code == 422

    # 5. build_export_rows lanzando ExportUnavailable -> 503
    with patch("app.routers.export.build_export_rows", side_effect=ExportUnavailable("La base no responde")):
        res = client.get("/api/export?shop_id=hellfish&date_from=2026-06-01&date_to=2026-06-02")
        assert res.status_code == 503
        assert "La base no responde" in res.json()["detail"]

    # 6. Caso feliz con build_export_rows mockeado
    mock_rows = [{
        'fecha': '2026-06-01',
        'hora_inicio': '10:00:00',
        'hora_fin': '10:30:00',
        'turno_id': '1',
        'profesional': 'Facundo',
        'servicio': 'Corte',
        'precio_servicio': '20000,00',
        'duracion_min': '30',
        'cliente_hash': 'abcdef',
        'canal': 'personal',
        'riesgo': 'BAJO',
        'probabilidad_ausencia': '0,1000',
        'accion_sugerida': 'Sin intervención',
        'contacto_bloqueado': 'no',
        'datos_suprimidos': 'no',
        'acciones_registradas': '',
        'asistencia_real': 'asistió',
    }]
    with patch("app.routers.export.build_export_rows", return_value=mock_rows):
        res = client.get("/api/export?shop_id=hellfish&date_from=2026-06-01&date_to=2026-06-02")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/csv")
        assert 'filename="turnofiel_hellfish_2026-06-01_2026-06-02.csv"' in res.headers["content-disposition"]
        assert res.content.startswith(b'\xef\xbb\xbf')


def test_build_export_rows():
    appt1 = AppointmentResponse(
        id=101,
        barber_id=1,
        barber_name="Facundo",
        date="2026-06-01",
        start_time="09:00:00",
        end_time="09:30:00",
        service_name="Corte",
        service_price=20000.0,
        service_duration=30,
        client_hashed="hash1",
        is_self_booked=1,
        target=0,
        ausentismo_risk="BAJO",
        noshow_probability=0.1,
        color_code="#10b981",
        diagnostic="Ok",
        contact_blocked=False,
        client_erased=False,
    )
    appt3 = AppointmentResponse(
        id=102,
        barber_id=1,
        barber_name="Facundo",
        date="2026-06-03",
        start_time="11:00:00",
        end_time="11:30:00",
        service_name="Corte",
        service_price=20000.0,
        service_duration=30,
        client_hashed="hash2",
        is_self_booked=0,
        target=1,
        ausentismo_risk="ALTO",
        noshow_probability=0.8,
        color_code="#ef4444",
        diagnostic="Riesgo",
        contact_blocked=False,
        client_erased=False,
    )

    cal1 = CalendarResponse(shop_id="hellfish", date="2026-06-01", total_appointments=1, appointments=[appt1])
    cal3 = CalendarResponse(shop_id="hellfish", date="2026-06-03", total_appointments=1, appointments=[appt3])

    def mock_get_cal(shop_id, date):
        if date == "2026-06-01":
            return cal1
        elif date == "2026-06-02":
            raise HTTPException(status_code=404, detail="No appointments")
        elif date == "2026-06-03":
            return cal3
        raise HTTPException(status_code=404)

    with patch("app.services.export_service.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.export_service.fetch_privacy_state", return_value={}), \
         patch("app.services.export_service.list_actions", return_value=[]), \
         patch("app.services.export_service.get_calendar_data", side_effect=mock_get_cal):
        rows = build_export_rows("hellfish", date(2026, 6, 1), date(2026, 6, 3))
        assert len(rows) == 2
        assert [r['turno_id'] for r in rows] == ['101', '102']

    # Si fetch_privacy_state lanza -> ExportUnavailable
    with patch("app.services.export_service.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.export_service.fetch_privacy_state", side_effect=RuntimeError("DB fail")), \
         patch("app.services.export_service.list_actions", return_value=[]):
        with pytest.raises(ExportUnavailable):
            build_export_rows("hellfish", date(2026, 6, 1), date(2026, 6, 3))


def test_build_export_rows_privacy_second_barrier():
    appt = AppointmentResponse(
        id=200,
        barber_id=1,
        barber_name="Facundo",
        date="2026-06-01",
        start_time="10:00:00",
        end_time="10:30:00",
        service_name="Corte",
        service_price=20000.0,
        service_duration=30,
        client_hashed="abc",
        is_self_booked=1,
        target=None,
        ausentismo_risk="ALTO",
        noshow_probability=0.75,
        color_code="#ef4444",
        diagnostic="Riesgo",
        contact_blocked=False,
        client_erased=False,
    )
    cal = CalendarResponse(shop_id="hellfish", date="2026-06-01", total_appointments=1, appointments=[appt])

    mock_state = {'abc': {'erased': True, 'do_not_contact': True}}

    with patch("app.services.export_service.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.export_service.fetch_privacy_state", return_value=mock_state), \
         patch("app.services.export_service.list_actions", return_value=[]), \
         patch("app.services.export_service.get_calendar_data", return_value=cal):
        rows = build_export_rows("hellfish", date(2026, 6, 1), date(2026, 6, 1))
        assert len(rows) == 1
        row = rows[0]
        assert row['cliente_hash'] == ''
        assert row['datos_suprimidos'] == 'sí'
        assert row['contacto_bloqueado'] == 'sí'
        assert row['accion_sugerida'] == 'Confirmación manual (cliente sin contacto por WhatsApp)'
