from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import secrets
from datetime import timedelta


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', db_index=True)
    preferred_currency = models.CharField(max_length=3, default='USD')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    email_notifications = models.BooleanField(default=True)
    budget_alerts = models.BooleanField(default=True)
    bill_reminders = models.BooleanField(default=True)
    goal_achieved_alerts = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, db_index=True)
    name = models.CharField(max_length=50)
    rate_to_usd = models.DecimalField(max_digits=12, decimal_places=6)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Currencies'

    def __str__(self):
        return f"{self.code} - {self.rate_to_usd}"


class Budget(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_index=True)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.user.username}'s Budget"


class CategoryBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    category = models.CharField(max_length=20, choices=[
        ('Food', 'Food'), ('Transport', 'Transport'), ('Entertainment', 'Entertainment'),
        ('Rent', 'Rent'), ('Shopping', 'Shopping'), ('Utilities', 'Utilities'), ('Other', 'Other'),
    ], db_index=True)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ['user', 'category']
        ordering = ['category']

    def __str__(self):
        return f"{self.user.username} - {self.category}: ${self.monthly_limit}"


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('Food', 'Food'), ('Transport', 'Transport'), ('Entertainment', 'Entertainment'),
        ('Rent', 'Rent'), ('Shopping', 'Shopping'), ('Utilities', 'Utilities'), ('Other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    date = models.DateField(db_index=True)
    recurring_source = models.ForeignKey('RecurringExpense', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"


class RecurringExpense(models.Model):
    INTERVAL_CHOICES = [
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=Expense.CATEGORY_CHOICES, db_index=True)
    start_date = models.DateField(default=timezone.now)
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default='monthly')
    next_due = models.DateField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.next_due:
            self.next_due = self.start_date
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.interval})"

    def create_expense(self):
        Expense.objects.create(
            user=self.user, title=self.title, amount=self.amount,
            category=self.category, date=self.next_due, recurring_source=self
        )
        if self.interval == 'daily':
            self.next_due += relativedelta(days=1)
        elif self.interval == 'weekly':
            self.next_due += relativedelta(weeks=1)
        elif self.interval == 'monthly':
            self.next_due += relativedelta(months=1)
        elif self.interval == 'yearly':
            self.next_due += relativedelta(years=1)
        self.save()


class SavingsGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    title = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.title} - {self.current_amount}/{self.target_amount}"

    def progress_percentage(self):
        if self.target_amount > 0:
            return min(100, (self.current_amount / self.target_amount) * 100)
        return 0

    def remaining(self):
        return max(0, self.target_amount - self.current_amount)


class SavingsContribution(models.Model):
    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name='contributions', db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now, db_index=True)
    note = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.amount} to {self.goal.title} on {self.date}"


class Income(models.Model):
    CATEGORY_CHOICES = [
        ('Salary', 'Salary'), ('Freelance', 'Freelance'), ('Gift', 'Gift'),
        ('Investment', 'Investment'), ('Refund', 'Refund'), ('Other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    date = models.DateField(db_index=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"


class Bill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(db_index=True)
    is_paid = models.BooleanField(default=False, db_index=True)
    is_recurring = models.BooleanField(default=False)
    recurring_interval = models.CharField(max_length=10, choices=RecurringExpense.INTERVAL_CHOICES, blank=True, null=True)
    reminder_days_before = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - Due: {self.due_date}"

    def is_due_soon(self):
        today = timezone.now().date()
        reminder_date = self.due_date - relativedelta(days=self.reminder_days_before)
        return not self.is_paid and today >= reminder_date and today <= self.due_date

    def mark_paid_and_create_next(self):
        self.is_paid = True
        self.save()
        if self.is_recurring and self.recurring_interval:
            next_due = self.due_date
            if self.recurring_interval == 'daily':
                next_due += relativedelta(days=1)
            elif self.recurring_interval == 'weekly':
                next_due += relativedelta(weeks=1)
            elif self.recurring_interval == 'monthly':
                next_due += relativedelta(months=1)
            elif self.recurring_interval == 'yearly':
                next_due += relativedelta(years=1)
            Bill.objects.create(
                user=self.user, title=self.title, amount=self.amount,
                due_date=next_due, is_recurring=True, recurring_interval=self.recurring_interval,
                reminder_days_before=self.reminder_days_before
            )


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('budget_exceeded', 'Budget Exceeded'),
        ('category_budget_exceeded', 'Category Budget Exceeded'),
        ('bill_due', 'Bill Due Soon'),
        ('goal_achieved', 'Goal Achieved'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    title = models.CharField(max_length=100)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    link = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class EmailVerificationToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.expires_at > timezone.now()

    def __str__(self):
        return f"Verification token for {self.user.email}"