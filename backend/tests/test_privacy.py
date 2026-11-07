from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from app.config import DATA_SOURCE
from app.services.calendar_service import get_calendar_data
from app.services.ml_service import predict_appointment_risk
from app.services.privacy_service import (
    CLIENT_HASH_RE,
    _STATE_CACHE,
    AlreadyErased,
    ClientNotFound,
    InvalidQuery,
    MissingSalt,
    fold_privacy_rows,
    get_appointment_client,
    get_privacy_state_safe,
    hash_phone,
    normalize_phone,
    register_privacy_request,
    search_clients,
)
from app.services.queue_service import _SLOT_BASE_CACHE, clear_slot_cache
from conftest import auth_headers
from data_pipeline.reset_demo import reset_demo
from data_pipeline.utils import hash_sensitive_data


# ---------------------------------------------------------------------------
# 1. normalize_phone
# ---------------------------------------------------------------------------
def test_normalize_phone():
    assert normalize_phone("11 2345-6789") == "1123456789"
    assert normalize_phone("12345") is None
    assert normalize_phone("1234567890123456") is None  # 16 dígitos
    assert normalize_phone("abc") is None
    assert normalize_phone("+54 9 11 2345-6789") == "5491123456789"


# ---------------------------------------------------------------------------
# 2. hash_phone vs data_pipeline.utils.hash_sensitive_data
# ---------------------------------------------------------------------------
def test_hash_phone_matches_pipeline_hash():
    digits = "1123456789"
    salt = "s"
    assert hash_phone(digits, salt) == hash_sensitive_data(digits, salt)


# ---------------------------------------------------------------------------
# 3. fold_privacy_rows
# ---------------------------------------------------------------------------
def test_fold_privacy_rows():
    t1 = datetime(2026, 1, 1, 10, 0)
    t2 = datetime(2026, 1, 2, 10, 0)

    # dnc -> dnc True
    s1 = fold_privacy_rows([("c1", "do_not_contact", t1)])
    assert s1["c1"]["do_not_contact"] is True
    assert s1["c1"]["erased"] is False
    assert s1["c1"]["erased_at"] is None

    # dnc + allow -> False
    s2 = fold_privacy_rows([("c2", "do_not_contact", t1), ("c2", "allow_contact", t2)])
    assert s2["c2"]["do_not_contact"] is False
    assert s2["c2"]["erased"] is False

    # allow + dnc -> True
    s3 = fold_privacy_rows([("c3", "allow_contact", t1), ("c3", "do_not_contact", t2)])
    assert s3["c3"]["do_not_contact"] is True
    assert s3["c3"]["erased"] is False

    # erasure + allow -> erased True y dnc True, erased_at = la de la erasure
    s4 = fold_privacy_rows([("c4", "erasure", t1), ("c4", "allow_contact", t2)])
    assert s4["c4"]["erased"] is True
    assert s4["c4"]["do_not_contact"] is True
    assert s4["c4"]["erased_at"] == t1


# ---------------------------------------------------------------------------
# 4. get_privacy_state_safe
# ---------------------------------------------------------------------------
def test_get_privacy_state_safe_cache_and_fallback():
    _STATE_CACHE.clear()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = [("c1", "do_not_contact", datetime(2026, 1, 1))]

    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn):
        res1 = get_privacy_state_safe("hellfish")
        assert "c1" in res1
        assert res1["c1"]["do_not_contact"] is True

    # Después la conexión falla -> devuelve lo cacheado
    with patch("app.services.privacy_service.get_db_connection", side_effect=Exception("DB down")):
        res2 = get_privacy_state_safe("hellfish")
        assert res2 == res1

        # sin caché -> {}
        res3 = get_privacy_state_safe("hooligans")
        assert res3 == {}


# ---------------------------------------------------------------------------
# 5. search_clients
# ---------------------------------------------------------------------------
def test_search_clients_with_hash():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = []

    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn), \
         patch("app.services.privacy_service.fetch_privacy_state", return_value={}):
        q_type, res = search_clients("hellfish", "0123456789abcdef")
        assert q_type == "client_hashed"
        sql, params = mock_cur.execute.call_args[0]
        assert "a.client_hashed = %s" in sql
        assert params == ("hellfish", "0123456789abcdef")


def test_search_clients_with_phone():
    phone_input = "11 2345-6789"
    digits = "1123456789"
    salt = "secret_salt"
    expected_hash = hash_phone(digits, salt)

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = []

    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn), \
         patch.dict("app.services.privacy_service.SHOP_SALTS", {"hellfish": salt}), \
         patch("app.services.privacy_service.fetch_privacy_state", return_value={}):
        q_type, res = search_clients("hellfish", phone_input)
        assert q_type == "phone"
        sql, params = mock_cur.execute.call_args[0]
        assert digits not in sql
        assert phone_input not in sql
        assert digits not in params
        assert phone_input not in params
        assert expected_hash in params


def test_search_clients_invalid_query_and_missing_salt():
    with pytest.raises(InvalidQuery):
        search_clients("hellfish", "abc")

    with patch.dict("app.services.privacy_service.SHOP_SALTS", {"hellfish": None}):
        with pytest.raises(MissingSalt):
            search_clients("hellfish", "1123456789")


def test_search_clients_erased_and_grouping():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # row: id, start_date, start_time, s.name, b.name, target, client_hashed
    mock_cur.fetchall.return_value = [
        (1, "2026-06-04", "10:00", "Corte", "Facundo", 0, "hash_erased_1111"),
        (2, "2026-06-04", "11:00", "Corte", "Facundo", 1, "hash_erased_1111"),
        (3, "2026-06-04", "12:00", "Afeitado", "Martin", 1, "hash_active_2222"),
        (4, "2026-06-04", "13:00", "Afeitado", "Martin", 0, "hash_active_2222"),
        (5, "2026-06-04", "14:00", "Afeitado", "Martin", 0, "hash_active_2222"),
    ]

    mock_state = {
        "hash_erased_1111": {"do_not_contact": True, "erased": True, "erased_at": datetime(2026, 1, 1)},
        "hash_active_2222": {"do_not_contact": False, "erased": False, "erased_at": None},
    }

    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn), \
         patch("app.services.privacy_service.fetch_privacy_state", return_value=mock_state):
        _, clients = search_clients("hellfish", "1123456789abcdef")
        assert len(clients) == 2

        # hash_active_2222 tiene 3 turnos, hash_erased_1111 tiene 0 (por suprimido) -> ordenados por total_appointments desc
        assert clients[0]["client_hashed"] == "hash_active_2222"
        assert clients[0]["total_appointments"] == 3
        assert clients[0]["no_shows"] == 1
        assert len(clients[0]["appointments"]) == 3

        assert clients[1]["client_hashed"] == "hash_erased_1111"
        assert clients[1]["total_appointments"] == 0
        assert clients[1]["no_shows"] == 0
        assert clients[1]["appointments"] == []
        assert clients[1]["erased"] is True


# ---------------------------------------------------------------------------
# 6. register_privacy_request
# ---------------------------------------------------------------------------
def test_register_privacy_request():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # ClientNotFound
    mock_cur.fetchone.return_value = None
    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn):
        with pytest.raises(ClientNotFound):
            register_privacy_request("hellfish", "0123456789abcdef", "do_not_contact", "admin")

    # AlreadyErased
    mock_cur.fetchone.return_value = (1,)
    mock_state = {"0123456789abcdef": {"erased": True, "do_not_contact": True, "erased_at": datetime(2026, 1, 1)}}
    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn), \
         patch("app.services.privacy_service.fetch_privacy_state", return_value=mock_state):
        with pytest.raises(AlreadyErased):
            register_privacy_request("hellfish", "0123456789abcdef", "do_not_contact", "admin")

    # INSERT con 4 parámetros y commit
    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn), \
         patch("app.services.privacy_service.fetch_privacy_state", return_value={}):
        res = register_privacy_request("hellfish", "0123456789abcdef", "do_not_contact", "admin")
        assert mock_conn.commit.called
        insert_calls = [
            c for c in mock_cur.execute.call_args_list
            if "insert into client_privacy_requests" in c[0][0].lower()
        ]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1] == ("hellfish", "0123456789abcdef", "do_not_contact", "admin")


# ---------------------------------------------------------------------------
# 7. SQL: ningún execute contiene UPDATE, DELETE o INSERT INTO appointments
# ---------------------------------------------------------------------------
def test_privacy_sql_never_touches_appointments():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = []
    mock_cur.fetchone.return_value = (1,)

    with patch("app.services.privacy_service.get_db_connection", return_value=mock_conn), \
         patch.dict("app.services.privacy_service.SHOP_SALTS", {"hellfish": "salt"}), \
         patch("app.services.privacy_service.fetch_privacy_state", return_value={}):
        search_clients("hellfish", "0123456789abcdef")
        search_clients("hellfish", "1123456789")
        register_privacy_request("hellfish", "0123456789abcdef", "do_not_contact", "admin")
        get_appointment_client("hellfish", 1)

    for call_item in mock_cur.execute.call_args_list:
        sql = call_item[0][0].lower()
        assert "update appointments" not in sql
        assert "delete from appointments" not in sql
        assert "insert into appointments" not in sql


# ---------------------------------------------------------------------------
# 8. Endpoints con client autenticado
# ---------------------------------------------------------------------------
def test_endpoints_privacy(client, anon_client):
    hellfish_headers = auth_headers("hellfish", "shop", "hellfish")
    hooligans_headers = auth_headers("hooligans", "shop", "hooligans")

    # Search 200: la respuesta no contiene la consulta
    with patch("app.routers.privacy.search_clients", return_value=("client_hashed", [])):
        res = client.post("/api/privacy/search", json={"shop_id": "hellfish", "query": "0123456789abcdef"})
        assert res.status_code == 200
        data = res.json()
        assert "query" not in data
        assert data["query_type"] == "client_hashed"
        assert data["clients"] == []

    # Search 422: InvalidQuery
    with patch("app.routers.privacy.search_clients", side_effect=InvalidQuery()):
        res = client.post("/api/privacy/search", json={"shop_id": "hellfish", "query": "abc"})
        assert res.status_code == 422
        assert "Ingresá un teléfono" in res.json()["detail"]

    # Search 503: en modo CSV
    with patch("app.routers.privacy.DATA_SOURCE", "CSV"):
        res = client.post("/api/privacy/search", json={"shop_id": "hellfish", "query": "0123456789abcdef"})
        assert res.status_code == 503
        assert res.json()["detail"] == "La gestión de privacidad requiere la base de datos."

    # Search 503: MissingSalt
    with patch("app.routers.privacy.search_clients", side_effect=MissingSalt()):
        res = client.post("/api/privacy/search", json={"shop_id": "hellfish", "query": "1123456789"})
        assert res.status_code == 503
        assert "Falta el salt del comercio" in res.json()["detail"]

    # Requests 201 y clear_slot_cache llamado
    with patch("app.routers.privacy.register_privacy_request", return_value={"client_hashed": "0123456789abcdef", "do_not_contact": True, "erased": False, "erased_at": None}), \
         patch("app.routers.privacy.clear_slot_cache") as mock_clear:
        res = client.post(
            "/api/privacy/requests",
            json={"shop_id": "hellfish", "client_hashed": "0123456789abcdef", "request_type": "do_not_contact"},
        )
        assert res.status_code == 201
        assert res.json()["do_not_contact"] is True
        assert mock_clear.called
        assert mock_clear.call_args[0][0] == "hellfish"

    # Requests 404: ClientNotFound
    with patch("app.routers.privacy.register_privacy_request", side_effect=ClientNotFound()):
        res = client.post(
            "/api/privacy/requests",
            json={"shop_id": "hellfish", "client_hashed": "0123456789abcdef", "request_type": "do_not_contact"},
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "No hay turnos de ese cliente en el comercio."

    # Requests 409: AlreadyErased
    with patch("app.routers.privacy.register_privacy_request", side_effect=AlreadyErased()):
        res = client.post(
            "/api/privacy/requests",
            json={"shop_id": "hellfish", "client_hashed": "0123456789abcdef", "request_type": "do_not_contact"},
        )
        assert res.status_code == 409
        assert res.json()["detail"] == "Los datos de este cliente ya fueron suprimidos."

    # Requests 422 por hash inválido
    res = client.post(
        "/api/privacy/requests",
        json={"shop_id": "hellfish", "client_hashed": "invalid_hash!", "request_type": "do_not_contact"},
    )
    assert res.status_code == 422

    # hellfish sobre hooligans -> 403 en las dos rutas
    res_search_403 = anon_client.post(
        "/api/privacy/search",
        json={"shop_id": "hooligans", "query": "0123456789abcdef"},
        headers=hellfish_headers,
    )
    assert res_search_403.status_code == 403

    res_req_403 = anon_client.post(
        "/api/privacy/requests",
        json={"shop_id": "hooligans", "client_hashed": "0123456789abcdef", "request_type": "do_not_contact"},
        headers=hellfish_headers,
    )
    assert res_req_403.status_code == 403

    # Sin token -> 401 en las dos rutas
    assert anon_client.post("/api/privacy/search", json={"shop_id": "hellfish", "query": "123"}).status_code == 401
    assert anon_client.post("/api/privacy/requests", json={"shop_id": "hellfish", "client_hashed": "0123456789abcdef", "request_type": "erasure"}).status_code == 401


# ---------------------------------------------------------------------------
# 9. Calendar con privacidad y comparación de probabilidades
# ---------------------------------------------------------------------------
def test_calendar_with_privacy():
    import pandas as pd
    from app.config import PROCESSED_FILE

    # Leer all_df real para comparar
    all_df = pd.read_csv(PROCESSED_FILE)
    df_hooligans = all_df[all_df["shop_id"] == "hooligans"].copy()
    app_date = str(df_hooligans["date"].iloc[0])
    target_apps = df_hooligans[df_hooligans["date"] == app_date]

    # Tomamos dos clientes distintos con turnos en esa fecha
    hashes = target_apps["client_hashed"].dropna().unique()
    hash_erased = str(hashes[0])
    hash_dnc = str(hashes[1]) if len(hashes) > 1 else "other_hash_1234"

    mock_state = {
        hash_erased: {"erased": True, "do_not_contact": True, "erased_at": datetime(2026, 1, 1)},
        hash_dnc: {"erased": False, "do_not_contact": True, "erased_at": None},
    }

    with patch("app.services.calendar_service.DATA_SOURCE", "POSTGRES"), \
         patch("app.services.calendar_service.fetch_appointments_from_db", side_effect=Exception("DB fallback")), \
         patch("app.services.calendar_service.get_privacy_state_safe", return_value=mock_state):
        cal = get_calendar_data("hooligans", date=app_date)

    erased_apps = [a for a in cal.appointments if a.client_erased]
    dnc_apps = [a for a in cal.appointments if a.contact_blocked and not a.client_erased]

    assert len(erased_apps) > 0
    for a in erased_apps:
        assert a.client_hashed == ""
        assert a.client_erased is True
        assert a.contact_blocked is True
        assert a.diagnostic == "Datos del cliente suprimidos a su pedido (Ley 25.326): el riesgo se estima sin su historial."

    if len(dnc_apps) > 0:
        for a in dnc_apps:
            assert a.contact_blocked is True
            assert a.client_erased is False
            assert a.client_hashed == hash_dnc

    # Test comparativo de probabilidad: turno suprimido vs predict_appointment_risk sin filas de ese cliente
    first_erased = target_apps[target_apps["client_hashed"] == hash_erased].iloc[0].copy()
    all_df_without_client = all_df.copy()
    all_df_without_client.loc[
        (all_df_without_client["shop_id"].astype(str).str.lower() == "hooligans") &
        (all_df_without_client["client_hashed"] == hash_erased),
        "client_hashed",
    ] = None

    row_erased_input = first_erased.copy()
    row_erased_input["client_hashed"] = None
    _, _, expected_prob = predict_appointment_risk(row_erased_input, all_appointments_df=all_df_without_client)

    matching_cal_app = next(a for a in erased_apps if a.id == int(first_erased["id"]))
    assert matching_cal_app.noshow_probability == pytest.approx(expected_prob, abs=1e-5)


# ---------------------------------------------------------------------------
# 10. Actions con privacidad
# ---------------------------------------------------------------------------
def test_actions_with_privacy(client):
    # whatsapp a un turno con dnc -> 409
    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.routers.actions.get_appointment_client", return_value="hash_dnc_1234"), \
         patch("app.routers.actions.fetch_privacy_state", return_value={"hash_dnc_1234": {"erased": False, "do_not_contact": True}}):
        res_wa_blocked = client.post(
            "/api/actions",
            json={"appointment_id": 100, "shop_id": "hellfish", "action_type": "whatsapp"},
        )
        assert res_wa_blocked.status_code == 409
        assert "El cliente pidió no ser contactado" in res_wa_blocked.json()["detail"]

    # confirm al mismo turno -> 201
    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.routers.actions.get_appointment_client", return_value="hash_dnc_1234"), \
         patch("app.routers.actions.fetch_privacy_state", return_value={"hash_dnc_1234": {"erased": False, "do_not_contact": True}}), \
         patch("app.routers.actions.register_action", return_value={"id": 1, "appointment_id": 100, "shop_id": "hellfish", "action_type": "confirm", "message": None, "created_at": datetime(2026, 1, 1)}):
        res_confirm = client.post(
            "/api/actions",
            json={"appointment_id": 100, "shop_id": "hellfish", "action_type": "confirm"},
        )
        assert res_confirm.status_code == 201

    # whatsapp a un turno simulado (sin fila -> client es None) -> 201
    with patch("app.routers.actions.DATA_SOURCE", "POSTGRES"), \
         patch("app.routers.actions.get_appointment_client", return_value=None), \
         patch("app.routers.actions.fetch_privacy_state", return_value={}), \
         patch("app.routers.actions.register_action", return_value={"id": 2, "appointment_id": 9999, "shop_id": "hellfish", "action_type": "whatsapp", "message": "msg", "created_at": datetime(2026, 1, 1)}):
        res_sim_wa = client.post(
            "/api/actions",
            json={"appointment_id": 9999, "shop_id": "hellfish", "action_type": "whatsapp", "message": "msg"},
        )
        assert res_sim_wa.status_code == 201


# ---------------------------------------------------------------------------
# 11. Simulate sin privacy_consent -> 422
# ---------------------------------------------------------------------------
def test_simulate_without_privacy_consent(client):
    payload = {
        "shop_id": "hooligans",
        "barber_id": 1,
        "barber_name": "Sebastian Fraga",
        "service_name": "Corte Clásico",
        "service_price": 19000.0,
        "service_duration": 45,
        "date": "2026-01-21",
        "start_time": "15:00:00",
        "lead_time_hours": 2.0,
        "client_profile": "fiel",
        "is_self_booked": 0,
        "privacy_consent": False,
    }
    res = client.post("/api/calendar/simulate", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"] == "El turno entrante no trae el consentimiento informado del cliente (Ley 25.326, Art. 5)."


# ---------------------------------------------------------------------------
# 12. clear_slot_cache
# ---------------------------------------------------------------------------
def test_clear_slot_cache():
    _SLOT_BASE_CACHE.clear()
    _SLOT_BASE_CACHE[("hellfish", "2026-06-04")] = {"data": 1}
    _SLOT_BASE_CACHE[("hellfish", "2026-06-05")] = {"data": 2}
    _SLOT_BASE_CACHE[("hooligans", "2026-01-21")] = {"data": 3}

    clear_slot_cache("hellfish")

    assert ("hellfish", "2026-06-04") not in _SLOT_BASE_CACHE
    assert ("hellfish", "2026-06-05") not in _SLOT_BASE_CACHE
    assert ("hooligans", "2026-01-21") in _SLOT_BASE_CACHE


# ---------------------------------------------------------------------------
# 13. reset_demo incluye TRUNCATE de ambas tablas
# ---------------------------------------------------------------------------
def test_reset_demo_truncates_both_tables():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.side_effect = [(5,), (2,)]

    with patch("data_pipeline.reset_demo.get_db_connection", return_value=mock_conn), \
         patch("data_pipeline.reset_demo.apply_grants_if_configured"):
        reset_demo()

    executed_sqls = [c[0][0] for c in mock_cur.execute.call_args_list]
    truncate_calls = [s for s in executed_sqls if "TRUNCATE TABLE" in s]
    assert len(truncate_calls) == 1
    assert "TRUNCATE TABLE preventive_actions, client_privacy_requests RESTART IDENTITY;" in truncate_calls[0]
