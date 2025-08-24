from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views import (
    AccountingAuditViewSet,
    AppLogViewSet,
    ClientViewSet,
    ComplianceViewSet,
    FinanceImplementationViewSet,
    FinancialStatementPreparationViewSet,
    HumanResourceImplementationViewSet,
    MiscellaneousTasksViewSet,
    NotificationViewSet,
    StatsAPIView,
    TaxCaseViewSet,
    UserViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"clients", ClientViewSet)
router.register(r"notifications", NotificationViewSet)
router.register(r"app-logs", AppLogViewSet)
router.register(r"compliance", ComplianceViewSet)
router.register(r"accounting-audits", AccountingAuditViewSet)
router.register(
    r"financial-statement-preparations",
    FinancialStatementPreparationViewSet,
    basename="financial-statement-preparation",
)
router.register(r"finance-implementations", FinanceImplementationViewSet)
router.register(r"human-resource-implementations", HumanResourceImplementationViewSet)
router.register(r"miscellaneous-tasks", MiscellaneousTasksViewSet)
router.register(r"tax-cases", TaxCaseViewSet)


urlpatterns = router.urls + [
    path("stats/", StatsAPIView.as_view(), name="stats"),
]
