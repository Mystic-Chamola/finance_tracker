import pytest
from django.urls import reverse
from tracker.tests.factories import UserFactory, ExpenseFactory, IncomeFactory, BudgetFactory, SavingsGoalFactory, BillFactory

@pytest.mark.django_db
class TestDashboardView:
    def test_dashboard_requires_login(self, client):
        response = client.get(reverse('dashboard'))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_dashboard_authenticated(self, client):
        user = UserFactory()
        client.force_login(user)
        ExpenseFactory(user=user, amount=100)
        IncomeFactory(user=user, amount=500)
        BudgetFactory(user=user, monthly_limit=1000)
        response = client.get(reverse('dashboard'))
        assert response.status_code == 200
        assert 'total_spent' in response.context
        assert response.context['total_spent'] == 100
        assert response.context['total_income'] == 500
        assert response.context['net_savings'] == 400


@pytest.mark.django_db
class TestIncomeViews:
    def test_income_list_authenticated(self, client):
        user = UserFactory()
        client.force_login(user)
        IncomeFactory.create_batch(3, user=user)
        response = client.get(reverse('income_list'))
        assert response.status_code == 200
        assert 'page_obj' in response.context
        assert len(response.context['page_obj']) == 3

    def test_income_add(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post(reverse('income_add'), {
            'title': 'Freelance',
            'amount': 1000,
            'category': 'Freelance',
            'date': '2026-04-17'
        })
        assert response.status_code == 302
        from tracker.models import Income
        assert Income.objects.filter(user=user, title='Freelance').exists()


@pytest.mark.django_db
class TestBillViews:
    def test_bill_list_authenticated(self, client):
        user = UserFactory()
        client.force_login(user)
        BillFactory.create_batch(2, user=user)
        response = client.get(reverse('bill_list'))
        assert response.status_code == 200
        assert 'page_obj' in response.context
        assert len(response.context['page_obj']) == 2

    def test_bill_mark_paid(self, client):
        user = UserFactory()
        client.force_login(user)
        bill = BillFactory(user=user, is_paid=False)
        response = client.post(reverse('bill_mark_paid', args=[bill.id]))
        assert response.status_code == 302
        bill.refresh_from_db()
        assert bill.is_paid is True


@pytest.mark.django_db
class TestGoalViews:
    def test_goal_list_authenticated(self, client):
        user = UserFactory()
        client.force_login(user)
        SavingsGoalFactory.create_batch(2, user=user)
        response = client.get(reverse('goal_list'))
        assert response.status_code == 200
        assert 'page_obj' in response.context
        assert len(response.context['page_obj']) == 2

    def test_goal_contribute(self, client):
        user = UserFactory()
        client.force_login(user)
        goal = SavingsGoalFactory(user=user, target_amount=1000, current_amount=0)
        response = client.post(reverse('goal_contribute', args=[goal.id]), {
            'amount': 500,
            'date': '2026-04-17',
            'note': 'Test'
        })
        assert response.status_code == 302
        goal.refresh_from_db()
        assert goal.current_amount == 500
        assert goal.is_completed is False

        response = client.post(reverse('goal_contribute', args=[goal.id]), {
            'amount': 600,
            'date': '2026-04-18',
            'note': ''
        })
        goal.refresh_from_db()
        assert goal.current_amount == 1100
        assert goal.is_completed is True