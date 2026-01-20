from locust import HttpUser, task, between
import random


class ApiUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self):
        """
        Инициализация состояния виртуального пользователя
        """
        self.user_ids = []

        response = self.client.get("/api/users/")
        if response.status_code == 200:
            self.user_ids = [u["id"] for u in response.json()]

    @task(5)
    def read_users(self):
        self.client.get("/api/users/")

    @task(3)
    def create_user(self):
        response = self.client.post("/api/users/", json={
            "email": f"user{random.randint(1, 10_000_000)}@test.com",
            "name": "LoadUser"
        })

        if response.status_code == 201:
            self.user_ids.append(response.json()["id"])

    @task(2)
    def create_order(self):
        if not self.user_ids:
            return

        user_id = random.choice(self.user_ids)
        self.client.post("/api/orders/", json={
            "user_id": user_id,
            "total_price": random.randint(10, 500)
        })