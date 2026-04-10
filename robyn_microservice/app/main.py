import logging
import time
import orjson

from robyn import Robyn, Request, Response
from robyn.argument_parser import Config

from .db import Base, engine, SessionLocal
from . import crud
from .monitoring import snapshot, log_line

logging.basicConfig(level=logging.INFO)

config = Config()
app = Robyn(__file__, config=config)


@app.startup_handler
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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

@app.get("/api/users/")
async def get_users(request: Request):
    start = time.perf_counter()

    async with SessionLocal() as session:
        users = await crud.list_users(session)

    data = [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "orders": [
                {"id": o.id, "total_price": float(o.total_price)}
                for o in u.orders
            ],
        }
        for u in users
    ]

    m = snapshot(start)
    log_line("GET", "/api/users/", m)

    return json_response(data)


@app.post("/api/users/")
async def post_user(request: Request):
    start = time.perf_counter()
    body = orjson.loads(request.body)

    email = body.get("email")
    name = body.get("name")

    if not email:
        return error_response("email is required")

    async with SessionLocal() as session:
        user = await crud.create_user(session, email, name)
        result = {"id": user.id, "email": user.email, "name": user.name}

    m = snapshot(start)
    log_line("POST", "/api/users/", m)

    return json_response(result, status_code=201)


@app.post("/api/orders/")
async def post_order(request: Request):
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

    m = snapshot(start)
    log_line("POST", "/api/orders/", m)

    return json_response(result, status_code=201)
