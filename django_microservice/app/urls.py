from django.urls import path
from .views import UserListCreateView, UserListOptimizedView, AnalyticsView, OrderCreateView

urlpatterns = [
    path("users/", UserListCreateView.as_view()),
    path("users/optimized/", UserListOptimizedView.as_view()),
    path("analytics/", AnalyticsView.as_view()),
    path("orders/", OrderCreateView.as_view()),
]
