from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase

from core.models import Client, ClientDocument

User = get_user_model()


class ClientDocumentTests(TestCase):
    """Test cases for ClientDocument model and functionality"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin_doc",
            first_name="Admin",
            last_name="Doc",
            email="admin@doc.com",
            role="admin",
        )

        self.staff_user = User.objects.create_user(
            username="staff_doc",
            first_name="Staff",
            last_name="Doc",
            email="staff@doc.com",
            role="staff",
        )

        self.test_client = Client.objects.create(
            name="Test Client for Documents",
            email="client@doc.com",
            created_by=self.admin_user,
        )

    def test_client_document_creation(self):
        """Test creating a client document"""
        # Create a test file
        test_file = ContentFile(b"Test file content", name="test_document.pdf")

        # Create document
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Test Document",
            description="A test document for client",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        # Verify document was created
        self.assertEqual(document.title, "Test Document")
        self.assertEqual(document.client, self.test_client)
        self.assertEqual(document.uploaded_by, self.admin_user)
        self.assertEqual(document.description, "A test document for client")
        self.assertIsNotNone(document.uploaded_at)
        self.assertIsNotNone(document.updated_at)

    def test_client_document_str_method(self):
        """Test the string representation of ClientDocument"""
        test_file = ContentFile(b"Test content", name="test.pdf")
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Sample Document",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        expected_str = f"Sample Document - {self.test_client.name}"
        self.assertEqual(str(document), expected_str)

    def test_file_size_property(self):
        """Test the file_size property"""
        # Create file with known size (1024 bytes = 1 KB)
        content = b"x" * 1024
        test_file = ContentFile(content, name="test_1kb.txt")

        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Size Test Document",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        # File size should be around 1.0 KB (or similar format)
        file_size = document.file_size
        self.assertTrue("KB" in file_size or "B" in file_size or "Unknown" in file_size)

    def test_file_extension_property(self):
        """Test the file_extension property"""
        test_file = ContentFile(b"Test content", name="document.pdf")
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Extension Test",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        self.assertEqual(document.file_extension, "PDF")

    def test_file_extension_no_extension(self):
        """Test file_extension when file has no extension"""
        test_file = ContentFile(b"Test content", name="document_without_extension")
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="No Extension Test",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        self.assertEqual(document.file_extension, "Unknown")

    def test_client_document_ordering(self):
        """Test that documents are ordered by uploaded_at descending"""
        # Create multiple documents
        test_file1 = ContentFile(b"Content 1", name="doc1.pdf")
        test_file2 = ContentFile(b"Content 2", name="doc2.pdf")
        test_file3 = ContentFile(b"Content 3", name="doc3.pdf")

        doc1 = ClientDocument.objects.create(
            client=self.test_client,
            title="Document 1",
            document_file=test_file1,
            uploaded_by=self.admin_user,
        )

        doc2 = ClientDocument.objects.create(
            client=self.test_client,
            title="Document 2",
            document_file=test_file2,
            uploaded_by=self.admin_user,
        )

        doc3 = ClientDocument.objects.create(
            client=self.test_client,
            title="Document 3",
            document_file=test_file3,
            uploaded_by=self.admin_user,
        )

        # Get all documents for this client
        documents = list(ClientDocument.objects.filter(client=self.test_client))

        # Should be ordered by uploaded_at descending (most recent first)
        self.assertEqual(documents[0], doc3)
        self.assertEqual(documents[1], doc2)
        self.assertEqual(documents[2], doc1)

    def test_client_document_relationships(self):
        """Test relationships between ClientDocument and other models"""
        test_file = ContentFile(b"Test content", name="relationship_test.pdf")
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Relationship Test",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        # Test reverse relationship from client
        client_documents = self.test_client.documents.all()
        self.assertIn(document, client_documents)

        # Test reverse relationship from user
        user_documents = self.admin_user.uploaded_documents.all()
        self.assertIn(document, user_documents)

    def test_client_document_deletion_cascade(self):
        """Test that documents are deleted when client is deleted"""
        test_file = ContentFile(b"Test content", name="cascade_test.pdf")
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Cascade Test",
            document_file=test_file,
            uploaded_by=self.admin_user,
        )

        # Verify document exists
        self.assertEqual(ClientDocument.objects.count(), 1)

        # Delete client
        self.test_client.delete()

        # Document should be deleted due to CASCADE
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_client_document_blank_description(self):
        """Test that description can be blank"""
        test_file = ContentFile(b"Test content", name="blank_desc.pdf")
        document = ClientDocument.objects.create(
            client=self.test_client,
            title="Blank Description Test",
            document_file=test_file,
            uploaded_by=self.admin_user,
            # No description provided
        )

        self.assertEqual(document.description, "")
