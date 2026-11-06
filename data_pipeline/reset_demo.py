"""Reset de la demo: vacía preventive_actions sin tocar los turnos históricos (appointments)."""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from init_db import get_db_connection

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

def reset_demo():
    """Elimina las acciones preventivas registradas y reinicia el contador de id."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(CREATE_ACTIONS_TABLE_SQL)
            cur.execute("SELECT COUNT(*) FROM preventive_actions;")
            count = cur.fetchone()[0]
            cur.execute("TRUNCATE TABLE preventive_actions RESTART IDENTITY;")
            conn.commit()
            print(f"Reset de la demo: {count} acciones preventivas eliminadas. Los turnos históricos (appointments) no se modificaron.")
        finally:
            cur.close()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_demo()
