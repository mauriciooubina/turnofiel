import os
import json
import math
from typing import Dict, Optional, Tuple
from fastapi import HTTPException
from app.config import QUEUE_METRICS_JSON, DATA_SOURCE
from app.services.db_service import fetch_queue_metrics_from_db
from data_pipeline.queuing_theory import calculate_mms_metrics
from app.services.calendar_service import get_calendar_data

_SLOT_BASE_CACHE: Dict[Tuple[str, str], dict] = {}
OPERATING_HOURS = range(10, 20)
MAX_WALK_INS_PER_SLOT = 20

def _sanitize_metrics(m: dict) -> dict:
    sanitized = {}
    for k, v in m.items():
        if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
            sanitized[k] = None
        else:
            sanitized[k] = v
    return sanitized

def compute_custom_metrics(lambda_rate: float, mu_rate: float, servers: int, shop_id: str = "custom") -> list:
    return [{
        "shop_id": shop_id,
        "lambda_rate": lambda_rate,
        "mu_rate": mu_rate,
        "servers": servers,
        "metrics": _sanitize_metrics(calculate_mms_metrics(lambda_rate, mu_rate, servers))
    }]

def parse_walk_ins(raw: Optional[str]) -> Dict[int, int]:
    if raw is None or raw == "" or raw.strip() == "":
        return {}
    result: Dict[int, int] = {}
    items = raw.split(",")
    for item in items:
        token = item.strip()
        if not token:
            raise HTTPException(
                status_code=422,
                detail="walk_ins inválido: usar el formato hora:cantidad, por ejemplo 12:2,18:1"
            )
        parts = token.split(":")
        if len(parts) != 2:
            raise HTTPException(
                status_code=422,
                detail="walk_ins inválido: usar el formato hora:cantidad, por ejemplo 12:2,18:1"
            )
        try:
            h = int(parts[0].strip())
            w = int(parts[1].strip())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="walk_ins inválido: usar el formato hora:cantidad, por ejemplo 12:2,18:1"
            )
        if not (0 <= h <= 23):
            raise HTTPException(
                status_code=422,
                detail="walk_ins inválido: usar el formato hora:cantidad, por ejemplo 12:2,18:1"
            )
        if w < 0 or w > MAX_WALK_INS_PER_SLOT:
            raise HTTPException(
                status_code=422,
                detail="walk_ins inválido: usar el formato hora:cantidad, por ejemplo 12:2,18:1"
            )
        if h in result:
            raise HTTPException(
                status_code=422,
                detail="walk_ins inválido: usar el formato hora:cantidad, por ejemplo 12:2,18:1"
            )
        result[h] = w
    return result

def _get_slot_base(shop_id: str, date: Optional[str]) -> dict:
    cache_key = (shop_id, date or "")
    if cache_key in _SLOT_BASE_CACHE:
        return _SLOT_BASE_CACHE[cache_key]
    cal = get_calendar_data(shop_id, date)
    hours: Dict[int, dict] = {}
    for a in cal.appointments:
        h = int(a.start_time[:2])
        if h not in hours:
            hours[h] = {"scheduled": 0, "expected_attendance": 0.0}
        hours[h]["scheduled"] += 1
        p = a.noshow_probability if a.noshow_probability is not None else 0.0
        hours[h]["expected_attendance"] += (1.0 - p)
    base = {
        "date": cal.date,
        "hours": hours
    }
    _SLOT_BASE_CACHE[cache_key] = base
    return base

def get_shop_queue_slots(shop_id: str, date: Optional[str] = None, walk_ins: Optional[str] = None) -> list:
    wi = parse_walk_ins(walk_ins)
    base_list = get_queue_metrics_data()
    item = next((dict(x) for x in base_list if x.get("shop_id") == shop_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"No queue metrics for shop: {shop_id}")
    base = _get_slot_base(shop_id, date)
    hours = sorted(set(OPERATING_HOURS) | set(base["hours"]))
    for h in wi:
        if h not in hours:
            raise HTTPException(status_code=422, detail=f"walk_ins: la hora {h} está fuera de las franjas del día")
    slots = []
    for h in hours:
        h_info = base["hours"].get(h, {})
        exp = float(h_info.get("expected_attendance", 0.0))
        sched = int(h_info.get("scheduled", 0))
        w = wi.get(h, 0)
        lam = exp + w
        metrics = _sanitize_metrics(calculate_mms_metrics(lam, item["mu_rate"], item["servers"]))
        slot = {
            "hour": h,
            "label": f"{h:02d}:00–{h+1:02d}:00",
            "scheduled": sched,
            "expected_attendance": exp,
            "walk_ins": w,
            "lambda_rate": lam,
            "metrics": metrics
        }
        slots.append(slot)
    return [{**item, "date": base["date"], "slots": slots}]

def get_queue_metrics_data():
    """Obtiene las métricas de líneas de espera M/M/s desde la base de datos o JSON local."""
    try:
        if DATA_SOURCE == "POSTGRES":
            try:
                return fetch_queue_metrics_from_db()
            except Exception as db_err:
                print(f"[Warning] PostgreSQL connection failed: {db_err}. Falling back to JSON mode.")
        
        if not os.path.exists(QUEUE_METRICS_JSON):
            raise HTTPException(
                status_code=404, 
                detail="Queue metrics JSON not found. Run queuing_theory.py first."
            )
        with open(QUEUE_METRICS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error reading queue metrics ({DATA_SOURCE}): {str(e)}"
        )


