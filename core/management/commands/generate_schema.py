from django.core.management.base import BaseCommand
from drf_spectacular.management.commands.spectacular import (
    Command as SpectacularCommand,
)


class Command(BaseCommand):
    help = "Generate API schema"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="Output file path")
        parser.add_argument("--validate", action="store_true", help="Validate schema")
        parser.add_argument(
            "--format", type=str, default="openapi", help="Output format"
        )

    def handle(self, *args, **options):
        # Create a new instance of the spectacular command
        spectacular_cmd = SpectacularCommand()
        spectacular_cmd.stdout = self.stdout
        spectacular_cmd.stderr = self.stderr

        # Call the spectacular command with our options
        file_path = options.get("file", "schema.yml")
        validate = options.get("validate", True)
        format_type = options.get("format", "openapi")

        # Execute the spectacular command
        from django.core.management import execute_from_command_line

        cmd_args = [
            "manage.py",
            "spectacular",
            "--file",
            file_path,
            "--format",
            format_type,
        ]
        if validate:
            cmd_args.append("--validate")

        execute_from_command_line(cmd_args)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully generated schema at {file_path}")
        )
