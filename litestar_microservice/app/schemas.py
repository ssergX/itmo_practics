import msgspec


class OrderOut(msgspec.Struct):
    id: int
    total_price: float


class UserCreate(msgspec.Struct):
    email: str
    name: str


class UserOut(msgspec.Struct):
    id: int
    email: str
    name: str
    orders: list[OrderOut] = []


class OrderCreate(msgspec.Struct):
    user_id: int
    total_price: float


class OrderCreated(msgspec.Struct):
    order_id: int
