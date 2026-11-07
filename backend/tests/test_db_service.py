import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from app.services.db_service import (
    get_db_connection,
    fetch_appointments_from_db,
    fetch_queue_metrics_from_db,
    fetch_barbers_by_shop_from_db
)
from app.services.calendar_service import get_calendar_data

def test_get_db_connection_live():
    try:
        conn = get_db_connection()
        assert conn is not None
        conn.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL not accessible directly from test environment: {e}")

def test_fetch_appointments_from_db_live_or_mock():
    try:
        df = fetch_appointments_from_db(shop_id="hellfish")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "shop_id" in df.columns
    except Exception:
        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            with patch("pandas.read_sql_query") as mock_read_sql:
                mock_read_sql.return_value = pd.DataFrame([{
                    "id": 1,
                    "shop_id": "hellfish",
                    "barber_id": 1,
                    "barber_name": "Test Barber",
                    "barber_active": True,
                    "date": "2026-03-24",
                    "start_time": "10:00",
                    "end_time": "10:30",
                    "service_name": "Corte",
                    "service_price": 5000.0,
                    "duration": 30,
                    "client_hashed": "client123",
                    "is_self_booked": 1,
                    "lead_time_hours": 24.0,
                    "target": 0
                }])
                df = fetch_appointments_from_db(shop_id="hellfish", date="2026-03-24")
                assert not df.empty
                assert df.iloc[0]["shop_id"] == "hellfish"

def test_fetch_queue_metrics_from_db_live_or_mock():
    try:
        metrics = fetch_queue_metrics_from_db()
        assert isinstance(metrics, list)
        assert len(metrics) > 0
    except Exception:
        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            with patch("pandas.read_sql_query") as mock_read_sql:
                mock_read_sql.return_value = pd.DataFrame([{
                    "shop_id": "hellfish",
                    "lambda_val": 4.5,
                    "mu_val": 2.0,
                    "servers_s": 3,
                    "rho": 0.75,
                    "p0": 0.05,
                    "lq": 0.8,
                    "wq": 0.18,
                    "l_val": 3.05,
                    "w_val": 0.68,
                    "stable": True
                }])
                metrics = fetch_queue_metrics_from_db()
                assert isinstance(metrics, list)
                assert metrics[0]["shop_id"] == "hellfish"
                assert metrics[0]["metrics"]["stable"] is True

def test_fetch_barbers_by_shop_from_db_groups_by_active():
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        with patch("pandas.read_sql_query") as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame([
                {"shop_id": "hellfish", "id": 1, "name": "Facundo (Yayu)", "active": True},
                {"shop_id": "hellfish", "id": 3, "name": "Alan", "active": False},
                {"shop_id": "hooligans", "id": 4, "name": "Valen", "active": False},
                {"shop_id": "hooligans", "id": 5, "name": "Valentino", "active": True},
            ])
            result = fetch_barbers_by_shop_from_db()
            expected = {
                "hellfish": {
                    "active": ["Facundo (Yayu)"],
                    "inactive": ["Alan"]
                },
                "hooligans": {
                    "active": ["Valentino"],
                    "inactive": ["Valen"]
                }
            }
            assert result == expected

def test_fetch_queue_metrics_survives_barbers_error():
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        with patch("pandas.read_sql_query") as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame([{
                "shop_id": "hellfish",
                "lambda_val": 4.5,
                "mu_val": 2.0,
                "servers_s": 3,
                "rho": 0.75,
                "p0": 0.05,
                "lq": 0.8,
                "wq": 0.18,
                "l_val": 3.05,
                "w_val": 0.68,
                "stable": True
            }])
            with patch("app.services.db_service.fetch_barbers_by_shop_from_db", side_effect=Exception("x")):
                metrics = fetch_queue_metrics_from_db()
                assert isinstance(metrics, list)
                assert len(metrics) > 0
                assert metrics[0].get("active_barbers") is None


def test_fetch_appointments_query_includes_model_features():
    with patch("app.services.db_service.get_db_connection"), \
         patch("app.services.db_service.pd.read_sql_query", return_value=pd.DataFrame()) as mock_read_sql:
        fetch_appointments_from_db(shop_id="hellfish", date="2026-06-04")
        assert mock_read_sql.called
        query = mock_read_sql.call_args[0][0]
        assert "a.day_of_week" in query
        assert "a.hour_of_day" in query
        assert "a.month" in query
        assert "AS appointment_start" in query
        assert "s.price AS service_price" in query
        assert "a.price AS price" in query
        assert "a.price AS service_price" not in query


def test_postgres_and_csv_modes_give_same_risk_levels():
    try:
        fetch_appointments_from_db(shop_id="hooligans", date="2026-01-21")
    except Exception:
        pytest.skip("PostgreSQL no disponible")

    cases = [
        ("hooligans", "2026-01-21"),
        ("hellfish", "2026-06-04"),
    ]
    for shop, date in cases:
        with patch("app.services.calendar_service.DATA_SOURCE", "POSTGRES"):
            res_pg = get_calendar_data(shop, date)
        with patch("app.services.calendar_service.DATA_SOURCE", "CSV"):
            res_csv = get_calendar_data(shop, date)

        assert res_pg.total_appointments == res_csv.total_appointments
        risks_pg = sorted([a.ausentismo_risk for a in res_pg.appointments])
        risks_csv = sorted([a.ausentismo_risk for a in res_csv.appointments])
        assert risks_pg == risks_csv

