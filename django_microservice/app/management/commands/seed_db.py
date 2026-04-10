from django.core.management.base import BaseCommand
from ...models import User, Order
import random


class Command(BaseCommand):
    help = "Seed database with users and orders"

    def handle(self, *args, **kwargs):
        User.objects.all().delete()

        users = []
        for i in range(1000):
            users.append(
                User(
                    email=f"user{i}@test.com",
                    name=f"User {i}"
                )
            )

        User.objects.bulk_create(users)

        orders = []
        users = User.objects.all()

        for user in users:
            for _ in range(random.randint(5, 10)):
                orders.append(
                    Order(
                        user=user,
                        total_price=random.randint(10, 500)
                    )
                )

        Order.objects.bulk_create(orders)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users and {len(orders)} orders"
            )
        )