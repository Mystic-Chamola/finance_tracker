from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password, ValidationError
from django.utils import timezone
from .models import Expense, Budget, RecurringExpense, SavingsGoal, SavingsContribution, Income, CategoryBudget, Bill, UserProfile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Please enter your email address.',
            'invalid': 'Enter a valid email address (e.g., name@example.com).',
        }
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username'
        self.fields['email'].label = 'Email Address'
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Confirm Password'
        self.fields['username'].help_text = 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
        self.fields['password1'].help_text = (
            'Your password must contain at least 8 characters, '
            'not be entirely numeric, and not be too common.'
        )

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if password1:
            try:
                validate_password(password1, self.instance)
            except ValidationError as e:
                friendly_messages = []
                for msg in e.messages:
                    if 'too short' in msg.lower():
                        friendly_messages.append('Password must be at least 8 characters long.')
                    elif 'entirely numeric' in msg.lower():
                        friendly_messages.append('Password cannot be entirely numeric.')
                    elif 'common' in msg.lower():
                        friendly_messages.append('Password is too common. Please choose a stronger one.')
                    elif 'similar' in msg.lower():
                        friendly_messages.append('Password is too similar to your username or email.')
                    else:
                        friendly_messages.append(msg)
                raise forms.ValidationError(friendly_messages)
        return password1

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The two password fields must match.')
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['date'] = timezone.now().date()


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['monthly_limit']
        labels = {'monthly_limit': 'Monthly Budget Limit'}


class CategoryBudgetForm(forms.ModelForm):
    class Meta:
        model = CategoryBudget
        fields = ['category', 'monthly_limit']
        widgets = {
            'monthly_limit': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class RecurringExpenseForm(forms.ModelForm):
    class Meta:
        model = RecurringExpense
        fields = ['title', 'amount', 'category', 'start_date', 'interval']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['start_date'] = timezone.now().date()


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['title', 'target_amount', 'deadline']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }


class SavingsContributionForm(forms.ModelForm):
    class Meta:
        model = SavingsContribution
        fields = ['amount', 'date', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['date'] = timezone.now().date()


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['title', 'amount', 'category', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['date'] = timezone.now().date()


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ['title', 'amount', 'due_date', 'is_recurring', 'recurring_interval', 'reminder_days_before']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['due_date'] = timezone.now().date()
        self.fields['recurring_interval'].required = False


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['preferred_currency', 'avatar', 'email_notifications', 'budget_alerts', 'bill_reminders', 'goal_achieved_alerts']
        widgets = {
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
        }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        help_texts = {
            'username': None,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].help_text = 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Current Password'
        self.fields['new_password1'].label = 'New Password'
        self.fields['new_password2'].label = 'Confirm New Password'
        self.fields['new_password1'].help_text = (
            'Your password must contain at least 8 characters, '
            'not be entirely numeric, and not be too common.'
        )


class DeleteAccountForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label='I understand that this action is permanent and cannot be undone.'
    )