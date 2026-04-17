import factory
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from tracker.models import (
    Budget, CategoryBudget, Expense, Income, SavingsGoal,
    SavingsContribution, Bill, RecurringExpense, Notification,
    UserProfile, Currency
)

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')

class UserProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    preferred_currency = 'USD'

class BudgetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Budget

    user = factory.SubFactory(UserFactory)
    monthly_limit = 1000.00

class CategoryBudgetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CategoryBudget

    user = factory.SubFactory(UserFactory)
    category = 'Food'
    monthly_limit = 300.00

class ExpenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Expense

    user = factory.SubFactory(UserFactory)
    title = factory.Faker('word')
    amount = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    category = 'Food'
    date = factory.LazyFunction(timezone.now)

class IncomeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Income

    user = factory.SubFactory(UserFactory)
    title = factory.Faker('word')
    amount = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    category = 'Salary'
    date = factory.LazyFunction(timezone.now)

class SavingsGoalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SavingsGoal

    user = factory.SubFactory(UserFactory)
    title = factory.Faker('sentence', nb_words=3)
    target_amount = 5000.00
    current_amount = 0

class SavingsContributionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SavingsContribution

    goal = factory.SubFactory(SavingsGoalFactory)
    amount = 500.00
    date = factory.LazyFunction(timezone.now)

class BillFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Bill

    user = factory.SubFactory(UserFactory)
    title = factory.Faker('word')
    amount = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    due_date = factory.LazyFunction(lambda: timezone.now().date() + relativedelta(days=7))

class RecurringExpenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RecurringExpense

    user = factory.SubFactory(UserFactory)
    title = factory.Faker('word')
    amount = 50.00
    category = 'Entertainment'
    start_date = factory.LazyFunction(timezone.now)
    interval = 'monthly'
    next_due = factory.LazyAttribute(lambda o: o.start_date)

class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    title = 'Test Notification'
    message = 'This is a test.'
    notification_type = 'system'

class CurrencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Currency

    code = 'USD'
    name = 'US Dollar'
    rate_to_usd = 1.0