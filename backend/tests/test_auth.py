from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock, patch
import jwt
import pytest

from conftest import auth_headers
from app import config
from app.schemas.auth import CurrentUser
from app.services.auth_service import (
    authenticate_user,
    decode_access_token,
    fetch_user,
    hash_password,
    verify_password,
)

def test_case_1_hash_and_verify_password():
    raw_pass = "supersecret123"
    h = hash_password(raw_pass)
    assert h.startswith("$2b$")
    assert verify_password(raw_pass, h) is True
    assert verify_password("wrongpassword", h) is False

def test_case_2_password_length_limits_and_invalid_hash():
    long_pass = "a" * 73
    with pytest.raises(ValueError, match="La contraseña no puede superar 72 bytes"):
        hash_password(long_pass)
    assert verify_password(long_pass, "$2b$12$somevalidlengthbutfakehashhere1234567890123456789012345") is False
    assert verify_password("password", "invalid_garbage_hash") is False

def test_case_3_authenticate_user():
    real_hash = hash_password("validpassword")
    mock_user = {
        "username": "admin",
        "password_hash": real_hash,
        "role": "admin",
        "shop_id": None,
    }

    # Usuario existente y contraseña correcta
    with patch("app.services.auth_service.fetch_user", return_value=mock_user):
        res = authenticate_user("admin", "validpassword")
        assert res == {"username": "admin", "role": "admin", "shop_id": None}
        assert "password_hash" not in res

    # Contraseña mala
    with patch("app.services.auth_service.fetch_user", return_value=mock_user):
        res = authenticate_user("admin", "wrongpassword")
        assert res is None

    # Usuario inexistente -> verify_password se llamó igual con el dummy hash (tiempo constante)
    from app.services import auth_service
    with patch("app.services.auth_service.fetch_user", return_value=None), \
         patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_verify:
        res = authenticate_user("nonexistent", "somepassword")
        assert res is None
        assert mock_verify.called
        assert mock_verify.call_args[0][1] == auth_service._DUMMY_HASH

def test_case_4_fetch_user_sql_and_cleanup():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = ("hellfish", "$2b$12$hash", "shop", "hellfish")

    with patch("app.services.auth_service.get_db_connection", return_value=mock_conn):
        u = fetch_user("hellfish")
        assert u == {
            "username": "hellfish",
            "password_hash": "$2b$12$hash",
            "role": "shop",
            "shop_id": "hellfish",
        }
        mock_cur.execute.assert_called_once()
        sql, params = mock_cur.execute.call_args[0]
        assert "select username, password_hash, role, shop_id from users where username = %s" in sql.lower()
        assert params == ("hellfish",)
        assert mock_cur.close.called
        assert mock_conn.close.called

def test_case_5_post_auth_login(anon_client):
    user_data = {"username": "admin", "role": "admin", "shop_id": None}

    # 200 OK
    with patch("app.routers.auth.authenticate_user", return_value=user_data):
        res = anon_client.post("/api/auth/login", json={"username": "admin", "password": "goodpassword"})
        assert res.status_code == 200
        data = res.json()
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert data["shop_id"] is None
        token = data["access_token"]
        decoded = decode_access_token(token)
        assert decoded.username == "admin"
        assert decoded.role == "admin"
        assert decoded.shop_id is None

    # 401 Credenciales incorrectas
    with patch("app.routers.auth.authenticate_user", return_value=None):
        res = anon_client.post("/api/auth/login", json={"username": "admin", "password": "badpassword"})
        assert res.status_code == 401
        assert res.json()["detail"] == "Usuario o contraseña incorrectos"
        assert res.headers.get("www-authenticate") == "Bearer"

    # 503 Base caída
    with patch("app.routers.auth.authenticate_user", side_effect=Exception("DB Down")):
        res = anon_client.post("/api/auth/login", json={"username": "admin", "password": "any"})
        assert res.status_code == 503
        assert res.json()["detail"] == "No se pudo iniciar sesión: base de datos no disponible."

    # 422 Body sin password
    res = anon_client.post("/api/auth/login", json={"username": "admin"})
    assert res.status_code == 422

def test_case_6_get_auth_me(anon_client):
    headers = auth_headers(username="hellfish", role="shop", shop_id="hellfish")
    res = anon_client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"username": "hellfish", "role": "shop", "shop_id": "hellfish"}

    res_anon = anon_client.get("/api/auth/me")
    assert res_anon.status_code == 401
    assert res_anon.headers.get("www-authenticate") == "Bearer"

@pytest.mark.parametrize("method,url,body", [
    ("GET", "/api/calendar?shop_id=hellfish", None),
    ("POST", "/api/calendar/simulate", {
        "shop_id": "hellfish",
        "barber_id": 1,
        "barber_name": "Facundo (Yayu)",
        "service_name": "Corte",
        "service_price": 22000,
        "service_duration": 30,
        "date": "2026-06-04",
        "start_time": "10:00",
        "lead_time_hours": 24,
        "client_profile": "matias",
        "client_name": "Matías Giménez",
        "is_self_booked": 1
    }),
    ("GET", "/api/queues", None),
    ("GET", "/api/actions?shop_id=hellfish", None),
    ("POST", "/api/actions", {"appointment_id": 1, "shop_id": "hellfish", "action_type": "whatsapp"}),
])
def test_case_7_unauthenticated_requests_return_401(anon_client, method, url, body):
    if method == "GET":
        res = anon_client.get(url)
    else:
        res = anon_client.post(url, json=body)
    assert res.status_code == 401
    assert res.headers.get("www-authenticate") == "Bearer"
    assert res.json()["detail"] == "No autenticado"

def test_case_8_invalid_tokens_return_401(anon_client):
    # 1. Bearer abc
    res1 = anon_client.get("/api/auth/me", headers={"Authorization": "Bearer abc"})
    assert res1.status_code == 401
    assert res1.json()["detail"] == "Token inválido o vencido"
    assert res1.headers.get("www-authenticate") == "Bearer"

    # 2. Token firmado con otra clave
    wrong_key_token = jwt.encode(
        {"sub": "admin", "role": "admin", "shop_id": None, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "wrong-secret-key-of-at-least-32-chars-long",
        algorithm="HS256",
    )
    res2 = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {wrong_key_token}"})
    assert res2.status_code == 401
    assert res2.json()["detail"] == "Token inválido o vencido"

    # 3. Token vencido
    expired_token = jwt.encode(
        {"sub": "admin", "role": "admin", "shop_id": None, "exp": datetime.now(timezone.utc) - timedelta(minutes=10)},
        config.JWT_SECRET,
        algorithm="HS256",
    )
    res3 = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res3.status_code == 401
    assert res3.json()["detail"] == "Token inválido o vencido"

    # 4. Token rol shop sin shop_id
    shop_without_shop_id = jwt.encode(
        {"sub": "hellfish", "role": "shop", "shop_id": None, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        config.JWT_SECRET,
        algorithm="HS256",
    )
    res4 = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {shop_without_shop_id}"})
    assert res4.status_code == 401
    assert res4.json()["detail"] == "Token inválido o vencido"

def test_case_9_hellfish_token_access_control(anon_client):
    hellfish_headers = auth_headers(username="hellfish", role="shop", shop_id="hellfish")

    with patch("app.routers.calendar.get_calendar_data", return_value={"shop_id": "hellfish", "date": "2026-06-04", "total_appointments": 0, "appointments": []}) as mock_cal:
        # GET /api/calendar?shop_id=hooligans -> 403 y mock_cal NO se llamó
        res_403 = anon_client.get("/api/calendar?shop_id=hooligans", headers=hellfish_headers)
        assert res_403.status_code == 403
        assert res_403.json()["detail"] == "No tenés acceso a este comercio"
        assert not mock_cal.called

        # GET /api/calendar?shop_id=hellfish -> 200
        res_200 = anon_client.get("/api/calendar?shop_id=hellfish", headers=hellfish_headers)
        assert res_200.status_code == 200
        assert mock_cal.called

    sim_response = {
        "id": 999,
        "barber_id": 1,
        "barber_name": "Test",
        "date": "2026-06-04",
        "start_time": "10:00",
        "end_time": "10:30",
        "service_name": "Corte",
        "service_price": 1000.0,
        "service_duration": 30,
        "client_hashed": "abc",
        "is_self_booked": 0,
        "ausentismo_risk": "BAJO",
        "color_code": "#10b981",
    }
    with patch("app.routers.calendar.simulate_appointment_service", return_value=sim_response) as mock_sim:
        payload_hooligans = {
            "shop_id": "hooligans",
            "barber_id": 1,
            "barber_name": "Sebastian Fraga",
            "service_name": "Corte de Pelo",
            "service_price": 18000,
            "service_duration": 30,
            "date": "2026-01-21",
            "start_time": "10:00",
            "lead_time_hours": 24,
            "client_profile": "matias",
            "client_name": "Matías Giménez",
            "is_self_booked": 1,
        }
        res = anon_client.post("/api/calendar/simulate", json=payload_hooligans, headers=hellfish_headers)
        assert res.status_code == 403
        assert not mock_sim.called

    with patch("app.routers.actions.list_actions", return_value=[]) as mock_list_act:
        res = anon_client.get("/api/actions?shop_id=hooligans", headers=hellfish_headers)
        assert res.status_code == 403
        assert not mock_list_act.called

    action_response = {
        "id": 1,
        "appointment_id": 1,
        "shop_id": "hellfish",
        "action_type": "confirm",
        "message": None,
        "created_at": datetime(2026, 11, 7, 12, 0),
    }
    with patch("app.routers.actions.register_action", return_value=action_response) as mock_reg_act, \
         patch("app.routers.actions.DATA_SOURCE", "CSV"):
        res = anon_client.post("/api/actions", json={"appointment_id": 1, "shop_id": "hooligans", "action_type": "whatsapp"}, headers=hellfish_headers)
        assert res.status_code == 403
        assert not mock_reg_act.called

    with patch("app.routers.queues.get_shop_queue_slots", return_value=[]) as mock_queue_slots:
        res = anon_client.get("/api/queues?shop_id=hooligans&date=2026-01-21", headers=hellfish_headers)
        assert res.status_code == 403
        assert not mock_queue_slots.called

    with patch("app.routers.queues.compute_custom_metrics", return_value=[]) as mock_custom:
        res = anon_client.get("/api/queues?lambda_rate=5&mu_rate=2&servers=3&shop_id=hooligans", headers=hellfish_headers)
        assert res.status_code == 403
        assert not mock_custom.called

def test_case_10_queues_no_params_shop_filtering(anon_client):
    mocked_queues = [
        {
            "shop_id": "hellfish",
            "lambda_rate": 2.0,
            "mu_rate": 1.5,
            "servers": 3,
            "metrics": {"utilization": 0.44, "p0": 0.25, "stable": True},
        },
        {
            "shop_id": "hooligans",
            "lambda_rate": 3.0,
            "mu_rate": 2.0,
            "servers": 4,
            "metrics": {"utilization": 0.50, "p0": 0.20, "stable": True},
        },
    ]
    with patch("app.routers.queues.get_queue_metrics_data", return_value=mocked_queues):
        # Token hooligans
        hooligans_headers = auth_headers(username="hooligans", role="shop", shop_id="hooligans")
        res_hooli = anon_client.get("/api/queues", headers=hooligans_headers)
        assert res_hooli.status_code == 200
        items_hooli = res_hooli.json()
        assert len(items_hooli) == 1
        assert items_hooli[0]["shop_id"] == "hooligans"

        # Admin
        admin_headers = auth_headers(username="admin", role="admin", shop_id=None)
        res_admin = anon_client.get("/api/queues", headers=admin_headers)
        assert res_admin.status_code == 200
        items_admin = res_admin.json()
        assert len(items_admin) == 2
        assert {item["shop_id"] for item in items_admin} == {"hellfish", "hooligans"}

def test_case_11_admin_access_both_shops(anon_client):
    admin_headers = auth_headers(username="admin", role="admin", shop_id=None)
    with patch("app.routers.calendar.get_calendar_data", return_value={"shop_id": "hellfish", "date": "2026-06-04", "total_appointments": 0, "appointments": []}):
        res1 = anon_client.get("/api/calendar?shop_id=hooligans", headers=admin_headers)
        assert res1.status_code == 200
        res2 = anon_client.get("/api/calendar?shop_id=hellfish", headers=admin_headers)
        assert res2.status_code == 200

def test_admin_custom_queues_with_date(anon_client):
    admin_headers = auth_headers(username="admin", role="admin", shop_id=None)
    with patch("app.routers.queues.compute_custom_metrics", return_value=[]) as mock_custom:
        res = anon_client.get(
            "/api/queues?lambda_rate=5&mu_rate=2&servers=3&date=2026-01-21",
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert mock_custom.called

def test_case_12_root_endpoint_public(anon_client):
    res = anon_client.get("/")
    assert res.status_code == 200
    assert res.json() == {"message": "Backend running successfully.", "status": "active"}

def test_case_13_create_users_script():
    from data_pipeline.create_users import main

    # 1. Variable faltante -> SystemExit con código 1 y get_db_connection sin llamar
    with patch.dict(os.environ, {"ADMIN_PASSWORD": "adminpassword123", "HELLFISH_PASSWORD": "hellfishpassword123"}, clear=True), \
         patch("data_pipeline.create_users.get_db_connection") as mock_conn:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert not mock_conn.called

    # 2. Contraseña de 7 caracteres -> SystemExit con código 1
    with patch.dict(os.environ, {
        "ADMIN_PASSWORD": "short12",
        "HELLFISH_PASSWORD": "hellfishpassword123",
        "HOOLIGANS_PASSWORD": "hooliganspassword123",
    }, clear=True), patch("data_pipeline.create_users.get_db_connection") as mock_conn:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert not mock_conn.called

    # 3. Las 3 válidas -> upsert 3 veces con hashes bcrypt y un solo commit
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.cursor.return_value = mock_cursor

    valid_env = {
        "ADMIN_PASSWORD": "validAdminPassword123",
        "HELLFISH_PASSWORD": "validHellfishPassword123",
        "HOOLIGANS_PASSWORD": "validHooligansPassword123",
    }
    with patch.dict(os.environ, valid_env, clear=True), \
         patch("data_pipeline.create_users.get_db_connection", return_value=mock_connection), \
         patch("data_pipeline.create_users.apply_grants_if_configured") as mock_grants:
        main()

        mock_grants.assert_called_once_with(mock_cursor)
        assert mock_connection.commit.call_count == 1
        assert mock_cursor.close.called
        assert mock_connection.close.called

        execute_calls = mock_cursor.execute.call_args_list
        assert any("create table if not exists users" in str(c[0][0]).lower() for c in execute_calls)

        upsert_calls = [
            c for c in execute_calls
            if "insert into users" in str(c[0][0]).lower()
        ]
        assert len(upsert_calls) == 3

        usernames_inserted = []
        for call in upsert_calls:
            params = call[0][1]
            uname, phash, role, shop = params
            usernames_inserted.append(uname)
            assert phash.startswith("$2b$")
            assert phash not in valid_env.values()

        assert set(usernames_inserted) == {"admin", "hellfish", "hooligans"}

def test_case_14_init_db_and_reset_demo_never_mention_users():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    with open(os.path.join(root, "data_pipeline", "init_db.py"), "r", encoding="utf-8") as f:
        init_db_content = f.read()
    assert "users" not in init_db_content.lower()

    with open(os.path.join(root, "data_pipeline", "reset_demo.py"), "r", encoding="utf-8") as f:
        reset_demo_content = f.read()
    assert "users" not in reset_demo_content.lower()
