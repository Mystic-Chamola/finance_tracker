from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Expense, Income, Budget, CategoryBudget, SavingsGoal,
    SavingsContribution, Bill, RecurringExpense, Notification,
    UserProfile, Currency
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        Budget.objects.create(user=user, monthly_limit=0)
        UserProfile.objects.create(user=user, preferred_currency='USD')
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'preferred_currency', 'avatar', 'email_notifications',
                  'budget_alerts', 'bill_reminders', 'goal_achieved_alerts']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'rate_to_usd', 'updated_at']


class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Expense
        fields = ['id', 'title', 'amount', 'category', 'category_display', 'date', 'recurring_source']
        read_only_fields = ['user', 'recurring_source']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class IncomeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Income
        fields = ['id', 'title', 'amount', 'category', 'category_display', 'date']
        read_only_fields = ['user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = ['id', 'monthly_limit']
        read_only_fields = ['user']


class CategoryBudgetSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = CategoryBudget
        fields = ['id', 'category', 'category_display', 'monthly_limit']
        read_only_fields = ['user']


class SavingsGoalSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()

    class Meta:
        model = SavingsGoal
        fields = ['id', 'title', 'target_amount', 'current_amount', 'deadline',
                  'created_at', 'is_completed', 'progress_percentage', 'remaining']
        read_only_fields = ['user', 'current_amount', 'is_completed']

    def get_progress_percentage(self, obj):
        return obj.progress_percentage()

    def get_remaining(self, obj):
        return obj.remaining()

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SavingsContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsContribution
        fields = ['id', 'goal', 'amount', 'date', 'note']

    def create(self, validated_data):
        contribution = super().create(validated_data)
        goal = contribution.goal
        goal.current_amount += contribution.amount
        if goal.current_amount >= goal.target_amount:
            goal.is_completed = True
        goal.save()
        return contribution


class BillSerializer(serializers.ModelSerializer):
    is_due_soon = serializers.SerializerMethodField()
    recurring_interval_display = serializers.CharField(source='get_recurring_interval_display', read_only=True)

    class Meta:
        model = Bill
        fields = ['id', 'title', 'amount', 'due_date', 'is_paid', 'is_recurring',
                  'recurring_interval', 'recurring_interval_display', 'reminder_days_before',
                  'created_at', 'is_due_soon']
        read_only_fields = ['user']

    def get_is_due_soon(self, obj):
        return obj.is_due_soon()

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class RecurringExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    interval_display = serializers.CharField(source='get_interval_display', read_only=True)

    class Meta:
        model = RecurringExpense
        fields = ['id', 'title', 'amount', 'category', 'category_display',
                  'start_date', 'interval', 'interval_display', 'next_due',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['user', 'next_due']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['next_due'] = validated_data['start_date']
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'notification_type_display',
                  'is_read', 'created_at', 'link']
        read_only_fields = ['user']


class DashboardSummarySerializer(serializers.Serializer):
    """Aggregated dashboard data."""
    total_income = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_savings = serializers.DecimalField(max_digits=10, decimal_places=2)
    budget_limit = serializers.DecimalField(max_digits=10, decimal_places=2)
    remaining_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    over_budget = serializers.BooleanField()
    category_breakdown = serializers.ListField(child=serializers.DictField())
    monthly_trends = serializers.DictField()
    upcoming_bills_count = serializers.IntegerField()
    active_goals_count = serializers.IntegerField()
    unread_notifications_count = serializers.IntegerField()