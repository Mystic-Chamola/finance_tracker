import pytest
from django.contrib.auth.models import User
from tracker.forms import RegisterForm, ExpenseForm, IncomeForm, BillForm

@pytest.mark.django_db
class TestRegisterForm:
    def test_valid_registration(self):
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!'
        })
        assert form.is_valid()

    def test_password_mismatch(self):
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'WrongPass123!'
        })
        assert not form.is_valid()
        assert 'password2' in form.errors

    def test_password_too_short(self):
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'short',
            'password2': 'short'
        })
        assert not form.is_valid()
        assert 'password1' in form.errors


@pytest.mark.django_db
class TestExpenseForm:
    def test_valid_expense(self):
        form = ExpenseForm(data={
            'title': 'Groceries',
            'amount': 50.00,
            'category': 'Food',
            'date': '2026-04-17'
        })
        assert form.is_valid()

    def test_negative_amount(self):
        form = ExpenseForm(data={
            'title': 'Groceries',
            'amount': -50.00,
            'category': 'Food',
            'date': '2026-04-17'
        })
        assert not form.is_valid()
        assert 'amount' in form.errors


@pytest.mark.django_db
class TestIncomeForm:
    def test_valid_income(self):
        form = IncomeForm(data={
            'title': 'Salary',
            'amount': 5000.00,
            'category': 'Salary',
            'date': '2026-04-17'
        })
        assert form.is_valid()

    def test_negative_amount(self):
        form = IncomeForm(data={
            'title': 'Salary',
            'amount': -100.00,
            'category': 'Salary',
            'date': '2026-04-17'
        })
        assert not form.is_valid()
        assert 'amount' in form.errors


@pytest.mark.django_db
class TestBillForm:
    def test_valid_bill(self):
        form = BillForm(data={
            'title': 'Rent',
            'amount': 1200.00,
            'due_date': '2026-05-01',
            'reminder_days_before': 3
        })
        assert form.is_valid()

    def test_negative_amount(self):
        form = BillForm(data={
            'title': 'Rent',
            'amount': -50.00,
            'due_date': '2026-05-01',
            'reminder_days_before': 3
        })
        assert not form.is_valid()
        assert 'amount' in form.errors