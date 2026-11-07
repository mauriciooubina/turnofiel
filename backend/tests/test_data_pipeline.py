import os
import sys
import pytest
import numpy as np
import pandas as pd

try:
    from data_pipeline import utils, train_models
except ImportError:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pipeline_dir = os.path.join(root_dir, "data_pipeline")
    if pipeline_dir not in sys.path:
        sys.path.append(pipeline_dir)
    import utils
    import train_models


# ---------------------------------------------------------------------------
# Tests de data_pipeline/utils.py
# ---------------------------------------------------------------------------

def test_hash_sensitive_data():
    val = "1144556677"
    salt_a = "salt_alpha"
    salt_b = "salt_beta"

    # mismo valor y salt → mismo hash
    h1 = utils.hash_sensitive_data(val, salt_a)
    h2 = utils.hash_sensitive_data(val, salt_a)
    assert h1 == h2

    # salt distinto → hash distinto
    h3 = utils.hash_sensitive_data(val, salt_b)
    assert h1 != h3

    # largo 16 y solo hex
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)

    # espacios alrededor no cambian el hash
    h_spaces = utils.hash_sensitive_data(f"  {val}  ", salt_a)
    assert h_spaces == h1

    # None, "", "nan", "NULL", "None" → NaN
    for invalid in [None, "", "   ", "nan", "NaN", "NULL", "None", "null"]:
        assert pd.isna(utils.hash_sensitive_data(invalid, salt_a))


def test_get_crypto_salt(monkeypatch):
    # Con la variable de entorno seteada → devuelve el salt
    monkeypatch.setenv("HELLFISH_SALT", "secret_salt_hellfish")
    assert utils.get_crypto_salt("hellfish") == "secret_salt_hellfish"
    assert utils.get_crypto_salt("HELLFISH") == "secret_salt_hellfish"

    # Sin la variable de entorno → RuntimeError
    monkeypatch.delenv("HELLFISH_SALT", raising=False)
    with pytest.raises(RuntimeError):
        utils.get_crypto_salt("hellfish")


def test_safe_parse_datetime():
    # fecha + hora válidas → Timestamp correcto
    d_series = pd.Series(["2026-05-10", "2026-11-20"])
    t_series = pd.Series(["14:30:00", "09:15:00"])
    parsed = utils.safe_parse_datetime(d_series, t_series)
    assert parsed.iloc[0] == pd.Timestamp("2026-05-10 14:30:00")
    assert parsed.iloc[1] == pd.Timestamp("2026-11-20 09:15:00")

    # "nan" / "None" / basura → NaT
    bad_d = pd.Series(["nan", "None", "NULL", "texto_invalido"])
    bad_t = pd.Series(["10:00:00", "nan", "None", "horario_invalido"])
    parsed_bad = utils.safe_parse_datetime(bad_d, bad_t)
    assert all(pd.isna(x) for x in parsed_bad)

    # sin time_series
    d_only = pd.Series(["2026-05-10", "invalido"])
    parsed_single = utils.safe_parse_datetime(d_only)
    assert parsed_single.iloc[0] == pd.Timestamp("2026-05-10")
    assert pd.isna(parsed_single.iloc[1])


def test_make_tz_naive():
    # serie con zona horaria → dt.tz is None
    tz_series = pd.Series(pd.date_range("2026-01-01", periods=3, tz="America/Argentina/Buenos_Aires"))
    naive = utils.make_tz_naive(tz_series)
    assert naive.dt.tz is None

    # serie de strings → datetime naive
    str_series = pd.Series(["2026-01-01 10:00:00", "2026-01-02 11:00:00"])
    naive_str = utils.make_tz_naive(str_series)
    assert pd.api.types.is_datetime64_any_dtype(naive_str)
    assert naive_str.dt.tz is None


# ---------------------------------------------------------------------------
# Tests de data_pipeline/train_models.py
# ---------------------------------------------------------------------------

def test_compute_channel_lead_time_medians():
    df_sample = pd.DataFrame([
        {"lead_time_hours": -10.0, "is_self_booked": 0},
        {"lead_time_hours": 10.0, "is_self_booked": 0},
        {"lead_time_hours": 20.0, "is_self_booked": 0},
        {"lead_time_hours": -5.0, "is_self_booked": 1},
        {"lead_time_hours": 30.0, "is_self_booked": 1},
        {"lead_time_hours": 50.0, "is_self_booked": 1},
    ])
    # Mediana personal (>= 0): [10.0, 20.0] → 15.0
    # Mediana autogestión (>= 0): [30.0, 50.0] → 40.0
    med_0, med_1 = train_models.compute_channel_lead_time_medians(df_sample)
    assert med_0 == 15.0
    assert med_1 == 40.0


def test_load_and_preprocess_data(tmp_path):
    rows = [
        # Historial de client_hist: asiste (target=0), falta (target=1), asiste (target=0)
        {
            "appointment_start": "2026-01-01 10:00:00",
            "client_hashed": "client_hist",
            "target": 0,
            "is_self_booked": 0,
            "lead_time_hours": 10.0,
            "service_price": 15000.0,
            "price": 8000.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 3,
            "month": 1,
            "barber_id": "1",
        },
        {
            "appointment_start": "2026-01-02 10:00:00",
            "client_hashed": "client_hist",
            "target": 1,
            "is_self_booked": 0,
            "lead_time_hours": 20.0,
            "service_price": np.nan,
            "price": 8500.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 4,
            "month": 1,
            "barber_id": "1",
        },
        {
            "appointment_start": "2026-01-03 10:00:00",
            "client_hashed": "client_hist",
            "target": 0,
            "is_self_booked": 1,
            "lead_time_hours": 30.0,
            "service_price": np.nan,
            "price": np.nan,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 5,
            "month": 1,
            "barber_id": "1",
        },
        # Registros adicionales para fijar medianas y probar imputaciones
        {
            "appointment_start": "2026-01-04 10:00:00",
            "client_hashed": "client_other_1",
            "target": 0,
            "is_self_booked": 1,
            "lead_time_hours": 50.0,
            "service_price": 10000.0,
            "price": 10000.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 6,
            "month": 1,
            "barber_id": "1",
        },
        # Antelación negativa del personal → imputa mediana personal (15.0)
        {
            "appointment_start": "2026-01-05 10:00:00",
            "client_hashed": "client_other_2",
            "target": 0,
            "is_self_booked": 0,
            "lead_time_hours": -5.0,
            "service_price": 10000.0,
            "price": 10000.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 0,
            "month": 1,
            "barber_id": "1",
        },
        # Antelación negativa de autogestión → imputa mediana autogestión (50.0)
        {
            "appointment_start": "2026-01-06 10:00:00",
            "client_hashed": "client_other_3",
            "target": 0,
            "is_self_booked": 1,
            "lead_time_hours": -10.0,
            "service_price": 10000.0,
            "price": 10000.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 1,
            "month": 1,
            "barber_id": "1",
        },
        # Antelación NaN → imputa mediana autogestión (50.0)
        {
            "appointment_start": "2026-01-07 10:00:00",
            "client_hashed": "client_other_4",
            "target": 0,
            "is_self_booked": 1,
            "lead_time_hours": np.nan,
            "service_price": 10000.0,
            "price": 10000.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 2,
            "month": 1,
            "barber_id": "1",
        },
        # Antelación extrema 1000 → recorta a 720.0
        {
            "appointment_start": "2026-01-08 10:00:00",
            "client_hashed": "client_other_5",
            "target": 0,
            "is_self_booked": 1,
            "lead_time_hours": 1000.0,
            "service_price": 10000.0,
            "price": 10000.0,
            "duration": 30,
            "hour_of_day": 10,
            "shop_id": "hellfish",
            "day_of_week": 3,
            "month": 1,
            "barber_id": "1",
        },
    ]

    csv_file = tmp_path / "test_train_data.csv"
    pd.DataFrame(rows).to_csv(csv_file, index=False)

    X, y, features_num, features_cat = train_models.load_and_preprocess_data(str(csv_file))

    # Devuelve 13 columnas y y con el mismo largo
    assert len(X.columns) == 13
    assert len(y) == len(X)
    assert len(X) == 8

    # Historial acumulado sin fuga para client_hist (filas 0, 1, 2)
    hist_mask = (X['barber_id'] == "1") & (X.index.isin([0, 1, 2]))
    hist_rows = X.iloc[[0, 1, 2]]
    assert list(hist_rows['client_past_apps']) == [0, 1, 2]
    assert list(hist_rows['client_past_noshows']) == [0, 0, 1]
    assert list(hist_rows['client_is_new']) == [1, 0, 0]

    # Precios de catálogo
    assert X.iloc[0]['catalog_price'] == 15000.0  # service_price presente
    assert X.iloc[1]['catalog_price'] == 8500.0   # service_price NaN → toma price
    assert X.iloc[2]['catalog_price'] == 10000.0  # ambos faltan → default 10000

    # Imputaciones de clean_lead_time
    assert X.iloc[4]['clean_lead_time'] == 15.0   # negativa personal → med_0
    assert X.iloc[5]['clean_lead_time'] == 50.0   # negativa autogestión → med_1
    assert X.iloc[6]['clean_lead_time'] == 50.0   # NaN → med_1
    assert X.iloc[7]['clean_lead_time'] == 720.0  # 1000 → capped a 720
