from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import ensure_shop_access, get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.queues import ShopQueueData
from app.services.queue_service import (
    compute_custom_metrics,
    get_queue_metrics_data,
    get_shop_queue_slots,
)

router = APIRouter(prefix="/api/queues", tags=["Queues"])

@router.get("", response_model=List[ShopQueueData])
def get_queue_metrics(
    shop_id: Optional[Literal["hellfish", "hooligans"]] = None,
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    walk_ins: Optional[str] = None,
    lambda_rate: Optional[float] = Query(None, ge=0),
    mu_rate: Optional[float] = Query(None, gt=0),
    servers: Optional[int] = Query(None, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Devuelve los parámetros e indicadores del modelo de líneas de espera M/M/s.

    Soporta tres modos de operación:
    1. Sin parámetros: métricas históricas consolidadas por comercio.
    2. Con lambda_rate, mu_rate y servers: cálculo directo en tiempo real (CP5).
    3. Con shop_id (y opcionalmente date y walk_ins): métricas por franja horaria
       del día a partir de la asistencia esperada de turnos y walk-ins en vivo.
    """
    custom_flags = [lambda_rate is not None, mu_rate is not None, servers is not None]
    if any(custom_flags) and not all(custom_flags):
        raise HTTPException(status_code=422, detail="lambda_rate, mu_rate y servers van juntos")

    if shop_id is not None:
        ensure_shop_access(user, shop_id)

    if all(custom_flags):
        return compute_custom_metrics(lambda_rate, mu_rate, servers, shop_id or "custom")

    if (walk_ins is not None or date is not None) and shop_id is None:
        raise HTTPException(status_code=422, detail="date y walk_ins requieren shop_id")

    if shop_id is not None:
        return get_shop_queue_slots(shop_id, date, walk_ins)

    data = get_queue_metrics_data()
    if user.role == "shop":
        return [item for item in data if item["shop_id"] == user.shop_id]

    return data
