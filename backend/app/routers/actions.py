from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import DATA_SOURCE
from app.dependencies import ensure_shop_access, get_current_user
from app.schemas.actions import PreventiveActionRequest, PreventiveActionResponse
from app.schemas.auth import CurrentUser
from app.services.actions_service import list_actions, register_action
from app.services.privacy_service import fetch_privacy_state, get_appointment_client

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
    if payload.action_type == "whatsapp":
        try:
            client = get_appointment_client(payload.shop_id, payload.appointment_id)
            state = fetch_privacy_state(payload.shop_id).get(client) if client else None
        except Exception as exc:
            raise HTTPException(503, "No se pudo registrar la acción preventiva: base de datos no disponible.") from exc
        if state and (state["erased"] or state["do_not_contact"]):
            raise HTTPException(409, "El cliente pidió no ser contactado (Ley 25.326): no se registró el recordatorio.")
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
