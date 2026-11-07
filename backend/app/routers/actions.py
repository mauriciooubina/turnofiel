from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import DATA_SOURCE
from app.dependencies import ensure_shop_access, get_current_user
from app.schemas.actions import PreventiveActionRequest, PreventiveActionResponse
from app.schemas.auth import CurrentUser
from app.services.actions_service import list_actions, register_action

router = APIRouter(prefix="/api/actions", tags=["Actions"])

@router.post("", response_model=PreventiveActionResponse, status_code=status.HTTP_201_CREATED)
def post_action(
    payload: PreventiveActionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    CU2: Registra la acción preventiva ejecutada sobre un turno en la base de datos.
    """
    ensure_shop_access(user, payload.shop_id)
    if DATA_SOURCE != "POSTGRES":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo registrar la acción preventiva: base de datos no disponible.",
        )
    try:
        return register_action(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo registrar la acción preventiva: base de datos no disponible.",
        ) from exc

@router.get("", response_model=List[PreventiveActionResponse])
def get_actions(
    shop_id: Literal["hellfish", "hooligans"] = Query(..., description="ID del comercio"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    CU2: Obtiene el registro histórico de acciones preventivas para un comercio.
    """
    ensure_shop_access(user, shop_id)
    if DATA_SOURCE != "POSTGRES":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo consultar el historial de acciones preventivas: base de datos no disponible.",
        )
    try:
        return list_actions(shop_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo consultar el historial de acciones preventivas: base de datos no disponible.",
        ) from exc
