import requests
from decimal import Decimal, InvalidOperation, getcontext
from django.core.management.base import BaseCommand
from tracker.models import Currency

# Set high precision for parsing
getcontext().prec = 30

class Command(BaseCommand):
    help = 'Fetch latest exchange rates from exchangerate-api.com (free tier)'

    def clean_rate_string(self, value):
        """Convert any numeric value to a clean string suitable for Decimal."""
        if value is None:
            return None
        s = str(value).strip()
        s = s.replace(',', '')
        s = s.replace('\u00a0', '').replace('\u202f', '')
        s = ''.join(c for c in s if c.isdigit() or c in '.-+eE')
        return s

    def fit_to_model_precision(self, value):
        """
        Adjust Decimal to fit max_digits=12, decimal_places=6.
        If the number is too large, truncate decimal places.
        If still too large, keep only the most significant digits.
        """
        # Maximum allowed digits = 12, with 6 decimal places
        # That means max integer part = 6 digits (12-6)
        max_digits = 12
        decimal_places = 6
        max_integer_digits = max_digits - decimal_places

        # Convert to string without scientific notation
        str_val = format(value, 'f')
        if '.' in str_val:
            int_part, frac_part = str_val.split('.')
        else:
            int_part, frac_part = str_val, ''

        # If integer part already exceeds allowed digits, truncate it drastically
        if len(int_part) > max_integer_digits:
            # Keep only the first max_integer_digits digits, drop the rest (set to zero)
            int_part = int_part[:max_integer_digits]
            frac_part = '0' * decimal_places
        else:
            # Truncate fractional part to 6 digits
            frac_part = (frac_part + '0' * decimal_places)[:decimal_places]

        adjusted_str = f"{int_part}.{frac_part}"
        return Decimal(adjusted_str)

    def handle(self, *args, **options):
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            rates = data.get('rates', {})

            updated_count = 0
            skipped_count = 0

            for code, rate in rates.items():
                clean_str = self.clean_rate_string(rate)
                if not clean_str:
                    self.stderr.write(f"Skipping {code}: empty after cleaning")
                    skipped_count += 1
                    continue

                try:
                    parsed = Decimal(clean_str)
                except InvalidOperation:
                    self.stderr.write(f"Skipping {code}: cannot parse '{clean_str}'")
                    skipped_count += 1
                    continue

                try:
                    # Fit to model precision
                    safe_rate = self.fit_to_model_precision(parsed)
                except Exception as e:
                    self.stderr.write(f"Skipping {code}: failed to fit precision - {e}")
                    skipped_count += 1
                    continue

                Currency.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': code,
                        'rate_to_usd': safe_rate
                    }
                )
                updated_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} exchange rates (skipped {skipped_count})'
                )
            )

        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f'Network error: {e}'))
        except Exception as e:
            import traceback
            self.stderr.write(self.style.ERROR(f'Unexpected error: {e}'))
            self.stderr.write(traceback.format_exc())