import pytest
from django.urls import reverse
from tracker.tests.factories import UserFactory, IncomeFactory

@pytest.mark.django_db
class TestTemplateRendering:
    def test_income_list_template(self, client):
        user = UserFactory()
        client.force_login(user)
        IncomeFactory.create_batch(2, user=user)
        response = client.get(reverse('income_list'))
        assert response.status_code == 200
        assert 'tracker/income_list.html' in [t.name for t in response.templates]
        content = response.content.decode()
        assert '💰 No income recorded yet' not in content
        assert 'Add Your First Income' not in content

    def test_empty_income_list_shows_message(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse('income_list'))
        content = response.content.decode()
        assert '💰 No income recorded yet' in content
        assert 'Add Your First Income' in content