from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser, LoginRequest, LoginResponse
from app.services.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    try:
        user = authenticate_user(payload.username, payload.password)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo iniciar sesión: base de datos no disponible.",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        username=user["username"],
        role=user["role"],
        shop_id=user["shop_id"],
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=user["role"],
        shop_id=user["shop_id"],
    )

@router.get("/me", response_model=CurrentUser)
def get_me(user: CurrentUser = Depends(get_current_user)):
    return user
