from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from core.models import (
    Client,
    ClientDeadline,
    ClientDocument,
    DeadlineType,
    User,
    WorkUpdate,
)


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = (
        "username",
        "email",
        "first_name",
        "middle_name",
        "last_name",
        "fullname",
        "is_staff",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "middle_name", "last_name", "email")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {"fields": ("first_name", "middle_name", "last_name", "email")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "updated")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    readonly_fields = ("updated", "last_login", "date_joined")


# Register your models here.
admin.site.register(Client)
admin.site.register(ClientDeadline)
admin.site.register(ClientDocument)
admin.site.register(DeadlineType)
admin.site.register(User, CustomUserAdmin)
admin.site.register(WorkUpdate)
