import orjson
from django.http import HttpResponse
from django.db.models import Count, Avg, Sum, Min, Max
from adrf.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import User, Order
from .serializers import UserSerializer


def orjson_response(data, status_code=200):
    return HttpResponse(
        orjson.dumps(data),
        content_type="application/json",
        status=status_code,
    )


class UserListCreateView(APIView):
    async def get(self, request):
        users_qs = User.objects.prefetch_related("orders").order_by("id")

        # Pagination support
        page = request.query_params.get("page")
        size = request.query_params.get("size")
        if page and size:
            page, size = int(page), int(size)
            offset = (page - 1) * size
            total = await User.objects.acount()
            users = [u async for u in users_qs[offset:offset + size]]
            serializer = UserSerializer(users, many=True)
            return Response({
                "page": page,
                "size": size,
                "total": total,
                "data": serializer.data,
            })

        users = [u async for u in users_qs]
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    async def post(self, request):
        email = request.data.get("email")
        name = request.data.get("name")
        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)
        user = await User.objects.acreate(email=email, name=name)
        return Response(
            {"id": user.id, "email": user.email, "name": user.name},
            status=status.HTTP_201_CREATED,
        )


class UserListOptimizedView(APIView):
    """Optimized: .values() + orjson, no ORM objects."""

    async def get(self, request):
        users_qs = User.objects.order_by("id").values("id", "email", "name")
        users = [u async for u in users_qs]

        user_ids = [u["id"] for u in users]
        orders_qs = Order.objects.filter(user_id__in=user_ids).values("id", "user_id", "total_price")
        orders_by_user = {}
        async for o in orders_qs:
            orders_by_user.setdefault(o["user_id"], []).append(
                {"id": o["id"], "total_price": float(o["total_price"])}
            )

        data = [{**u, "orders": orders_by_user.get(u["id"], [])} for u in users]
        return orjson_response(data)


class AnalyticsView(APIView):
    async def get(self, request):
        user_count = await User.objects.acount()
        order_stats = await Order.objects.aaggregate(
            total_orders=Count("id"),
            avg_price=Avg("total_price"),
            total_revenue=Sum("total_price"),
            min_price=Min("total_price"),
            max_price=Max("total_price"),
        )

        top_users_qs = (
            User.objects
            .annotate(order_count=Count("orders"), total_spent=Sum("orders__total_price"))
            .order_by("-total_spent")
            .values("id", "email", "order_count", "total_spent")[:10]
        )
        top_users = [u async for u in top_users_qs]
        for u in top_users:
            u["total_spent"] = float(u["total_spent"]) if u["total_spent"] else 0

        return Response({
            "user_count": user_count,
            "order_count": order_stats["total_orders"],
            "avg_order_price": round(float(order_stats["avg_price"] or 0), 2),
            "total_revenue": round(float(order_stats["total_revenue"] or 0), 2),
            "min_order_price": round(float(order_stats["min_price"] or 0), 2),
            "max_order_price": round(float(order_stats["max_price"] or 0), 2),
            "top_users": top_users,
        })


class OrderCreateView(APIView):
    async def post(self, request):
        user_id = request.data.get("user_id")
        price = request.data.get("total_price")
        if not user_id or price is None:
            return Response({"error": "invalid data"}, status=status.HTTP_400_BAD_REQUEST)
        if not await User.objects.filter(id=user_id).aexists():
            return Response({"error": "user not found"}, status=status.HTTP_400_BAD_REQUEST)
        order = await Order.objects.acreate(user_id=user_id, total_price=price)
        return Response({"order_id": order.id}, status=status.HTTP_201_CREATED)
