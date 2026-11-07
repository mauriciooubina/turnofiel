from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.actions import PreventiveActionRequest
from app.services.actions_service import list_actions, register_action

def test_register_action_inserts_and_commits():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = (1, 2814, "hooligans", "whatsapp", "Hola", datetime(2026, 1, 21, 10, 0))

    with patch("app.services.actions_service.get_db_connection", return_value=mock_conn):
        req = PreventiveActionRequest(
            appointment_id=2814,
            shop_id="hooligans",
            action_type="whatsapp",
            message="Hola"
        )
        res = register_action(req)

        assert res == {
            "id": 1,
            "appointment_id": 2814,
            "shop_id": "hooligans",
            "action_type": "whatsapp",
            "message": "Hola",
            "created_at": datetime(2026, 1, 21, 10, 0)
        }
        assert mock_conn.commit.called
        assert mock_conn.close.called

        insert_calls = [
            args for args in mock_cur.execute.call_args_list
            if "insert into preventive_actions" in args[0][0].lower()
        ]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1] == (2814, "hooligans", "whatsapp", "Hola")

def test_actions_sql_never_touches_appointments():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = (1, 2814, "hooligans", "whatsapp", "Hola", datetime(2026, 1, 21, 10, 0))
    mock_cur.fetchall.return_value = []

    with patch("app.services.actions_service.get_db_connection", return_value=mock_conn):
        req = PreventiveActionRequest(
            appointment_id=2814,
            shop_id="hooligans",
            action_type="whatsapp",
            message="Hola"
        )
        register_action(req)
        list_actions("hooligans")

        assert mock_cur.execute.call_count > 0
        for call_args in mock_cur.execute.call_args_list:
            sql = call_args[0][0]
            assert "appointments" not in sql.lower()
            assert "update " not in sql.lower()
            assert "delete " not in sql.lower()

def test_list_actions_returns_rows():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = [
        (1, 2814, "hooligans", "whatsapp", "Msg 1", datetime(2026, 1, 21, 10, 0)),
        (2, 2815, "hooligans", "confirm", None, datetime(2026, 1, 21, 10, 5))
    ]

    with patch("app.services.actions_service.get_db_connection", return_value=mock_conn):
        rows = list_actions("hooligans")
        assert len(rows) == 2
        assert rows[0] == {
            "id": 1,
            "appointment_id": 2814,
            "shop_id": "hooligans",
            "action_type": "whatsapp",
            "message": "Msg 1",
            "created_at": datetime(2026, 1, 21, 10, 0)
        }
        assert rows[1] == {
            "id": 2,
            "appointment_id": 2815,
            "shop_id": "hooligans",
            "action_type": "confirm",
            "message": None,
            "created_at": datetime(2026, 1, 21, 10, 5)
        }
        assert mock_conn.close.called

def test_post_action_endpoint_201(client):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = (1, 2814, "hooligans", "whatsapp", "Hola", datetime(2026, 1, 21, 10, 0))

    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.actions_service.get_db_connection", return_value=mock_conn):
        response = client.post("/api/actions", json={
            "appointment_id": 2814,
            "shop_id": "hooligans",
            "action_type": "whatsapp",
            "message": "Hola"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["action_type"] == "whatsapp"
        assert data["appointment_id"] == 2814
        assert data["id"] == 1

def test_post_action_invalid_type_422(client):
    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.actions_service.get_db_connection") as mock_get_db:
        response = client.post("/api/actions", json={
            "appointment_id": 2814,
            "shop_id": "hooligans",
            "action_type": "sms",
            "message": "Hola"
        })
        assert response.status_code == 422
        assert not mock_get_db.called

def test_post_action_db_down_503(client):
    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.actions_service.get_db_connection", side_effect=Exception("down")):
        response = client.post("/api/actions", json={
            "appointment_id": 2814,
            "shop_id": "hooligans",
            "action_type": "whatsapp",
            "message": "Hola"
        })
        assert response.status_code == 503
        assert "base de datos no disponible" in response.json()["detail"]

def test_post_action_csv_mode_503(client):
    with patch("app.routers.actions.DATA_SOURCE", "CSV"):
        response = client.post("/api/actions", json={
            "appointment_id": 2814,
            "shop_id": "hooligans",
            "action_type": "whatsapp",
            "message": "Hola"
        })
        assert response.status_code == 503
        assert "base de datos no disponible" in response.json()["detail"]

def test_get_actions_endpoint(client):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = [
        (1, 101, "hellfish", "whatsapp", "Msg 1", datetime(2026, 1, 21, 10, 0))
    ]

    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.actions_service.get_db_connection", return_value=mock_conn):
        response = client.get("/api/actions?shop_id=hellfish")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["shop_id"] == "hellfish"
        assert data[0]["appointment_id"] == 101
        assert data[0]["action_type"] == "whatsapp"


def test_actions_never_execute_create():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = (1, 2814, "hooligans", "whatsapp", "Hola", datetime(2026, 1, 21, 10, 0))
    mock_cur.fetchall.return_value = []

    with patch("app.services.actions_service.get_db_connection", return_value=mock_conn):
        req = PreventiveActionRequest(
            appointment_id=2814,
            shop_id="hooligans",
            action_type="whatsapp",
            message="Hola"
        )
        register_action(req)
        list_actions("hooligans")

        assert mock_cur.execute.call_count > 0
        for call_args in mock_cur.execute.call_args_list:
            sql = call_args[0][0]
            assert "create table" not in str(sql).lower()

