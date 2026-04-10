import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar, get, post, Response
from litestar.di import Provide
from litestar.middleware.base import AbstractMiddleware
from litestar.types import Receive, Scope, Send
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, engine, SessionLocal
from . import schemas, crud
from .monitoring import snapshot, log_line

logging.basicConfig(level=logging.INFO)


async def provide_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


class MetricsMiddleware(AbstractMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        await self.app(scope, receive, send)
        m = snapshot(start)
        method = scope.get("method", "?")
        path = scope.get("path", "?")
        log_line(method, path, m)


@get("/api/users/")
async def get_users(session: AsyncSession) -> list[schemas.UserOut]:
    users = await crud.list_users(session)
    return [
        schemas.UserOut(
            id=u.id,
            email=u.email,
            name=u.name,
            orders=[
                schemas.OrderOut(id=o.id, total_price=float(o.total_price))
                for o in u.orders
            ],
        )
        for u in users
    ]


@post("/api/users/", status_code=201)
async def post_user(data: schemas.UserCreate, session: AsyncSession) -> schemas.UserOut:
    user = await crud.create_user(session, data.email, data.name)
    return schemas.UserOut(id=user.id, email=user.email, name=user.name, orders=[])


@post("/api/orders/", status_code=201)
async def post_order(data: schemas.OrderCreate, session: AsyncSession) -> schemas.OrderCreated:
    try:
        order = await crud.create_order(session, data.user_id, data.total_price)
    except ValueError:
        return Response(content={"detail": "user_not_found"}, status_code=400)
    return schemas.OrderCreated(order_id=order.id)


app = Litestar(
    route_handlers=[get_users, post_user, post_order],
    dependencies={"session": Provide(provide_session)},
    lifespan=[lifespan],
    middleware=[MetricsMiddleware],
)
