"""Script para aprovisionar el rol restringido de la aplicación en PostgreSQL."""

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

from init_db import get_db_connection
from db_roles import (
    MIN_APP_PASSWORD_LEN,
    ensure_app_role,
    grant_app_privileges,
    validate_app_role_name,
)


def main() -> None:
    app_user = os.getenv("APP_DB_USER", "pfi_app")
    app_password = os.getenv("APP_DB_PASS")
    admin_user = os.getenv("DB_USER", "postgres")

    if not app_password or len(app_password) < MIN_APP_PASSWORD_LEN:
        print("Error: APP_DB_PASS inválida o faltante (mínimo 12 caracteres).")
        sys.exit(1)

    try:
        validate_app_role_name(app_user, admin_user)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            action = ensure_app_role(cur, app_user, app_password)
            grant_app_privileges(cur, app_user)
            conn.commit()
            print(f"Rol {app_user} {action} y permisos aplicados.")
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
