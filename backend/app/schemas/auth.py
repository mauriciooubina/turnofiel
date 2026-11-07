from typing import Literal, Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=200)

class CurrentUser(BaseModel):
    username: str
    role: Literal["admin", "shop"]
    shop_id: Optional[Literal["hellfish", "hooligans"]] = None

class LoginResponse(CurrentUser):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
