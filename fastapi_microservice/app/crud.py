from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, Order


async def list_users(session: AsyncSession) -> list[User]:
    stmt = select(User).options(selectinload(User.orders)).order_by(User.id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def list_users_paginated(session: AsyncSession, page: int, size: int):
    offset = (page - 1) * size
    total = await session.scalar(select(func.count()).select_from(User))
    stmt = (
        select(User).options(selectinload(User.orders))
        .order_by(User.id).offset(offset).limit(size)
    )
    res = await session.execute(stmt)
    return total, list(res.scalars().all())


async def list_users_optimized(session: AsyncSession) -> list[dict]:
    users_rows = await session.execute(
        select(User.id, User.email, User.name).order_by(User.id)
    )
    users = [dict(r._mapping) for r in users_rows]

    user_ids = [u["id"] for u in users]
    orders_rows = await session.execute(
        select(Order.id, Order.user_id, Order.total_price)
        .where(Order.user_id.in_(user_ids))
    )
    orders_by_user: dict[int, list] = {}
    for o in orders_rows:
        orders_by_user.setdefault(o.user_id, []).append(
            {"id": o.id, "total_price": float(o.total_price)}
        )
    for u in users:
        u["orders"] = orders_by_user.get(u["id"], [])
    return users


async def get_analytics(session: AsyncSession) -> dict:
    user_count = await session.scalar(select(func.count()).select_from(User))
    row = (await session.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.avg(Order.total_price).label("avg_price"),
            func.sum(Order.total_price).label("total_revenue"),
            func.min(Order.total_price).label("min_price"),
            func.max(Order.total_price).label("max_price"),
        )
    )).one()

    top_stmt = (
        select(
            User.id, User.email,
            func.count(Order.id).label("order_count"),
            func.sum(Order.total_price).label("total_spent"),
        )
        .join(Order, User.id == Order.user_id)
        .group_by(User.id, User.email)
        .order_by(func.sum(Order.total_price).desc())
        .limit(10)
    )
    top_rows = (await session.execute(top_stmt)).all()

    return {
        "user_count": user_count,
        "order_count": row.total_orders,
        "avg_order_price": round(float(row.avg_price or 0), 2),
        "total_revenue": round(float(row.total_revenue or 0), 2),
        "min_order_price": round(float(row.min_price or 0), 2),
        "max_order_price": round(float(row.max_price or 0), 2),
        "top_users": [
            {"id": r.id, "email": r.email, "order_count": r.order_count,
             "total_spent": round(float(r.total_spent or 0), 2)}
            for r in top_rows
        ],
    }


async def create_user(session: AsyncSession, email: str, name: str) -> User:
    user = User(email=email, name=name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_order(session: AsyncSession, user_id: int, total_price: float) -> Order:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("user_not_found")
    order = Order(user_id=user_id, total_price=total_price)
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order
