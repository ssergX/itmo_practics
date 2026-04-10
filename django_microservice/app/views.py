from adrf.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import User, Order
from .serializers import UserSerializer


class UserListCreateView(APIView):
    """
    GET  /api/users/   – read-heavy
    POST /api/users/   – create user
    """

    async def get(self, request):
        # ORM-объекты с prefetch_related — стандартный Django-паттерн
        users_qs = User.objects.prefetch_related("orders").order_by("id")
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
