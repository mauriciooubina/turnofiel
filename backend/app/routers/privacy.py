from fastapi import APIRouter, Depends, HTTPException, status

from app.config import DATA_SOURCE
from app.dependencies import ensure_shop_access, get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.privacy import (
    PrivacyRequestCreate,
    PrivacySearchRequest,
    PrivacySearchResponse,
    PrivacyStateResponse,
)
from app.services.privacy_service import (
    AlreadyErased,
    ClientNotFound,
    InvalidQuery,
    MissingSalt,
    register_privacy_request,
    search_clients,
)
from app.services.queue_service import clear_slot_cache

router = APIRouter(prefix="/api/privacy", tags=["Privacy"])


@router.post("/search", response_model=PrivacySearchResponse, status_code=status.HTTP_200_OK)
def search_privacy_endpoint(
    payload: PrivacySearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    ensure_shop_access(user, payload.shop_id)
    if DATA_SOURCE != "POSTGRES":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La gestión de privacidad requiere la base de datos.",
        )
    try:
        query_type, clients = search_clients(payload.shop_id, payload.query)
        return PrivacySearchResponse(
            shop_id=payload.shop_id,
            query_type=query_type,
            clients=clients,
        )
    except InvalidQuery as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ingresá un teléfono (solo números, de 6 a 15 dígitos) o el identificador de cliente de 16 caracteres.",
        ) from exc
    except MissingSalt as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falta el salt del comercio en el servidor: no se puede buscar por teléfono.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La gestión de privacidad requiere la base de datos.",
        ) from exc


@router.post("/requests", response_model=PrivacyStateResponse, status_code=status.HTTP_201_CREATED)
def create_privacy_request_endpoint(
    payload: PrivacyRequestCreate,
    user: CurrentUser = Depends(get_current_user),
):
    ensure_shop_access(user, payload.shop_id)
    if DATA_SOURCE != "POSTGRES":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La gestión de privacidad requiere la base de datos.",
        )
    try:
        res = register_privacy_request(
            shop_id=payload.shop_id,
            client_hashed=payload.client_hashed,
            request_type=payload.request_type,
            requested_by=user.username,
        )
        clear_slot_cache(payload.shop_id)
        return res
    except ClientNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay turnos de ese cliente en el comercio.",
        ) from exc
    except AlreadyErased as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Los datos de este cliente ya fueron suprimidos.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La gestión de privacidad requiere la base de datos.",
        ) from exc
