from fastapi import APIRouter, Depends, Query
from app.dependencies import ensure_shop_access, get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.calendar import CalendarResponse, AppointmentResponse, SimulateAppointmentRequest
from app.services.calendar_service import get_calendar_data, simulate_appointment_service

router = APIRouter(prefix="/api/calendar", tags=["Calendar"])

@router.get("", response_model=CalendarResponse)
def get_calendar(
    shop_id: str = Query(..., description="ID del comercio: 'hellfish' o 'hooligans'"),
    date: str = Query(None, description="Fecha en formato YYYY-MM-DD. Si no se especifica, toma la primera fecha disponible."),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Devuelve los turnos para un comercio y fecha, evaluando el riesgo de ausentismo en tiempo real.
    """
    ensure_shop_access(user, shop_id)
    return get_calendar_data(shop_id=shop_id, date=date)

@router.post("/simulate", response_model=AppointmentResponse)
def simulate_appointment(
    payload: SimulateAppointmentRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Simula en caliente la inyección de un nuevo turno para la defensa en vivo,
    evaluándolo inmediatamente con el clasificador Gradient Boosting.
    """
    ensure_shop_access(user, payload.shop_id)
    return simulate_appointment_service(payload)
