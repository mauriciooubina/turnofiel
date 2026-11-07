"""Crea la tabla users e inserta o actualiza los 3 usuarios con contraseñas hasheadas."""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.services.auth_service import CREATE_USERS_TABLE_SQL, hash_password
from init_db import get_db_connection
from db_roles import apply_grants_if_configured

USER_DEFINITIONS = [
    ("admin", "ADMIN_PASSWORD", "admin", None),
    ("hellfish", "HELLFISH_PASSWORD", "shop", "hellfish"),
    ("hooligans", "HOOLIGANS_PASSWORD", "shop", "hooligans"),
]

def main():
    passwords = {}
    for username, var_name, role, shop_id in USER_DEFINITIONS:
        val = os.getenv(var_name)
        if not val or len(val) < 8 or len(val.encode("utf-8")) > 72:
            print(f"Error: variable {var_name} inválida o faltante (mínimo 8 caracteres, máximo 72 bytes).")
            sys.exit(1)
        passwords[username] = val

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(CREATE_USERS_TABLE_SQL)
            upsert_sql = (
                "INSERT INTO users (username, password_hash, role, shop_id) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (username) DO UPDATE SET "
                "password_hash = EXCLUDED.password_hash, "
                "role = EXCLUDED.role, "
                "shop_id = EXCLUDED.shop_id;"
            )
            for username, var_name, role, shop_id in USER_DEFINITIONS:
                pwd_hash = hash_password(passwords[username])
                cur.execute(upsert_sql, (username, pwd_hash, role, shop_id))
            apply_grants_if_configured(cur)
            conn.commit()
            print("Usuarios creados o actualizados: admin, hellfish, hooligans")
        finally:
            cur.close()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
