from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    CustomAuthToken, RegisterAPI, UserProfileViewSet, CurrencyViewSet,
    ExpenseViewSet, IncomeViewSet, BudgetViewSet, CategoryBudgetViewSet,
    SavingsGoalViewSet, SavingsContributionViewSet, BillViewSet,
    RecurringExpenseViewSet, NotificationViewSet, DashboardSummaryAPI
)

router = DefaultRouter()
router.register(r'profile', UserProfileViewSet, basename='profile')
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'incomes', IncomeViewSet, basename='income')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'category-budgets', CategoryBudgetViewSet, basename='categorybudget')
router.register(r'goals', SavingsGoalViewSet, basename='goal')
router.register(r'contributions', SavingsContributionViewSet, basename='contribution')
router.register(r'bills', BillViewSet, basename='bill')
router.register(r'recurring', RecurringExpenseViewSet, basename='recurring')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('auth/login/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('auth/register/', RegisterAPI.as_view(), name='api_register'),
    path('dashboard/summary/', DashboardSummaryAPI.as_view(), name='api_dashboard_summary'),
    path('', include(router.urls)),
]