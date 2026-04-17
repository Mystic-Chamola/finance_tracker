from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView 
from . import views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('add/', views.add_expense, name='add_expense'),
    path('edit/<int:pk>/', views.edit_expense, name='edit_expense'),
    path('delete/<int:pk>/', views.delete_expense, name='delete_expense'),
    path('set-budget/', views.set_budget, name='set_budget'),
    path('category-budgets/', views.manage_category_budgets, name='manage_category_budgets'),
    path('export/', views.export_csv, name='export_csv'),
    path('report/', views.generate_report, name='generate_report'),
    # Recurring
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/add/', views.recurring_add, name='recurring_add'),
    path('recurring/edit/<int:pk>/', views.recurring_edit, name='recurring_edit'),
    path('recurring/delete/<int:pk>/', views.recurring_delete, name='recurring_delete'),
    path('recurring/toggle/<int:pk>/', views.recurring_toggle, name='recurring_toggle'),
    # Goals
    path('goals/', views.goal_list, name='goal_list'),
    path('goals/add/', views.goal_add, name='goal_add'),
    path('goals/<int:pk>/', views.goal_detail, name='goal_detail'),
    path('goals/<int:pk>/edit/', views.goal_edit, name='goal_edit'),
    path('goals/<int:pk>/delete/', views.goal_delete, name='goal_delete'),
    path('goals/<int:pk>/contribute/', views.goal_contribute, name='goal_contribute'),
    # Income
    path('income/', views.income_list, name='income_list'),
    path('income/add/', views.income_add, name='income_add'),
    path('income/edit/<int:pk>/', views.income_edit, name='income_edit'),
    path('income/delete/<int:pk>/', views.income_delete, name='income_delete'),
    # Bills
    path('bills/', views.bill_list, name='bill_list'),
    path('bills/add/', views.bill_add, name='bill_add'),
    path('bills/edit/<int:pk>/', views.bill_edit, name='bill_edit'),
    path('bills/delete/<int:pk>/', views.bill_delete, name='bill_delete'),
    path('bills/mark-paid/<int:pk>/', views.bill_mark_paid, name='bill_mark_paid'),
    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
    # Profile & Settings
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/password/', views.change_password, name='change_password'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    # Currency
    path('set-currency/', views.set_currency, name='set_currency'),
    # Offline fallback (PWA)
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
]