from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List


class OrderOut(BaseModel):
    id: int
    total_price: float

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    name: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    user_id: int
    total_price: float


class OrderCreated(BaseModel):
    order_id: int
