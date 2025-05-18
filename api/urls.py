from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views import (
    AppLogViewSet,
    ClientDeadlineViewSet,
    ClientDocumentViewSet,
    ClientViewSet,
    DeadlineTypeViewSet,
    NotificationViewSet,
    StatsAPIView,
    UserViewSet,
    WorkUpdateViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"clients", ClientViewSet)
router.register(r"deadline-types", DeadlineTypeViewSet)
router.register(r"client-deadlines", ClientDeadlineViewSet, basename="clientdeadline")
router.register(r"work-updates", WorkUpdateViewSet, basename="workupdate")
router.register(r"client-documents", ClientDocumentViewSet)
router.register(r"notifications", NotificationViewSet)
router.register(r"app-logs", AppLogViewSet)

urlpatterns = router.urls + [
    path("stats/", StatsAPIView.as_view(), name="stats"),
]
