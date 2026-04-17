from django.core.management.base import BaseCommand
from django.utils import timezone
from tracker.models import RecurringExpense

class Command(BaseCommand):
    help = 'Create expense entries for due recurring expenses'

    def handle(self, *args, **options):
        today = timezone.now().date()
        due_recurrings = RecurringExpense.objects.filter(
            is_active=True,
            next_due__lte=today
        )

        count = 0
        for rec in due_recurrings:
            rec.create_expense()
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} recurring expenses.'))