from random import choice, randint

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from faker import Faker

from core.choices import *
from core.models import *

User = get_user_model()


class Command(BaseCommand):
    help = "Populate all models with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=50, help="Number of records per model"
        )

    def handle(self, *args, **options):
        count = options["count"]
        fake = Faker()

        # Get existing users or create new ones
        existing_users = list(User.objects.all())
        users = existing_users.copy()

        # Create additional users if needed
        for i in range(max(0, count - len(existing_users))):
            # Find a unique username
            username = f"testuser_{i+1}"
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"testuser_{i+1}_{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password="password123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                role=choice([UserRoles.ADMIN, UserRoles.STAFF]),
            )
            users.append(user)

        # Clients
        clients = []
        for i in range(count):
            client = Client.objects.create(
                name=fake.company(),
                contact_person=fake.name(),
                email=fake.email(),
                phone=fake.phone_number(),
                address=fake.address(),
                tin=fake.random_number(digits=9),
                notes=fake.text(),
                created_by=choice(users),
            )
            clients.append(client)

        # Tasks
        tasks = []
        for i in range(count):
            task = Task.objects.create(
                client=choice(clients),
                category=choice(list(TaskCategory)),
                description=fake.sentence(),
                status=choice(list(TaskStatus)),
                assigned_to=choice(users),
                priority=choice(list(TaskPriority)),
                deadline=fake.date_this_year(),
                remarks=fake.text(),
                period_covered=fake.date_this_year().strftime("%Y-%m"),
                engagement_date=fake.date_this_year(),
                requires_approval=fake.boolean(),
            )
            tasks.append(task)

        # TaskStatusHistory
        for i in range(count):
            TaskStatusHistory.objects.create(
                task=choice(tasks),
                old_status=choice(list(TaskStatus)),
                new_status=choice(list(TaskStatus)),
                changed_by=choice(users),
                remarks=fake.text(),
                change_type=choice(["manual", "approval", "system"]),
            )

        # TaskApproval
        for i in range(count):
            TaskApproval.objects.create(
                task=choice(tasks),
                approver=choice(users),
                action=choice(["approved", "rejected", "pending"]),
                comments=fake.text(),
                step_number=randint(1, 5),
            )

        # Notifications
        for i in range(count):
            Notification.objects.create(
                recipient=choice(users),
                title=fake.sentence(),
                message=fake.text(),
                link=fake.url(),
                is_read=fake.boolean(),
            )

        # ClientDocuments - Use local storage to avoid R2 costs
        import os

        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        # Temporarily force local storage for dummy files
        original_storage = default_storage
        from django.core.files.storage import FileSystemStorage

        local_storage = FileSystemStorage(
            location=os.path.join(settings.BASE_DIR, "uploads", "client_documents")
        )

        for i in range(count):
            # Create dummy PDF content
            pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Dummy PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000200 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n284\n%%EOF"

            filename = f"dummy_{i+1}_{fake.file_name(extension='pdf')}"
            file_path = f"client_documents/{filename}"

            # Save to local storage
            local_storage.save(file_path, ContentFile(pdf_content))

            ClientDocument.objects.create(
                client=choice(clients),
                title=fake.sentence(),
                description=fake.text(),
                document_file=file_path,  # Store just the path, not the file object
                uploaded_by=choice(users),
            )

        # AppLogs
        for i in range(count):
            AppLog.objects.create(user=choice(users), details=fake.text())

        self.stdout.write(f"Successfully created {count} records for each model")
