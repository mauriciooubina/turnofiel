import os
import sys
import pytest
import pandas as pd

try:
    from data_pipeline import init_db
except ImportError:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pipeline_dir = os.path.join(root_dir, "data_pipeline")
    if pipeline_dir not in sys.path:
        sys.path.append(pipeline_dir)
    import init_db

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_schema_declares_foreign_keys():
    sql = init_db.CREATE_TABLES_SQL
    assert "FOREIGN KEY (shop_id, barber_id) REFERENCES barbers (shop_id, id)" in sql
    assert "FOREIGN KEY (shop_id, service_id) REFERENCES services (shop_id, id)" in sql
    assert "REFERENCES appointments" not in sql


def test_seed_barbers():
    barbers = init_db.read_seed_barbers(ROOT)
    assert len(barbers) == 8
    assert ("1", "hooligans", "Sebastian Fraga", "admin", True, None) in barbers
    assert ("3", "hellfish", "Alan", "barber", False, None) in barbers
    assert all(b[5] is None for b in barbers)


def test_seed_services():
    services = init_db.read_seed_services(ROOT)
    assert len(services) == 10
    assert (
        "3",
        "hellfish",
        "Corte + Arreglo de Barba",
        "Corte de Pelo + Arreglo de Barba + (Afeitado a vapor opcional)",
        27000.0,
        60,
    ) in services


def test_seed_has_no_personal_columns():
    df_b = pd.read_csv(os.path.join(ROOT, "data", "seed", "barbers.csv"))
    assert list(df_b.columns) == ["shop_id", "id", "name", "role", "active"]

    df_s = pd.read_csv(os.path.join(ROOT, "data", "seed", "services.csv"))
    assert list(df_s.columns) == ["shop_id", "id", "name", "description", "price", "duration"]


def test_seed_covers_processed_data():
    barbers = init_db.read_seed_barbers(ROOT)
    services = init_db.read_seed_services(ROOT)
    barber_pairs = {(b[1], b[0]) for b in barbers}
    service_pairs = {(s[1], s[0]) for s in services}

    for fname in ["processed_appointments_matrix.csv", "consolidated_blocks.csv"]:
        path = os.path.join(ROOT, "data", "processed", fname)
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            if pd.notna(row.get("barber_id")):
                b_pair = (str(row["shop_id"]), str(int(float(row["barber_id"]))))
                assert b_pair in barber_pairs
            if pd.notna(row.get("service_id")):
                s_pair = (str(row["shop_id"]), str(int(float(row["service_id"]))))
                assert s_pair in service_pairs


def test_missing_seed_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        init_db.read_seed_barbers(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        init_db.read_seed_services(str(tmp_path))


def test_init_db_does_not_read_raw():
    init_db_path = os.path.join(ROOT, "data_pipeline", "init_db.py")
    with open(init_db_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert '"raw"' not in content


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2026-04-14 15:00:00", "15:30:00", "2026-04-14 15:30:00"),
        ("2026-04-14 15:00:00", None, None),
        ("2026-04-14 15:00:00", float("nan"), None),
        (None, "15:30:00", None),
        (float("nan"), "15:30:00", None),
        ("2026-04-14 15:00:00", "abc", None),
        ("abc", "15:30:00", None),
        ("2026-04-14 23:30:00", "00:15:00", "2026-04-15 00:15:00"),
        ("2026-04-14 15:00:00", "", None),
        ("2026-04-14 15:00:00", "   ", None),
        ("", "15:30:00", None),
        ("   ", "15:30:00", None),
    ],
)
def test_build_end_timestamp(start, end, expected):
    assert init_db.build_end_timestamp(start, end) == expected

