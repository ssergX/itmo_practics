import logging
import time
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, engine, get_session
from . import schemas, crud
from .monitoring import snapshot, log_line

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FastAPI REST Prototype")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    m = snapshot(start)
    log_line(request.method, request.url.path, m)
    return response


@app.get("/api/users/", response_model=list[schemas.UserOut])
async def get_users(session: AsyncSession = Depends(get_session)):
    return await crud.list_users(session)


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
