from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.choices import UserRoles
from core.models import Client

User = get_user_model()


class ClientAPITests(TestCase):
    """Test cases for Client API endpoints"""

    def setUp(self):
        """Set up test data and API client"""
        self.client = APIClient()

        # Create test users
        self.admin_user = User.objects.create_user(
            username="admin_client",
            first_name="Admin",
            last_name="Client",
            email="admin@client.com",
            role=UserRoles.ADMIN,
        )

        self.staff_user = User.objects.create_user(
            username="staff_client",
            first_name="Staff",
            last_name="Client",
            email="staff@client.com",
            role=UserRoles.STAFF,
        )

        # Create test clients with various data for search testing
        self.client1 = Client.objects.create(
            name="ABC Corporation",
            contact_person="John Smith",
            email="john@abc.com",
            phone="123-456-7890",
            address="123 Main St, City, State",
            created_by=self.admin_user,
        )

        self.client2 = Client.objects.create(
            name="XYZ Industries",
            contact_person="Jane Doe",
            email="jane@xyz.com",
            phone="987-654-3210",
            address="456 Oak Ave, Town, State",
            created_by=self.admin_user,
        )

        self.client3 = Client.objects.create(
            name="Tech Solutions Ltd",
            contact_person="Bob Johnson",
            email="bob@techsolutions.com",
            phone="555-123-4567",
            address="789 Pine Rd, Village, State",
            created_by=self.staff_user,
        )

        self.client4 = Client.objects.create(
            name="Global Enterprises",
            contact_person="Alice Brown",
            email="alice@global.com",
            phone="111-222-3333",
            address="321 Elm St, Metro, State",
            created_by=self.staff_user,
        )

    def test_search_by_name_exact_match(self):
        """Test search by client name with exact match"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "ABC Corporation"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return only the matching client
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "ABC Corporation")

    def test_search_by_name_partial_match(self):
        """Test search by client name with partial match"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "Corp"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return ABC Corporation
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "ABC Corporation")

    def test_search_by_name_case_insensitive(self):
        """Test search by client name is case insensitive"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "abc corporation"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return ABC Corporation
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "ABC Corporation")

    def test_search_by_contact_person(self):
        """Test search by contact_person field"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "John Smith"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return ABC Corporation
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["contact_person"], "John Smith")

    def test_search_by_email(self):
        """Test search by email field"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "jane@xyz.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return XYZ Industries
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "jane@xyz.com")

    def test_search_by_email_partial(self):
        """Test search by email field with partial match"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "@xyz.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return XYZ Industries
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "jane@xyz.com")

    def test_search_by_phone(self):
        """Test search by phone field"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "555-123-4567"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return Tech Solutions Ltd
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["phone"], "555-123-4567")

    def test_search_by_address(self):
        """Test search by address field"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "Main St"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return ABC Corporation
        self.assertEqual(response.data["count"], 1)
        self.assertIn("Main St", response.data["results"][0]["address"])

    def test_search_multiple_results(self):
        """Test search that returns multiple results"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "State"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return all clients (all addresses contain 'State')
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 4)

    def test_search_no_results(self):
        """Test search that returns no results"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "nonexistent"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return no results
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_with_pagination(self):
        """Test search functionality with pagination"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "State", "page": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should have pagination metadata
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_search_staff_user_permissions(self):
        """Test that staff users can only see clients they created"""
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get("/api/clients/", {"search": "Tech Solutions"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Staff user should see Tech Solutions Ltd (created by them)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Tech Solutions Ltd")

    def test_search_staff_user_cannot_see_others_clients(self):
        """Test that staff users cannot see clients created by others"""
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get("/api/clients/", {"search": "ABC Corporation"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Staff user should not see ABC Corporation (created by admin)
        self.assertEqual(response.data["count"], 0)

    def test_search_admin_user_sees_all_clients(self):
        """Test that admin users can see all clients"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "Ltd"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Admin should see Tech Solutions Ltd
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Tech Solutions Ltd")

    def test_search_empty_string(self):
        """Test search with empty string returns all clients for admin"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return all clients
        self.assertEqual(response.data["count"], 4)

    def test_search_unauthenticated_user(self):
        """Test that unauthenticated users cannot access clients endpoint"""
        response = self.client.get("/api/clients/", {"search": "test"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_special_characters(self):
        """Test search with special characters"""
        # Create a client with special characters in name
        special_client = Client.objects.create(
            name="Test & Co.",
            contact_person="Special User",
            email="special@test.com",
            phone="999-888-7777",
            address="Special Address",
            created_by=self.admin_user,
        )

        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "&"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return the special client
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Test & Co.")

    def test_search_numeric_values(self):
        """Test search with numeric values in phone"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/clients/", {"search": "456-7890"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return ABC Corporation (phone contains 456-7890)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "ABC Corporation")
