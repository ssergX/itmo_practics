import pytest
import httpx

BASE = "http://localhost:8000"


@pytest.mark.asyncio
async def test_full_flow():
    async with httpx.AsyncClient(base_url=BASE) as client:
        # create user
        r = await client.post("/api/users/", json={
            "email": "user@test.com",
            "name": "Test"
        })
        uid = r.json()["id"]

        # create orders
        for _ in range(5):
            await client.post("/api/orders/", json={
                "user_id": uid,
                "total_price": 100
            })

        # read user
        r = await client.get("/api/users/")
        users = r.json()
        assert any(len(u["orders"]) == 5 for u in users)
