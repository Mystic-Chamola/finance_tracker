import pytest
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from tracker.tests.factories import UserFactory, ExpenseFactory

@pytest.mark.django_db
class TestExpenseAPI:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        # Token is auto-created by signal, so get it
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_list_expenses(self):
        ExpenseFactory.create_batch(3, user=self.user)
        response = self.client.get('/api/expenses/')
        assert response.status_code == 200
        assert len(response.data['results']) == 3

    def test_create_expense(self):
        response = self.client.post('/api/expenses/', {
            'title': 'API Expense',
            'amount': 99.99,
            'category': 'Shopping',
            'date': '2026-04-17'
        })
        assert response.status_code == 201
        assert response.data['title'] == 'API Expense'

    def test_unauthenticated_access(self):
        client = APIClient()
        response = client.get('/api/expenses/')
        assert response.status_code == 401

@pytest.mark.django_db
class TestAuthAPI:
    def test_login(self):
        user = UserFactory()
        user.set_password('testpass123')
        user.save()
        client = APIClient()
        response = client.post('/api/auth/login/', {
            'username': user.username,
            'password': 'testpass123'
        })
        assert response.status_code == 200
        assert 'token' in response.data

    def test_register(self):
        client = APIClient()
        response = client.post('/api/auth/register/', {
            'username': 'apiuser',
            'email': 'api@example.com',
            'password': 'SecurePass123!'
        })
        assert response.status_code == 201
        from django.contrib.auth.models import User
        assert User.objects.filter(username='apiuser').exists()