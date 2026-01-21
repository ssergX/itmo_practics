from adrf.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.db.models import Prefetch

from .models import User, Order


class UserListCreateView(APIView):
    """
    GET  /api/users/   – read-heavy
    POST /api/users/   – create user
    """

    async def get(self, request):
        qs = (
            User.objects.only("id", "email", "name")
            .prefetch_related(
                Prefetch(
                    "orders",
                    queryset=Order.objects.only("id", "user_id", "total_price"),
                    to_attr="prefetched_orders",   # <-- важно
                )
            )
            .order_by("id")
        )

        data = []
        async for u in qs.aiterator(chunk_size=200):
            data.append({
                "id": u.id,
                "email": u.email,
                "name": getattr(u, "name", None),
                "orders": [
                    {"id": o.id, "total_price": o.total_price}
                    for o in getattr(u, "prefetched_orders", [])
                ],
            })

        return Response(data)

    async def post(self, request):
        email = request.data.get("email")
        name = request.data.get("name")

        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = await User.objects.acreate(email=email, name=name)

        return Response(
            {"id": user.id, "email": user.email, "name": getattr(user, "name", None)},
            status=status.HTTP_201_CREATED
        )


class OrderCreateView(APIView):
    async def post(self, request):
        user_id = request.data.get("user_id")
        price = request.data.get("total_price")

        if not user_id or price is None:
            return Response({"error": "invalid data"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = await Order.objects.acreate(user_id=user_id, total_price=price)
        except IntegrityError:
            return Response({"error": "user not found"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"order_id": order.id}, status=status.HTTP_201_CREATED)
