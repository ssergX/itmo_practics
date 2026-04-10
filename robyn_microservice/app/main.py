import logging
import time
import orjson

from robyn import Robyn, Request, Response
from robyn.argument_parser import Config

import robyn as _robyn
from sqlalchemy import text

from .db import Base, engine, SessionLocal
from . import crud

logging.basicConfig(level=logging.INFO)

_start_time = time.time()

config = Config()
app = Robyn(__file__, config=config)


@app.startup_handler
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health/")
async def health_check(request: Request):
    db_ok = False
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return json_response({
        "status": "ok" if db_ok else "degraded",
        "service": "robyn",
        "framework": f"Robyn {_robyn.__version__}",
        "database": "connected" if db_ok else "disconnected",
        "uptime_s": round(time.time() - _start_time, 1),
    })


# --- helpers ---

def json_response(data, status_code=200):
    return Response(
        status_code=status_code,
        headers={"content-type": "application/json"},
        description=orjson.dumps(data),
    )


def error_response(detail: str, status_code=400):
    return json_response({"error": detail}, status_code=status_code)


# --- routes ---

def structured_log(request_id, method, path, status, elapsed_ms):
    import json as _json
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "service": "robyn",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
    }
    logging.info(_json.dumps(entry, ensure_ascii=False))


def get_request_id(request: Request):
    import uuid
    for key, value in request.headers.items():
        if key.lower() == "x-request-id":
            return value
    return str(uuid.uuid4())


def _users_to_dicts(users):
    return [
        {
            "id": u.id, "email": u.email, "name": u.name,
            "orders": [{"id": o.id, "total_price": float(o.total_price)} for o in u.orders],
        }
        for u in users
    ]


@app.get("/api/users/")
async def get_users(request: Request):
    request_id = get_request_id(request)
    start = time.perf_counter()

    # Pagination support
    page = request.query_params.get("page")
    size = request.query_params.get("size")

    async with SessionLocal() as session:
        if page and size:
            total, users = await crud.list_users_paginated(session, int(page), int(size))
            data = {"page": int(page), "size": int(size), "total": total, "data": _users_to_dicts(users)}
        else:
            users = await crud.list_users(session)
            data = _users_to_dicts(users)

    elapsed = (time.perf_counter() - start) * 1000
    structured_log(request_id, "GET", "/api/users/", 200, elapsed)
    return json_response(data)


@app.get("/api/users/optimized/")
async def get_users_optimized(request: Request):
    request_id = get_request_id(request)
    start = time.perf_counter()

    async with SessionLocal() as session:
        data = await crud.list_users_optimized(session)

    elapsed = (time.perf_counter() - start) * 1000
    structured_log(request_id, "GET", "/api/users/optimized/", 200, elapsed)
    return json_response(data)


@app.get("/api/analytics/")
async def get_analytics(request: Request):
    request_id = get_request_id(request)
    start = time.perf_counter()

    async with SessionLocal() as session:
        data = await crud.get_analytics(session)

    elapsed = (time.perf_counter() - start) * 1000
    structured_log(request_id, "GET", "/api/analytics/", 200, elapsed)
    return json_response(data)


@app.post("/api/users/")
async def post_user(request: Request):
    request_id = get_request_id(request)
    start = time.perf_counter()
    body = orjson.loads(request.body)

    email = body.get("email")
    name = body.get("name")

    if not email:
        return error_response("email is required")

    async with SessionLocal() as session:
        user = await crud.create_user(session, email, name)
        result = {"id": user.id, "email": user.email, "name": user.name}

    elapsed = (time.perf_counter() - start) * 1000
    structured_log(request_id, "POST", "/api/users/", 201, elapsed)

    return json_response(result, status_code=201)


@app.post("/api/orders/")
async def post_order(request: Request):
    request_id = get_request_id(request)
    start = time.perf_counter()
    body = orjson.loads(request.body)

    user_id = body.get("user_id")
    total_price = body.get("total_price")

    if not user_id or total_price is None:
        return error_response("invalid data")

    async with SessionLocal() as session:
        try:
            order = await crud.create_order(session, user_id, total_price)
        except ValueError:
            return error_response("user not found")
        result = {"order_id": order.id}

    elapsed = (time.perf_counter() - start) * 1000
    structured_log(request_id, "POST", "/api/orders/", 201, elapsed)

    return json_response(result, status_code=201)
