from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views import (
    AppLogViewSet,
    ClientViewSet,
    NotificationViewSet,
    StatsAPIView,
    TaskViewSet,
    UserViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"clients", ClientViewSet)
router.register(r"notifications", NotificationViewSet)
router.register(r"app-logs", AppLogViewSet)
router.register(r"tasks", TaskViewSet)


urlpatterns = router.urls + [
    path("stats/", StatsAPIView.as_view(), name="stats"),
]
