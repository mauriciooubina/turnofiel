from typing import Any, Dict, List
from app.schemas.actions import PreventiveActionRequest
from app.services.db_service import get_db_connection

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

def register_action(req: PreventiveActionRequest) -> dict:
    """Registra una acción preventiva en la base de datos."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(CREATE_ACTIONS_TABLE_SQL)
            insert_sql = (
                "INSERT INTO preventive_actions (appointment_id, shop_id, action_type, message) "
                "VALUES (%s, %s, %s, %s) "
                "RETURNING id, appointment_id, shop_id, action_type, message, created_at;"
            )
            cur.execute(insert_sql, (req.appointment_id, req.shop_id, req.action_type, req.message))
            row = cur.fetchone()
            conn.commit()
            return {
                "id": row[0],
                "appointment_id": row[1],
                "shop_id": row[2],
                "action_type": row[3],
                "message": row[4],
                "created_at": row[5],
            }
        finally:
            cur.close()
    finally:
        conn.close()

def list_actions(shop_id: str) -> list[dict]:
    """Obtiene el historial cronológico de acciones preventivas para un comercio."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(CREATE_ACTIONS_TABLE_SQL)
            conn.commit()
            select_sql = (
                "SELECT id, appointment_id, shop_id, action_type, message, created_at "
                "FROM preventive_actions "
                "WHERE shop_id = %s "
                "ORDER BY created_at ASC, id ASC;"
            )
            cur.execute(select_sql, (shop_id,))
            rows = cur.fetchall() or []
            return [
                {
                    "id": r[0],
                    "appointment_id": r[1],
                    "shop_id": r[2],
                    "action_type": r[3],
                    "message": r[4],
                    "created_at": r[5],
                }
                for r in rows
            ]
        finally:
            cur.close()
    finally:
        conn.close()
