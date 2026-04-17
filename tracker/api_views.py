from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Expense, Income, Budget, CategoryBudget, SavingsGoal,
    SavingsContribution, Bill, RecurringExpense, Notification,
    UserProfile, Currency
)
from .serializers import (
    UserSerializer, RegisterSerializer, UserProfileSerializer,
    ExpenseSerializer, IncomeSerializer, BudgetSerializer,
    CategoryBudgetSerializer, SavingsGoalSerializer, SavingsContributionSerializer,
    BillSerializer, RecurringExpenseSerializer, NotificationSerializer,
    CurrencySerializer, DashboardSummarySerializer
)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Only allow owners to edit their objects."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class CustomAuthToken(ObtainAuthToken):
    """Login endpoint returning token and user data."""
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
        })


class RegisterAPI(generics.CreateAPIView):
    """User registration endpoint."""
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    """Current user's profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

    def get_object(self):
        return self.get_queryset().first()

    @action(detail=False, methods=['GET', 'PUT', 'PATCH'])
    def me(self, request):
        profile = self.get_object()
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        else:
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """Public exchange rates."""
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'date']

    def get_queryset(self):
        queryset = Expense.objects.filter(user=self.request.user)
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        if year and month:
            queryset = queryset.filter(date__year=year, date__month=month)
        elif year:
            queryset = queryset.filter(date__year=year)
        return queryset.order_by('-date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class IncomeViewSet(viewsets.ModelViewSet):
    serializer_class = IncomeSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'date']

    def get_queryset(self):
        queryset = Income.objects.filter(user=self.request.user)
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        if year and month:
            queryset = queryset.filter(date__year=year, date__month=month)
        elif year:
            queryset = queryset.filter(date__year=year)
        return queryset.order_by('-date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)

    def get_object(self):
        obj, _ = Budget.objects.get_or_create(user=self.request.user, defaults={'monthly_limit': 0})
        return obj

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryBudgetViewSet(viewsets.ModelViewSet):
    serializer_class = CategoryBudgetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return CategoryBudget.objects.filter(user=self.request.user).order_by('category')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavingsGoalViewSet(viewsets.ModelViewSet):
    serializer_class = SavingsGoalSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return SavingsGoal.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavingsContributionViewSet(viewsets.ModelViewSet):
    serializer_class = SavingsContributionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavingsContribution.objects.filter(goal__user=self.request.user).order_by('-date')


class BillViewSet(viewsets.ModelViewSet):
    serializer_class = BillSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_paid', 'due_date']

    def get_queryset(self):
        return Bill.objects.filter(user=self.request.user).order_by('is_paid', 'due_date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['POST'])
    def mark_paid(self, request, pk=None):
        bill = self.get_object()
        bill.mark_paid_and_create_next()
        return Response({'status': 'paid', 'next_due': bill.next_due if hasattr(bill, 'next_due') else None})


class RecurringExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = RecurringExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return RecurringExpense.objects.filter(user=self.request.user).order_by('-is_active', 'next_due')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['POST'])
    def toggle(self, request, pk=None):
        recurring = self.get_object()
        recurring.is_active = not recurring.is_active
        recurring.save()
        return Response({'is_active': recurring.is_active})


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['POST'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'all marked read'})

    @action(detail=True, methods=['POST'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'read'})


class DashboardSummaryAPI(generics.GenericAPIView):
    """Aggregated dashboard data."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DashboardSummarySerializer

    def get(self, request):
        user = request.user
        now = timezone.now()
        year = request.query_params.get('year', now.year)
        month = request.query_params.get('month', now.month)
        try:
            year = int(year)
            month = int(month)
        except ValueError:
            year, month = now.year, now.month

        income_total = Income.objects.filter(user=user, date__year=year, date__month=month).aggregate(t=Sum('amount'))['t'] or 0
        expense_total = Expense.objects.filter(user=user, date__year=year, date__month=month).aggregate(t=Sum('amount'))['t'] or 0
        budget_obj = Budget.objects.filter(user=user).first()
        budget_limit = budget_obj.monthly_limit if budget_obj else 0
        net_savings = income_total - expense_total
        remaining = budget_limit - expense_total
        over_budget = remaining < 0

        category_data = Expense.objects.filter(user=user, date__year=year, date__month=month) \
            .values('category').annotate(total=Sum('amount')).order_by('-total')
        category_breakdown = [
            {'category': item['category'], 'total': float(item['total'])}
            for item in category_data
        ]

        start_date = timezone.now().date().replace(year=year, month=month, day=1) - relativedelta(months=5)
        monthly_exp = Expense.objects.filter(user=user, date__gte=start_date) \
            .extra(select={'month': "strftime('%%Y-%%m', date)"}) \
            .values('month').annotate(total=Sum('amount')).order_by('month')
        monthly_inc = Income.objects.filter(user=user, date__gte=start_date) \
            .extra(select={'month': "strftime('%%Y-%%m', date)"}) \
            .values('month').annotate(total=Sum('amount')).order_by('month')
        monthly_trends = {
            'expenses': {item['month']: float(item['total']) for item in monthly_exp},
            'income': {item['month']: float(item['total']) for item in monthly_inc},
        }

        upcoming_bills = Bill.objects.filter(user=user, is_paid=False, due_date__gte=now.date()).count()
        active_goals = SavingsGoal.objects.filter(user=user, is_completed=False).count()
        unread_notifications = Notification.objects.filter(user=user, is_read=False).count()

        data = {
            'total_income': income_total,
            'total_spent': expense_total,
            'net_savings': net_savings,
            'budget_limit': budget_limit,
            'remaining_budget': remaining,
            'over_budget': over_budget,
            'category_breakdown': category_breakdown,
            'monthly_trends': monthly_trends,
            'upcoming_bills_count': upcoming_bills,
            'active_goals_count': active_goals,
            'unread_notifications_count': unread_notifications,
        }
        serializer = self.get_serializer(data)
        return Response(serializer.data)