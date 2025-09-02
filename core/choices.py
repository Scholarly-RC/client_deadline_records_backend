from django.db import models


class TaskCategory(models.TextChoices):
    COMPLIANCE = "compliance", "Compliance"
    FINANCIAL_STATEMENT = "financial_statement", "Financial Statement Preparation"
    ACCOUNTING_AUDIT = "accounting_audit", "Accounting Audit"
    FINANCE_IMPLEMENTATION = "finance_implementation", "Finance Implementation"
    HR_IMPLEMENTATION = "hr_implementation", "Human Resource Implementation"
    MISCELLANEOUS = "miscellaneous", "Miscellaneous Tasks"
    TAX_CASE = "tax_case", "Tax Case"


class TaskStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    FOR_REVISION = "for_revision", "For Revision"
    FOR_CHECKING = "for_checking", "For Checking"
    ON_GOING = "on_going", "On Going"
    PENDING = "pending", "Pending"
    NOT_YET_STARTED = "not_yet_started", "Not Yet Started"
    CANCELLED = "cancelled", "Cancelled"


class TaskPriority(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class ClientStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class UserRoles(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"


class TaxCaseCategory(models.TextChoices):
    ONE_TIME_ENGAGEMENT = "OTE", "One-Time Engagement"
    REGULAR_PROCESS = "RP", "Regular Process"


class TypeOfTaxCase(models.TextChoices):
    PERCENTAGE_TAX = "PT", "Percentage Tax"
    INCOME_TAX = "IT", "Income Tax"
    WITHHOLDING_EXPANDED = "WE", "Withholding Tax - Expanded"


class BirForms(models.TextChoices):
    BIR_FORM_2551Q = "2551Q", "BIR Form 2551Q - Quarterly Percentage Tax Return"
    BIR_FORM_1701 = (
        "1701",
        "BIR Form 1701 - Annual Income Tax Return (Individuals, Estates, Trusts)",
    )
    BIR_FORM_0619E = (
        "0619E",
        "BIR Form 0619E - Monthly Remittance Form of Creditable Income Taxes Withheld (Expanded)",
    )
    BIR_FORM_1601EQ = (
        "1601EQ",
        "BIR Form 1601-EQ - Quarterly Remittance Return of Creditable Income Taxes Withheld (Expanded)",
    )
