from django.urls import path
from .views import UserListCreateView, OrderCreateView

urlpatterns = [
    path("users/", UserListCreateView.as_view()),
    path("orders/", OrderCreateView.as_view()),
]
