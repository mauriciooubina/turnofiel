from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

ShopId = Literal["hellfish", "hooligans"]

class PrivacySearchRequest(BaseModel):
    shop_id: ShopId
    query: str = Field(..., min_length=1, max_length=64)

class ClientAppointment(BaseModel):
    id: int
    date: str
    start_time: str
    service_name: Optional[str] = None
    barber_name: Optional[str] = None
    target: Optional[int] = None

class ClientRecord(BaseModel):
    client_hashed: str
    total_appointments: int
    no_shows: int
    do_not_contact: bool
    erased: bool
    erased_at: Optional[datetime] = None
    appointments: List[ClientAppointment]

class PrivacySearchResponse(BaseModel):
    shop_id: ShopId
    query_type: Literal["phone", "client_hashed"]
    clients: List[ClientRecord]

class PrivacyRequestCreate(BaseModel):
    shop_id: ShopId
    client_hashed: str = Field(..., pattern=r"^[0-9a-f]{16}$")
    request_type: Literal["do_not_contact", "allow_contact", "erasure"]

class PrivacyStateResponse(BaseModel):
    client_hashed: str
    do_not_contact: bool
    erased: bool
    erased_at: Optional[datetime] = None
