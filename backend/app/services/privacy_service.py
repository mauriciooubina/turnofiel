import hashlib
import re
from typing import Dict, List, Optional, Tuple

from app.config import SHOP_SALTS
from app.services.db_service import get_db_connection

CLIENT_HASH_RE = re.compile(r"^[0-9a-f]{16}$")
_STATE_CACHE: Dict[str, Dict[str, dict]] = {}


class InvalidQuery(ValueError):
    pass


class MissingSalt(RuntimeError):
    pass


class ClientNotFound(LookupError):
    pass


class AlreadyErased(Exception):
    pass


def normalize_phone(raw: str) -> Optional[str]:
    """Deja solo los dígitos. Devuelve None si quedan menos de 6 o más de 15."""
    if not isinstance(raw, str):
        return None
    digits = "".join(c for c in raw if c.isdigit())
    if 6 <= len(digits) <= 15:
        return digits
    return None


def hash_phone(digits: str, salt: str) -> str:
    """sha256(f"{digits}_{salt}".encode("utf-8")).hexdigest()[:16]
    (idéntico a data_pipeline.utils.hash_sensitive_data para un texto de dígitos)."""
    return hashlib.sha256(f"{digits}_{salt}".encode("utf-8")).hexdigest()[:16]


def fold_privacy_rows(rows) -> Dict[str, dict]:
    """rows: tuplas (client_hashed, request_type, created_at) ordenadas por created_at, id.
    Devuelve {client_hashed: {"do_not_contact": bool, "erased": bool, "erased_at": datetime|None}}.
    erased = hay alguna fila 'erasure' (erased_at = la primera).
    do_not_contact = True si erased, o si la última fila entre 'do_not_contact'/'allow_contact'
    es 'do_not_contact'."""
    state_by_client: Dict[str, dict] = {}
    for row in rows:
        c_hash, req_type, created_at = row[0], row[1], row[2]
        if c_hash not in state_by_client:
            state_by_client[c_hash] = {
                "erased": False,
                "erased_at": None,
                "last_contact_choice": None,
            }
        entry = state_by_client[c_hash]
        if req_type == "erasure":
            if not entry["erased"]:
                entry["erased"] = True
                entry["erased_at"] = created_at
        elif req_type in ("do_not_contact", "allow_contact"):
            entry["last_contact_choice"] = req_type

    res: Dict[str, dict] = {}
    for c_hash, entry in state_by_client.items():
        erased = entry["erased"]
        dnc = erased or (entry["last_contact_choice"] == "do_not_contact")
        res[c_hash] = {
            "do_not_contact": dnc,
            "erased": erased,
            "erased_at": entry["erased_at"],
        }
    return res


def fetch_privacy_state(shop_id: str) -> Dict[str, dict]:
    """SELECT client_hashed, request_type, created_at FROM client_privacy_requests
    WHERE shop_id = %s ORDER BY created_at ASC, id ASC;  -> fold_privacy_rows.
    Guarda el resultado en _STATE_CACHE[shop_id] y lo devuelve. Si falla, propaga la excepción."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT client_hashed, request_type, created_at FROM client_privacy_requests "
                "WHERE shop_id = %s ORDER BY created_at ASC, id ASC;",
                (shop_id,),
            )
            rows = cur.fetchall() or []
            state = fold_privacy_rows(rows)
            _STATE_CACHE[shop_id] = state
            return state
        finally:
            cur.close()
    finally:
        conn.close()


def get_privacy_state_safe(shop_id: str) -> Dict[str, dict]:
    """fetch_privacy_state; si lanza cualquier excepción, devuelve _STATE_CACHE.get(shop_id, {})."""
    try:
        return fetch_privacy_state(shop_id)
    except Exception:
        return _STATE_CACHE.get(shop_id, {})


def search_clients(shop_id: str, query: str) -> Tuple[str, List[dict]]:
    """Devuelve (query_type, clients)."""
    q = query.strip().lower()
    if CLIENT_HASH_RE.match(q):
        query_type = "client_hashed"
        filter_sql = "a.client_hashed = %s"
        params: tuple = (shop_id, q)
    else:
        digits = normalize_phone(query)
        if digits is None:
            raise InvalidQuery()
        salt = SHOP_SALTS.get(shop_id)
        if not salt:
            raise MissingSalt()
        query_type = "phone"
        phone_h = hash_phone(digits, salt)
        filter_sql = (
            "a.client_hashed IN ("
            "SELECT DISTINCT client_hashed FROM appointments "
            "WHERE LOWER(shop_id) = LOWER(%s) AND phone_hashed = %s AND client_hashed IS NOT NULL"
            ")"
        )
        params = (shop_id, shop_id, phone_h)

    sql = f"""SELECT a.id, TO_CHAR(a.start_time, 'YYYY-MM-DD'), TO_CHAR(a.start_time, 'HH24:MI'),
       s.name, b.name, a.target, a.client_hashed
FROM appointments a
LEFT JOIN barbers b ON a.shop_id = b.shop_id AND a.barber_id = b.id
LEFT JOIN services s ON a.shop_id = s.shop_id AND a.service_id = s.id
WHERE LOWER(a.shop_id) = LOWER(%s) AND {filter_sql}
ORDER BY a.start_time ASC, a.id ASC;"""

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
        finally:
            cur.close()
    finally:
        conn.close()

    grouped: Dict[str, List[dict]] = {}
    for r in rows:
        c_h = str(r[6]) if r[6] is not None else ""
        if not c_h:
            continue
        if c_h not in grouped:
            grouped[c_h] = []
        grouped[c_h].append(
            {
                "id": int(r[0]),
                "date": str(r[1]),
                "start_time": str(r[2]),
                "service_name": r[3] if r[3] is not None else None,
                "barber_name": r[4] if r[4] is not None else None,
                "target": int(r[5]) if r[5] is not None else None,
            }
        )

    state_map = fetch_privacy_state(shop_id)
    clients: List[dict] = []
    for c_h, appts in grouped.items():
        st = state_map.get(
            c_h, {"do_not_contact": False, "erased": False, "erased_at": None}
        )
        erased = bool(st.get("erased", False))
        erased_at = st.get("erased_at")
        dnc = bool(st.get("do_not_contact", False))

        if erased:
            total_appointments = 0
            no_shows = 0
            client_appts: List[dict] = []
        else:
            total_appointments = len(appts)
            no_shows = sum(1 for a in appts if a.get("target") == 1)
            client_appts = appts

        clients.append(
            {
                "client_hashed": c_h,
                "total_appointments": total_appointments,
                "no_shows": no_shows,
                "do_not_contact": dnc,
                "erased": erased,
                "erased_at": erased_at,
                "appointments": client_appts,
            }
        )

    clients.sort(key=lambda x: (-x["total_appointments"], x["client_hashed"]))
    return query_type, clients


def register_privacy_request(
    shop_id: str, client_hashed: str, request_type: str, requested_by: str
) -> dict:
    """Devuelve el estado nuevo {client_hashed, do_not_contact, erased, erased_at}."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT 1 FROM appointments WHERE LOWER(shop_id) = LOWER(%s) AND client_hashed = %s LIMIT 1;",
                (shop_id, client_hashed),
            )
            if not cur.fetchone():
                raise ClientNotFound()

            state = fetch_privacy_state(shop_id).get(client_hashed)
            if state and state.get("erased"):
                raise AlreadyErased()

            cur.execute(
                "INSERT INTO client_privacy_requests (shop_id, client_hashed, request_type, requested_by) "
                "VALUES (%s, %s, %s, %s);",
                (shop_id, client_hashed, request_type, requested_by),
            )
            conn.commit()
        finally:
            cur.close()
    finally:
        conn.close()

    new_state = fetch_privacy_state(shop_id).get(
        client_hashed, {"do_not_contact": False, "erased": False, "erased_at": None}
    )
    return {
        "client_hashed": client_hashed,
        "do_not_contact": new_state.get("do_not_contact", False),
        "erased": new_state.get("erased", False),
        "erased_at": new_state.get("erased_at"),
    }


def get_appointment_client(shop_id: str, appointment_id: int) -> Optional[str]:
    """SELECT client_hashed FROM appointments WHERE id = %s AND LOWER(shop_id) = LOWER(%s);
    None si no hay fila o si es NULL (los turnos simulados no están en la base)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT client_hashed FROM appointments WHERE id = %s AND LOWER(shop_id) = LOWER(%s);",
                (appointment_id, shop_id),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return str(row[0])
        finally:
            cur.close()
    finally:
        conn.close()
