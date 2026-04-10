import orjson
from django.http import HttpResponse
from adrf.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import User, Order


def orjson_response(data, status_code=200):
    """JsonResponse на orjson — в ~3-5x быстрее стандартного json.dumps."""
    return HttpResponse(
        orjson.dumps(data),
        content_type="application/json",
        status=status_code,
    )


class UserListCreateView(APIView):
    """
    GET  /api/users/   – read-heavy
    POST /api/users/   – create user
    """

    async def get(self, request):
        # .values() возвращает dict, минуя создание Model-объектов — основной выигрыш
        users_qs = User.objects.order_by("id").values("id", "email", "name")
        users = [u async for u in users_qs]

        # Собираем orders одним запросом, группируем в Python
        user_ids = [u["id"] for u in users]
        orders_qs = (
            Order.objects
            .filter(user_id__in=user_ids)
            .values("id", "user_id", "total_price")
        )
        orders_by_user = {}
        async for o in orders_qs:
            orders_by_user.setdefault(o["user_id"], []).append(
                {"id": o["id"], "total_price": float(o["total_price"])}
            )

        data = [
            {
                **u,
                "orders": orders_by_user.get(u["id"], []),
            }
            for u in users
        ]

        return orjson_response(data)

    async def post(self, request):
        email = request.data.get("email")
        name = request.data.get("name")

        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = await User.objects.acreate(email=email, name=name)

        return orjson_response(
            {"id": user.id, "email": user.email, "name": user.name},
            status_code=201,
        )


class OrderCreateView(APIView):
    async def post(self, request):
        user_id = request.data.get("user_id")
        price = request.data.get("total_price")

        if not user_id or price is None:
            return Response({"error": "invalid data"}, status=status.HTTP_400_BAD_REQUEST)

        if not await User.objects.filter(id=user_id).aexists():
            return Response({"error": "user not found"}, status=status.HTTP_400_BAD_REQUEST)

        order = await Order.objects.acreate(user_id=user_id, total_price=price)

        return orjson_response({"order_id": order.id}, status_code=201)
