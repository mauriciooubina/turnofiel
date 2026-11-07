"""Reset de la demo: vacía preventive_actions y client_privacy_requests sin tocar los turnos históricos (appointments)."""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from init_db import get_db_connection
from db_roles import apply_grants_if_configured

CREATE_ACTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS preventive_actions (
    id SERIAL PRIMARY KEY,
    appointment_id INT NOT NULL,
    shop_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('whatsapp', 'confirm')),
    message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_PRIVACY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS client_privacy_requests (
    id SERIAL PRIMARY KEY,
    shop_id VARCHAR(50) NOT NULL,
    client_hashed VARCHAR(64) NOT NULL,
    request_type VARCHAR(20) NOT NULL CHECK (request_type IN ('do_not_contact', 'allow_contact', 'erasure')),
    requested_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

def reset_demo():
    """Elimina las acciones preventivas y pedidos de privacidad registrados y reinicia los contadores de id."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(CREATE_ACTIONS_TABLE_SQL)
            cur.execute(CREATE_PRIVACY_TABLE_SQL)
            cur.execute("SELECT COUNT(*) FROM preventive_actions;")
            n_acciones = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM client_privacy_requests;")
            n_privacidad = cur.fetchone()[0]
            cur.execute("TRUNCATE TABLE preventive_actions, client_privacy_requests RESTART IDENTITY;")
            apply_grants_if_configured(cur)
            conn.commit()
            print(f"Reset de la demo: {n_acciones} acciones preventivas y {n_privacidad} pedidos de privacidad eliminados. Los turnos históricos (appointments) no se modificaron.")
        finally:
            cur.close()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_demo()
