import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from tracker.models import (
    Budget, Expense, Income, SavingsGoal, Bill, RecurringExpense, Notification
)
from tracker.tests.factories import (
    UserFactory, ExpenseFactory, IncomeFactory, SavingsGoalFactory,
    BillFactory, RecurringExpenseFactory, NotificationFactory
)

@pytest.mark.django_db
class TestExpenseModel:
    def test_expense_creation(self):
        expense = ExpenseFactory()
        assert expense.id is not None
        assert str(expense) == f"{expense.title} - {expense.amount}"

    def test_expense_user_required(self):
        with pytest.raises(Exception):
            Expense.objects.create(title='Test', amount=100, category='Food', date=timezone.now())

@pytest.mark.django_db
class TestSavingsGoalModel:
    def test_progress_percentage(self):
        goal = SavingsGoalFactory(target_amount=1000, current_amount=250)
        assert goal.progress_percentage() == 25.0

    def test_remaining(self):
        goal = SavingsGoalFactory(target_amount=1000, current_amount=250)
        assert goal.remaining() == 750

    def test_progress_percentage_zero_target(self):
        goal = SavingsGoalFactory(target_amount=0, current_amount=100)
        assert goal.progress_percentage() == 0

@pytest.mark.django_db
class TestBillModel:
    def test_is_due_soon(self):
        bill = BillFactory(due_date=timezone.now().date() + relativedelta(days=2))
        assert bill.is_due_soon() is True

        bill.due_date = timezone.now().date() + relativedelta(days=10)
        bill.save()
        assert bill.is_due_soon() is False

    def test_mark_paid_and_create_next(self):
        bill = BillFactory(is_recurring=True, recurring_interval='monthly')
        bill.mark_paid_and_create_next()
        assert bill.is_paid is True
        next_bill = Bill.objects.filter(title=bill.title, is_paid=False).first()
        assert next_bill is not None
        assert next_bill.due_date == bill.due_date + relativedelta(months=1)

@pytest.mark.django_db
class TestRecurringExpenseModel:
    def test_create_expense(self):
        recurring = RecurringExpenseFactory()
        recurring.create_expense()
        expense = Expense.objects.filter(recurring_source=recurring).first()
        assert expense is not None
        assert expense.amount == recurring.amount
        assert recurring.next_due == recurring.start_date + relativedelta(months=1)