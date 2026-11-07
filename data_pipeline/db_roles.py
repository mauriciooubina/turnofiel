"""Gestión del rol restringido de PostgreSQL y asignación de permisos mínimos."""

import os
import re
from psycopg2 import sql

APP_TABLES = (
    "appointments",
    "barbers",
    "services",
    "consolidated_blocks",
    "queue_metrics",
    "preventive_actions",
    "users",
)
INSERT_TABLES = ("preventive_actions",)
SEQUENCES = ("preventive_actions_id_seq",)
FORBIDDEN_ROLE_NAMES = ("postgres",)
ROLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
MIN_APP_PASSWORD_LEN = 12


def validate_app_role_name(app_user: str, admin_user: str) -> None:
    """ValueError si app_user no cumple ROLE_NAME_RE, si está en FORBIDDEN_ROLE_NAMES
    o si es igual a admin_user (así nunca se le revocan permisos al admin)."""
    if not isinstance(app_user, str) or not ROLE_NAME_RE.match(app_user):
        raise ValueError(f"Nombre de rol inválido: {app_user!r}")
    if app_user in FORBIDDEN_ROLE_NAMES:
        raise ValueError(f"El rol {app_user!r} está en FORBIDDEN_ROLE_NAMES")
    if app_user == admin_user:
        raise ValueError(f"El rol {app_user!r} no puede ser igual al usuario administrador")


def ensure_app_role(cur, app_user: str, app_password: str) -> str:
    """Crea el rol si no existe o le actualiza la contraseña si existe.
    Devuelve 'created' o 'updated'. Siempre deja NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION LOGIN."""
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
    exists = cur.fetchone() is not None

    if not exists:
        create_sql = sql.SQL(
            "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %s"
        ).format(sql.Identifier(app_user))
        cur.execute(create_sql, (app_password,))
        return "created"
    else:
        alter_sql = sql.SQL(
            "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %s"
        ).format(sql.Identifier(app_user))
        cur.execute(alter_sql, (app_password,))
        return "updated"


def grant_app_privileges(cur, app_user: str) -> bool:
    """Deja al rol exactamente con los permisos mínimos. Devuelve False (sin ejecutar
    nada más) si el rol no existe; True si los aplicó. Es idempotente."""
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
    if not cur.fetchone():
        return False

    # 2. REVOKE CREATE ON SCHEMA public FROM PUBLIC
    cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))

    # 3. REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {app}
    cur.execute(
        sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(
            sql.Identifier(app_user)
        )
    )

    # 4. REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {app}
    cur.execute(
        sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(
            sql.Identifier(app_user)
        )
    )

    # 5. GRANT CONNECT ON DATABASE {db} TO {app}
    cur.execute("SELECT current_database()")
    row = cur.fetchone()
    db_name = row[0]
    cur.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(db_name), sql.Identifier(app_user)
        )
    )

    # 6. GRANT USAGE ON SCHEMA public TO {app}
    cur.execute(
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
            sql.Identifier(app_user)
        )
    )

    # 7. GRANT SELECT ON {tabla} TO {app} para cada tabla existente
    for t in APP_TABLES:
        cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
        res = cur.fetchone()
        if res and res[0] is not None:
            cur.execute(
                sql.SQL("GRANT SELECT ON {} TO {}").format(
                    sql.Identifier(t), sql.Identifier(app_user)
                )
            )

    # 8. GRANT INSERT ON {tabla} TO {app} para cada tabla de inserción existente
    for t in INSERT_TABLES:
        cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
        res = cur.fetchone()
        if res and res[0] is not None:
            cur.execute(
                sql.SQL("GRANT INSERT ON {} TO {}").format(
                    sql.Identifier(t), sql.Identifier(app_user)
                )
            )

    # 9. GRANT USAGE ON SEQUENCE {seq} TO {app} para cada secuencia existente
    for seq in SEQUENCES:
        cur.execute("SELECT to_regclass(%s)", (f"public.{seq}",))
        res = cur.fetchone()
        if res and res[0] is not None:
            cur.execute(
                sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(
                    sql.Identifier(seq), sql.Identifier(app_user)
                )
            )

    return True


def apply_grants_if_configured(cur) -> None:
    """Para el final de init_db / create_users / reset_demo. Lee APP_DB_USER (default
    'pfi_app') y DB_USER (default 'postgres'); valida el nombre; llama a grant_app_privileges
    e imprime una de estas dos líneas:
    'Permisos de <app_user> aplicados.' o
    'Aviso: el rol <app_user> no existe todavía; corré data_pipeline/setup_app_role.py.'
    Si el nombre es inválido, imprime 'Aviso: APP_DB_USER inválido; no se aplicaron permisos.' y no ejecuta nada."""
    app_user = os.getenv("APP_DB_USER", "pfi_app")
    admin_user = os.getenv("DB_USER", "postgres")

    try:
        validate_app_role_name(app_user, admin_user)
    except ValueError:
        print("Aviso: APP_DB_USER inválido; no se aplicaron permisos.")
        return

    applied = grant_app_privileges(cur, app_user)
    if applied:
        print(f"Permisos de {app_user} aplicados.")
    else:
        print(f"Aviso: el rol {app_user} no existe todavía; corré data_pipeline/setup_app_role.py.")

