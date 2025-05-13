from django.urls import path

from core.views import download_client_document

app_name = "core"

urlpatterns = [
    path(
        "download-client-document/<str:file_id>/",
        download_client_document,
        name="download_client_document",
    ),
]
