from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from core.models import (AppLog, Client, ClientDocument, Notification, Task,
                         TaskApproval, TaskStatusHistory, User)


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


class TaskStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "task",
        "old_status",
        "new_status",
        "changed_by",
        "change_type",
        "created_at",
    )
    list_filter = ("new_status", "old_status", "change_type", "created_at")
    search_fields = ("task__description", "changed_by__username", "remarks")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("task", "changed_by", "related_approval")
        )


class TaskApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "task",
        "approver",
        "action",
        "step_number",
        "created_at",
        "updated_at",
    )
    list_filter = ("action", "step_number", "created_at", "updated_at")
    search_fields = ("task__description", "approver__username", "comments")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("task", "approver", "next_approver")
        )


class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "client",
        "category",
        "status",
        "assigned_to",
        "priority",
        "deadline",
        "requires_approval",
        "current_approval_step",
    )
    list_filter = (
        "category",
        "status",
        "priority",
        "requires_approval",
        "deadline",
        "created_at" if hasattr(Task, "created_at") else "last_update",
    )
    search_fields = ("description", "client__name", "assigned_to__username")
    readonly_fields = ("last_update",)
    ordering = ("-last_update",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("client", "assigned_to")


class ClientDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "client",
        "uploaded_by",
        "file_size",
        "file_extension",
        "uploaded_at",
    )
    list_filter = ("uploaded_at", "client", "uploaded_by")
    search_fields = ("title", "description", "client__name", "uploaded_by__username")
    readonly_fields = ("uploaded_at", "updated_at", "file_size", "file_extension")
    ordering = ("-uploaded_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("client", "uploaded_by")


# Register your models here.
admin.site.register(AppLog)
admin.site.register(Client)
admin.site.register(ClientDocument, ClientDocumentAdmin)
admin.site.register(Notification)
admin.site.register(Task, TaskAdmin)
admin.site.register(TaskApproval, TaskApprovalAdmin)
admin.site.register(TaskStatusHistory, TaskStatusHistoryAdmin)
admin.site.register(User, CustomUserAdmin)
