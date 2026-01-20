from locust import HttpUser, task, between
import random


class ApiUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task(5)
    def read_users(self):
        self.client.get("/api/users/")

    @task(3)
    def create_user(self):
        self.client.post("/api/users/", json={
            "email": f"user{random.randint(1, 10_000_000)}@test.com",
            "name": "LoadUser",
        })

    @task(2)
    def create_order(self):
        # создаём пользователя в рамках задачи -> берём его id -> создаём заказ
        r = self.client.post("/api/users/", json={
            "email": f"order_user{random.randint(1, 10_000_000)}@test.com",
            "name": "OrderUser",
        })
        if r.status_code != 201:
            return

        user_id = r.json()["id"]

        self.client.post("/api/orders/", json={
            "user_id": user_id,
            "total_price": random.randint(10, 500),
        })
