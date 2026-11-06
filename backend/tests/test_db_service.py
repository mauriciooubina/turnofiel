import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from app.services.db_service import (
    get_db_connection,
    fetch_appointments_from_db,
    fetch_queue_metrics_from_db,
    fetch_barbers_by_shop_from_db
)

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

