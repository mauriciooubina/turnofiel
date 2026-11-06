from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

class PreventiveActionRequest(BaseModel):
    appointment_id: int = Field(..., gt=0)
    shop_id: Literal["hellfish", "hooligans"]
    action_type: Literal["whatsapp", "confirm"]
    message: Optional[str] = Field(None, max_length=1000)

class PreventiveActionResponse(BaseModel):
    id: int
    appointment_id: int
    shop_id: str
    action_type: str
    message: Optional[str] = None
    created_at: datetime
