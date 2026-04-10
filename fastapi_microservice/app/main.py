import logging
import time
import fastapi
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, engine, get_session
from . import schemas, crud
from .monitoring import snapshot, log_line

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FastAPI REST Prototype")

_start_time = time.time()


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health/")
async def health_check(session: AsyncSession = Depends(get_session)):
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "fastapi",
        "framework": f"FastAPI {fastapi.__version__}",
        "database": "connected" if db_ok else "disconnected",
        "uptime_s": round(time.time() - _start_time, 1),
    }


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    import uuid, json
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "service": "fastapi",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "elapsed_ms": round(elapsed, 2),
    }
    logging.info(json.dumps(log_entry, ensure_ascii=False))
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/api/users/")
async def get_users(
    page: int = None, size: int = None,
    session: AsyncSession = Depends(get_session),
):
    if page and size:
        total, users = await crud.list_users_paginated(session, page, size)
        return {
            "page": page, "size": size, "total": total,
            "data": [schemas.UserOut.model_validate(u) for u in users],
        }
    users = await crud.list_users(session)
    return [schemas.UserOut.model_validate(u) for u in users]


@app.get("/api/users/optimized/")
async def get_users_optimized(session: AsyncSession = Depends(get_session)):
    import orjson
    from fastapi.responses import Response as FastAPIResponse
    data = await crud.list_users_optimized(session)
    return FastAPIResponse(content=orjson.dumps(data), media_type="application/json")


@app.get("/api/analytics/")
async def get_analytics(session: AsyncSession = Depends(get_session)):
    return await crud.get_analytics(session)


@app.post("/api/users/", response_model=schemas.UserCreated, status_code=201)
async def post_user(payload: schemas.UserCreate, session: AsyncSession = Depends(get_session)):
    user = await crud.create_user(session, payload.email, payload.name)
    return user


@app.post("/api/orders/", response_model=schemas.OrderCreated, status_code=201)
async def post_order(payload: schemas.OrderCreate, session: AsyncSession = Depends(get_session)):
    try:
        order = await crud.create_order(session, payload.user_id, payload.total_price)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_not_found")
    return {"order_id": order.id}
