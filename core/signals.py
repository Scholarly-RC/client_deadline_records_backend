import os

from django.db.models.signals import post_delete
from django.dispatch import receiver

# @receiver(post_delete, sender=ClientDocument)
# def delete_file_on_document_delete(sender, instance, **kwargs):
#     if instance.file and instance.file.path and os.path.isfile(instance.file.path):
#         os.remove(instance.file.path)
