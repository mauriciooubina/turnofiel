import os
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PIPELINE_DIR = os.path.join(ROOT, "data_pipeline")
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data_pipeline.db_roles import (
    APP_TABLES,
    INSERT_TABLES,
    SEQUENCES,
    validate_app_role_name,
    ensure_app_role,
    grant_app_privileges,
    apply_grants_if_configured,
)
from data_pipeline.setup_app_role import main as setup_app_role_main


def test_validate_app_role_name():
    # Acepta pfi_app
    validate_app_role_name("pfi_app", "postgres")

    # Rechaza postgres
    with pytest.raises(ValueError):
        validate_app_role_name("postgres", "admin_user")

    # Rechaza el mismo nombre que admin_user
    with pytest.raises(ValueError):
        validate_app_role_name("myadmin", "myadmin")

    # Rechaza "Pfi" (mayúsculas)
    with pytest.raises(ValueError):
        validate_app_role_name("Pfi", "postgres")

    # Rechaza "a-b" (guión)
    with pytest.raises(ValueError):
        validate_app_role_name("a-b", "postgres")

    # Rechaza "" (vacío)
    with pytest.raises(ValueError):
        validate_app_role_name("", "postgres")

    # Rechaza "x; DROP" (inyección / caracteres inválidos)
    with pytest.raises(ValueError):
        validate_app_role_name("x; DROP", "postgres")


def test_ensure_app_role_nonexistent():
    cur = MagicMock()
    cur.fetchone.return_value = None

    res = ensure_app_role(cur, "pfi_app", "secret_pass_12")
    assert res == "created"

    assert cur.execute.call_count == 2
    create_call = cur.execute.call_args_list[1]
    sql_arg, params = create_call[0]
    sql_repr = repr(sql_arg)

    assert "CREATE ROLE" in sql_repr
    assert "Identifier('pfi_app')" in sql_repr
    assert "NOSUPERUSER" in sql_repr
    assert "NOCREATEDB" in sql_repr
    assert "NOCREATEROLE" in sql_repr
    assert "secret_pass_12" not in sql_repr
    assert params == ("secret_pass_12",)


def test_ensure_app_role_existing():
    cur = MagicMock()
    cur.fetchone.return_value = (1,)

    res = ensure_app_role(cur, "pfi_app", "new_secret_pass_12")
    assert res == "updated"

    assert cur.execute.call_count == 2
    alter_call = cur.execute.call_args_list[1]
    sql_arg, params = alter_call[0]
    sql_repr = repr(sql_arg)

    assert "ALTER ROLE" in sql_repr
    assert "Identifier('pfi_app')" in sql_repr
    assert "secret_pass_12" not in sql_repr
    assert params == ("new_secret_pass_12",)


def test_grant_app_privileges_nonexistent_role():
    cur = MagicMock()
    cur.fetchone.return_value = None

    res = grant_app_privileges(cur, "pfi_app")
    assert res is False
    assert cur.execute.call_count == 1


def test_grant_app_privileges_all_tables_present():
    cur = MagicMock()

    def mock_fetchone():
        last_query = cur.execute.call_args[0][0]
        query_repr = repr(last_query)
        if "pg_roles" in query_repr:
            return (1,)
        if "current_database" in query_repr:
            return ("pfi_db",)
        if "to_regclass" in query_repr:
            params = cur.execute.call_args[0][1]
            return (params[0],)
        return None

    cur.fetchone.side_effect = mock_fetchone

    res = grant_app_privileges(cur, "pfi_app")
    assert res is True

    executed_sqls = [repr(c[0][0]) for c in cur.execute.call_args_list]

    # Ningún execute contiene UPDATE, DELETE, TRUNCATE, GRANT ALL ni SUPERUSER
    for sql_repr in executed_sqls:
        lower_repr = sql_repr.lower()
        assert "update" not in lower_repr
        assert "delete" not in lower_repr
        assert "truncate" not in lower_repr
        assert "grant all" not in lower_repr
        assert "superuser" not in lower_repr

    # GRANT SELECT para las 7 tablas
    select_grants = [
        s for s in executed_sqls
        if "GRANT SELECT" in s
    ]
    assert len(select_grants) == len(APP_TABLES) == 7
    for table in APP_TABLES:
        assert any(f"Identifier('{table}')" in s and "Identifier('pfi_app')" in s for s in select_grants)

    # GRANT INSERT solo para preventive_actions
    insert_grants = [
        s for s in executed_sqls
        if "GRANT INSERT" in s
    ]
    assert len(insert_grants) == 1
    assert "Identifier('preventive_actions')" in insert_grants[0]
    assert "Identifier('pfi_app')" in insert_grants[0]

    # GRANT USAGE ON SEQUENCE para preventive_actions_id_seq
    seq_grants = [
        s for s in executed_sqls
        if "GRANT USAGE ON SEQUENCE" in s
    ]
    assert len(seq_grants) == 1
    assert "Identifier('preventive_actions_id_seq')" in seq_grants[0]
    assert "Identifier('pfi_app')" in seq_grants[0]


def test_grant_app_privileges_users_missing():
    cur = MagicMock()

    def mock_fetchone():
        last_query = cur.execute.call_args[0][0]
        query_repr = repr(last_query)
        if "pg_roles" in query_repr:
            return (1,)
        if "current_database" in query_repr:
            return ("pfi_db",)
        if "to_regclass" in query_repr:
            params = cur.execute.call_args[0][1]
            if params and params[0] == "public.users":
                return (None,)
            return (params[0],)
        return None

    cur.fetchone.side_effect = mock_fetchone

    res = grant_app_privileges(cur, "pfi_app")
    assert res is True

    executed_sqls = [repr(c[0][0]) for c in cur.execute.call_args_list]
    for s in executed_sqls:
        if "GRANT SELECT" in s:
            assert "Identifier('users')" not in s


def test_setup_app_role_main_invalid_password():
    # 1. Sin APP_DB_PASS
    with patch.dict(os.environ, {"APP_DB_USER": "pfi_app"}, clear=True), \
         patch("data_pipeline.setup_app_role.get_db_connection") as mock_conn:
        with pytest.raises(SystemExit) as exc:
            setup_app_role_main()
        assert exc.value.code == 1
        assert not mock_conn.called

    # 2. Con 11 caracteres (< 12)
    with patch.dict(os.environ, {"APP_DB_USER": "pfi_app", "APP_DB_PASS": "short11char"}, clear=True), \
         patch("data_pipeline.setup_app_role.get_db_connection") as mock_conn:
        with pytest.raises(SystemExit) as exc:
            setup_app_role_main()
        assert exc.value.code == 1
        assert not mock_conn.called


def test_setup_app_role_main_forbidden_user():
    with patch.dict(os.environ, {"APP_DB_USER": "postgres", "APP_DB_PASS": "valid_pass_123"}, clear=True), \
         patch("data_pipeline.setup_app_role.get_db_connection") as mock_conn:
        with pytest.raises(SystemExit) as exc:
            setup_app_role_main()
        assert exc.value.code == 1
        assert not mock_conn.called


def test_apply_grants_if_configured_nonexistent_role(capsys):
    cur = MagicMock()
    cur.fetchone.return_value = None

    with patch.dict(os.environ, {"APP_DB_USER": "pfi_app", "DB_USER": "postgres"}):
        apply_grants_if_configured(cur)

    captured = capsys.readouterr()
    assert "Aviso: el rol pfi_app no existe todavía; corré data_pipeline/setup_app_role.py." in captured.out
