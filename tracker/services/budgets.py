import logging
from django.db import transaction, DatabaseError
from ..models import Budget, CategoryBudget, Expense
from ..forms import BudgetForm
from ..audit import log_audit

logger = logging.getLogger(__name__)


class BudgetService:
    def __init__(self, user):
        self.user = user

    def get_global_budget(self):
        obj, _ = Budget.objects.get_or_create(user=self.user, defaults={'monthly_limit': 0})
        return obj

    def update_global_budget(self, data):
        budget = self.get_global_budget()
        form = BudgetForm(data, instance=budget)
        if not form.is_valid():
            return False, form.errors

        try:
            form.save()
            log_audit(self.user, 'BUDGET_UPDATED', f'Limit: {budget.monthly_limit}')
            return True, None
        except DatabaseError as e:
            logger.error(f"Database error updating budget: {e}")
            return False, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error updating budget")
            return False, {'__all__': ['An unexpected error occurred.']}

    def get_category_budgets(self):
        categories = Expense.CATEGORY_CHOICES
        for cat_code, _ in categories:
            CategoryBudget.objects.get_or_create(user=self.user, category=cat_code, defaults={'monthly_limit': 0})
        return CategoryBudget.objects.filter(user=self.user).order_by('category')

    def update_category_budgets(self, data):
        category_budgets = self.get_category_budgets()
        try:
            with transaction.atomic():
                for budget in category_budgets:
                    limit_key = f'limit_{budget.category}'
                    if limit_key in data:
                        new_limit = float(data[limit_key])
                        budget.monthly_limit = max(0, new_limit)
                        budget.save()
            log_audit(self.user, 'CATEGORY_BUDGETS_UPDATED')
            return True, None
        except ValueError:
            return False, {'__all__': ['Invalid budget value.']}
        except DatabaseError as e:
            logger.error(f"Database error updating category budgets: {e}")
            return False, {'__all__': ['A database error occurred.']}
        except Exception as e:
            logger.exception("Unexpected error updating category budgets")
            return False, {'__all__': ['An unexpected error occurred.']}