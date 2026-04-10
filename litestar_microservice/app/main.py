import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import litestar as _litestar
from litestar import Litestar, get, post, Response
from litestar.di import Provide
from litestar.middleware.base import AbstractMiddleware
from litestar.types import Receive, Scope, Send
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, engine, SessionLocal
from . import schemas, crud

logging.basicConfig(level=logging.INFO)

_start_time = time.time()


async def provide_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


class StructuredLoggingMiddleware(AbstractMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import uuid
        import json
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())
        start = time.perf_counter()
        await self.app(scope, receive, send)
        elapsed = (time.perf_counter() - start) * 1000
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "service": "litestar",
            "request_id": request_id,
            "method": scope.get("method", "?"),
            "path": scope.get("path", "?"),
            "elapsed_ms": round(elapsed, 2),
        }
        logging.info(json.dumps(log_entry, ensure_ascii=False))


def _user_to_schema(u) -> schemas.UserOut:
    return schemas.UserOut(
        id=u.id, email=u.email, name=u.name,
        orders=[schemas.OrderOut(id=o.id, total_price=float(o.total_price)) for o in u.orders],
    )


@get("/api/users/")
async def get_users(session: AsyncSession, page: int | None = None, size: int | None = None) -> Response:
    import orjson
    if page and size:
        total, users = await crud.list_users_paginated(session, page, size)
        data = {
            "page": page, "size": size, "total": total,
            "data": [_user_to_schema(u) for u in users],
        }
        return Response(content=orjson.dumps(data, default=lambda o: o.__dict__), media_type="application/json")
    users = await crud.list_users(session)
    return [_user_to_schema(u) for u in users]


@get("/api/users/optimized/")
async def get_users_optimized(session: AsyncSession) -> Response:
    import orjson
    data = await crud.list_users_optimized(session)
    return Response(content=orjson.dumps(data), media_type="application/json")


@get("/api/analytics/")
async def get_analytics(session: AsyncSession) -> dict:
    return await crud.get_analytics(session)


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


@get("/health/")
async def health_check(session: AsyncSession) -> dict:
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "litestar",
        "framework": f"Litestar {_litestar.__version__}",
        "database": "connected" if db_ok else "disconnected",
        "uptime_s": round(time.time() - _start_time, 1),
    }


app = Litestar(
    route_handlers=[get_users, get_users_optimized, get_analytics, post_user, post_order, health_check],
    dependencies={"session": Provide(provide_session)},
    lifespan=[lifespan],
    middleware=[StructuredLoggingMiddleware],
)
