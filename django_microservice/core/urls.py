from django.urls import path, include
from app.health import health_check

urlpatterns = [
    path("api/", include("app.urls")),
    path("health/", health_check),
]