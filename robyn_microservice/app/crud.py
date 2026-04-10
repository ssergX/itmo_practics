from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, Order


async def list_users(session: AsyncSession) -> list[User]:
    stmt = select(User).options(selectinload(User.orders)).order_by(User.id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


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
