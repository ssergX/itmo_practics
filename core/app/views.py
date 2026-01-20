import time
import logging
from asgiref.sync import sync_to_async
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import User, Order
from .serializers import UserSerializer
from .monitoring import get_process_metrics

logger = logging.getLogger("app")


class UserListCreateView(APIView):
    """
    GET  /api/users/   – read-heavy
    POST /api/users/   – create user
    """

    async def get(self, request):
        start = time.perf_counter()

        users = await self._get_users()
        data = UserSerializer(users, many=True).data  # сериализация синхронная, но CPU-bound, ок

        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics = get_process_metrics()

        logger.info(
            "GET /api/users/ | "
            f"time={elapsed_ms:.2f}ms | "
            f"cpu={metrics['cpu_percent']}% | "
            f"ram={metrics['memory_mb']:.1f}MB | "
            f"threads={metrics['threads']}"
        )
        return Response(data)

    async def post(self, request):
        start = time.perf_counter()

        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = await self._save_user(serializer)

            elapsed_ms = (time.perf_counter() - start) * 1000
            metrics = get_process_metrics()

            logger.info(
                "POST /api/users/ | "
                f"time={elapsed_ms:.2f}ms | "
                f"cpu={metrics['cpu_percent']}% | "
                f"ram={metrics['memory_mb']:.1f}MB | "
                f"threads={metrics['threads']}"
            )

            # чтобы ответ совпадал с FastAPI: можно вернуть созданного пользователя
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    async def _get_users(self):
        # ORM синхронный -> обязательно в threadpool
        return await sync_to_async(list)(
            User.objects.prefetch_related("orders").all()
        )

    async def _save_user(self, serializer):
        # serializer.save() тоже синхронный
        return await sync_to_async(serializer.save)()


class OrderCreateView(APIView):
    """
    POST /api/orders/ – write-heavy
    """

    async def post(self, request):
        start = time.perf_counter()

        user_id = request.data.get("user_id")
        price = request.data.get("total_price")

        if not user_id or not price:
            return Response({"error": "invalid data"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = await self._create_order(user_id, price)
        except User.DoesNotExist:
            logger.warning(f"POST /api/orders/ | invalid user_id={user_id}")
            return Response({"error": "user not found"}, status=status.HTTP_400_BAD_REQUEST)

        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics = get_process_metrics()

        logger.info(
            "POST /api/orders/ | "
            f"time={elapsed_ms:.2f}ms | "
            f"cpu={metrics['cpu_percent']}% | "
            f"ram={metrics['memory_mb']:.1f}MB | "
            f"threads={metrics['threads']}"
        )

        return Response({"order_id": order.id}, status=status.HTTP_201_CREATED)

    async def _create_order(self, user_id, price):
        @sync_to_async
        def create():
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                return Order.objects.create(user=user, total_price=price)

        return await create()
