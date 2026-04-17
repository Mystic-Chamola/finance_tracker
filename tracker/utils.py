from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import Notification, Bill

def create_notification(user, title, message, notification_type, link=''):
    """Utility to create a notification for a user."""
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )

def check_budget_alerts(user, total_spent, budget_limit):
    """Check overall budget and create alert if exceeded."""
    if budget_limit > 0 and total_spent > budget_limit:
        existing = Notification.objects.filter(
            user=user,
            notification_type='budget_exceeded',
            is_read=False,
            created_at__month=timezone.now().month
        ).exists()
        if not existing:
            create_notification(
                user,
                "Monthly Budget Exceeded!",
                f"You've spent ${total_spent:.2f} which exceeds your monthly limit of ${budget_limit:.2f}.",
                'budget_exceeded',
                '/dashboard/'
            )

def check_category_budget_alerts(user, category_spent_dict, category_budgets):
    """Check per-category budgets and create alerts if exceeded."""
    today = timezone.now()
    for cat_code, limit in category_budgets.items():
        if limit > 0:
            spent = category_spent_dict.get(cat_code, 0)
            if spent > limit:
                existing = Notification.objects.filter(
                    user=user,
                    notification_type='category_budget_exceeded',
                    title__contains=cat_code,
                    is_read=False,
                    created_at__month=today.month
                ).exists()
                if not existing:
                    create_notification(
                        user,
                        f"Category Budget Exceeded: {cat_code}",
                        f"You've spent ${spent:.2f} on {cat_code}, exceeding your limit of ${limit:.2f}.",
                        'category_budget_exceeded',
                        '/dashboard/'
                    )

def check_bill_reminders(user):
    """Create notifications for bills due within reminder period."""
    today = timezone.now().date()
    bills = Bill.objects.filter(user=user, is_paid=False, due_date__gte=today)
    for bill in bills:
        reminder_date = bill.due_date - relativedelta(days=bill.reminder_days_before)
        if today >= reminder_date:
            existing = Notification.objects.filter(
                user=user,
                notification_type='bill_due',
                title__contains=bill.title,
                is_read=False,
                created_at__date=today
            ).exists()
            if not existing:
                create_notification(
                    user,
                    f"Bill Due: {bill.title}",
                    f"${bill.amount:.2f} is due on {bill.due_date.strftime('%b %d, %Y')}.",
                    'bill_due',
                    '/bills/'
                )