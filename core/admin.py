from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from core.models import (
    AppLog,
    Client,
    Notification,
    User,
)


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("username", "email", "fullname", "role")
    list_filter = ("role", "is_superuser", "is_active")
    search_fields = ("username", "first_name", "middle_name", "last_name", "email")
    ordering = (
        "role",
        "first_name",
    )

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
                    "role",
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
admin.site.register(AppLog)
admin.site.register(Client)
admin.site.register(Notification)
admin.site.register(User, CustomUserAdmin)
