from rest_framework.routers import DefaultRouter

from core.views import (
    ClientDeadlineViewSet,
    ClientDocumentViewSet,
    ClientViewSet,
    DeadlineTypeViewSet,
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
router.register(r"client-documents", ClientDocumentViewSet, basename="clientdocument")

urlpatterns = router.urls
