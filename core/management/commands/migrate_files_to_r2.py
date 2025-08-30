from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.core.files.base import File
from core.models import ClientDocument
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Migrate existing local files to Cloudflare R2 storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--delete-local',
            action='store_true',
            help='Delete local files after successful migration to R2',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_local = options['delete_local']

        self.stdout.write(
            self.style.WARNING('Starting file migration to R2...')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No files will be actually migrated')
            )

        # Get all documents
        documents = ClientDocument.objects.all()
        total_docs = documents.count()

        self.stdout.write(f'Found {total_docs} documents to check')

        migrated_count = 0
        skipped_count = 0
        error_count = 0

        for doc in documents:
            try:
                file_path = doc.document_file.name
                local_path = os.path.join('uploads', file_path)

                # Check if file exists locally
                if os.path.exists(local_path):
                    self.stdout.write(f'Processing: {file_path}')

                    if dry_run:
                        self.stdout.write(f'  Would migrate: {local_path} -> R2')
                        migrated_count += 1
                        continue

                    # Read local file
                    with open(local_path, 'rb') as local_file:
                        file_content = local_file.read()

                    # Upload to R2
                    r2_file = default_storage.open(file_path, 'wb')
                    r2_file.write(file_content)
                    r2_file.close()

                    # Verify upload
                    if default_storage.exists(file_path):
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✅ Migrated: {file_path}')
                        )
                        migrated_count += 1

                        # Delete local file if requested
                        if delete_local:
                            os.remove(local_path)
                            self.stdout.write(
                                self.style.SUCCESS(f'  🗑️  Deleted local: {local_path}')
                            )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Upload failed: {file_path}')
                        )
                        error_count += 1

                else:
                    # File doesn't exist locally, check if it's already in R2
                    if default_storage.exists(file_path):
                        self.stdout.write(
                            self.style.SUCCESS(f'  ⏭️  Already in R2: {file_path}')
                        )
                        skipped_count += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  File not found: {file_path}')
                        )
                        skipped_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error processing {doc.document_file.name}: {str(e)}')
                )
                error_count += 1

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Migration Summary:'))
        self.stdout.write(f'  Total documents: {total_docs}')
        self.stdout.write(f'  Migrated: {migrated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Errors: {error_count}')

        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('This was a dry run. Use --dry-run=False to perform actual migration.'))
        elif migrated_count > 0:
            self.stdout.write('\n' + self.style.SUCCESS('Migration completed successfully!'))
            if not delete_local:
                self.stdout.write(self.style.WARNING('Local files were kept. Use --delete-local to remove them after migration.'))

        self.stdout.write('='*50)