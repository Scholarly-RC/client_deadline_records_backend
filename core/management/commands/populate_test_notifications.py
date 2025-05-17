# management/commands/generate_sample_notifications.py
from random import choice, randint

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from faker import Faker

from core.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = "Generates 30 sample notifications for testing purposes"

    def handle(self, *args, **options):
        fake = Faker()

        # Generate 30 sample notifications
        notification_types = [
            ("System Update", "A new system update is available"),
            ("New Message", "You have received a new message"),
            ("Task Reminder", "Don't forget to complete your task"),
            ("Event Invitation", "You've been invited to an event"),
            ("Payment Received", "Your payment has been processed"),
        ]

        links = [
            "/dashboard",
            "/messages",
            "/tasks",
            "/events",
            "/payments",
            None,
            None,
        ]

        for i in range(30):
            notification_type = choice(notification_types)

            Notification.objects.create(
                recipient=User.objects.get(id=11),
                title=notification_type[0] + (f" #{i}" if randint(0, 1) else ""),
                message=f"{notification_type[1]}. {fake.sentence()}",
                link=choice(links),
                is_read=fake.boolean(chance_of_getting_true=30),
            )

        self.stdout.write(
            self.style.SUCCESS("Successfully generated 30 sample notifications")
        )
