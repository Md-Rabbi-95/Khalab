# D:\Django\khalab\orders\models.py
from decimal import Decimal
from django.db import models
from accounts.models import Account
from store.models import Product, Variation


class DeliveryCharge(models.Model):
    location = models.CharField(max_length=100, unique=True, help_text="City/Location name")
    charge = models.DecimalField(max_digits=10, decimal_places=2, help_text="Delivery charge for this location")
    is_default = models.BooleanField(default=False, help_text="Default charge for unlisted locations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Charge"
        verbose_name_plural = "Delivery Charges"
        ordering = ['location']

    def __str__(self):
        if self.is_default:
            return f"Default: Tk. {self.charge}"
        return f"{self.location}: Tk. {self.charge}"

    def save(self, *args, **kwargs):
        # Normalize for consistent matching
        if self.location:
            self.location = self.location.lower()
        # Ensure only one default exists
        if self.is_default:
            DeliveryCharge.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PaymentSettings(models.Model):
    bkash_number = models.CharField(max_length=20, default="01XXXXXXXXX")
    nagad_number = models.CharField(max_length=20, default="01XXXXXXXXX")
    rocket_number = models.CharField(max_length=20, default="01XXXXXXXXX")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Settings"
        verbose_name_plural = "Payment Settings"

    def __str__(self):
        return f"Payment Settings (Updated: {self.updated_at})"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and PaymentSettings.objects.exists():
            raise ValueError("Only one PaymentSettings instance is allowed")
        super().save(*args, **kwargs)


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('BKASH', 'Bkash'),
        ('NAGAD', 'Nagad'),
        ('ROCKET', 'Rocket'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('FULL', 'Full Payment'),
        ('ADVANCE', 'Delivery Charge Only'),
    ]

    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='FULL')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=100, default='Pending')
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """
        Display logic:
        - COD: show 'COD – Cash on Delivery' (no UUIDs).
        - Online with trx id: '<trx> – <Method>'.
        - Otherwise: '<payment_id> – <Method>'.
        """
        method_display = dict(self.PAYMENT_METHOD_CHOICES).get(self.payment_method, self.payment_method)
        if self.payment_method == 'COD':
            return f"COD – {method_display}"
        tid = (self.transaction_id or "").strip()
        return f"{tid} – {method_display}" if tid else f"{self.payment_id} – {method_display}"

    def save(self, *args, **kwargs):
        # Normalize transaction_id
        if self.transaction_id is not None:
            self.transaction_id = self.transaction_id.strip()
        # Never keep a transaction_id for COD
        if self.payment_method == 'COD':
            self.transaction_id = ''
        super().save(*args, **kwargs)


class Order(models.Model):
    STATUS = (
        ('New', 'New'),
        ('Accept', 'Accept'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    order_number = models.CharField(max_length=20)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    email = models.CharField(max_length=50)
    address_line_1 = models.CharField(max_length=50)
    address_line_2 = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    order_note = models.CharField(max_length=100, blank=True)

    # ---- Money fields (use Decimal + safe defaults) ----
    order_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=10, choices=STATUS, default='New')
    ip = models.CharField(blank=True, max_length=20)
    is_ordered = models.BooleanField(default=False)
    requires_advance = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=False, auto_now=True)

    # ------- Convenience helpers -------
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'.strip()

    def items_subtotal(self):
        """Sum of all OrderProduct line totals (Decimal)."""
        total = Decimal("0.00")
        for op in self.orderproduct_set.all():
            total += (op.product_price or Decimal("0.00")) * Decimal(op.quantity or 0)
        return total

    def get_delivery_charge(self):
        """Calculate delivery charge based on city."""
        try:
            dc = DeliveryCharge.objects.get(location=(self.city or "").lower())
            return dc.charge
        except DeliveryCharge.DoesNotExist:
            try:
                default_dc = DeliveryCharge.objects.get(is_default=True)
                return default_dc.charge
            except DeliveryCharge.DoesNotExist:
                return Decimal("150.00")  # Fallback if no default is set

    def update_totals(self, commit=True):
        """
        Recalculate delivery_charge (based on city) and order_total
        from current OrderProduct lines. Optionally save the order.
        """
        self.delivery_charge = self.get_delivery_charge()
        sub_total = self.items_subtotal()
        self.order_total = (sub_total + (self.delivery_charge or Decimal("0.00")))
        if commit:
            self.save(update_fields=["delivery_charge", "order_total"])
        return self.order_total

    def save(self, *args, **kwargs):
        # Refresh delivery charge and outside-Dhaka flag
        self.delivery_charge = self.get_delivery_charge()
        city_norm = (self.city or "").lower()
        self.requires_advance = bool(city_norm and city_norm != 'dhaka')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_number} ({self.full_name()})"


class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_products', null=True, blank=True)
    variations = models.ManyToManyField(Variation, blank=True)
    quantity = models.IntegerField()
    # Use Decimal for currency
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def line_total(self):
        price = self.product_price or Decimal("0.00")
        qty = Decimal(self.quantity or 0)
        return price * qty

    def __str__(self):
        return getattr(self.product, "product_name", "Order Product")
