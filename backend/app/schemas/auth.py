from datetime import datetime
from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime

class TokenPayload(BaseModel):
    sub: str | None = None

class LoginRequest(BaseModel):
    username: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    role: str

    class Config:
        from_attributes = True
