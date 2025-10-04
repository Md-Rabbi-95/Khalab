# orders/models.py
from decimal import Decimal
from django.db import models
from accounts.models import Account
from store.models import Product, Variation
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from django.db import models, transaction


class DeliveryCharge(models.Model):
    district = models.CharField(max_length=100, unique=True, help_text="District name")
    charge = models.DecimalField(max_digits=10, decimal_places=2, help_text="Delivery charge for this district")
    is_default = models.BooleanField(default=False, help_text="Default charge for unlisted districts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Charge"
        verbose_name_plural = "Delivery Charges"
        ordering = ['district']

    def __str__(self):
        if self.is_default:
            return f"Default: Tk. {self.charge}"
        return f"{self.district}: Tk. {self.charge}"

    def save(self, *args, **kwargs):
        if self.district:
            self.district = self.district.strip()
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

    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid (Delivery Charge)', 'Paid (Delivery Charge)'),
        ('Paid (Full)', 'Paid (Full)'),
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Refunded', 'Refunded'),
    ]

    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='FULL')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default='Pending')
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        method_display = dict(self.PAYMENT_METHOD_CHOICES).get(self.payment_method, self.payment_method)
        if self.payment_method == 'COD':
            return f"COD – {method_display}"
        tid = (self.transaction_id or "").strip()
        return f"{tid} – {method_display}" if tid else f"{self.payment_id} – {method_display}"

    def save(self, *args, **kwargs):
        if self.transaction_id is not None:
            self.transaction_id = self.transaction_id.strip()
        if self.payment_method == 'COD':
            self.transaction_id = ''
            # Auto-set status for COD if not already set
            if not self.pk and not self.status:
                self.status = 'Unpaid'
        super().save(*args, **kwargs)


class Order(models.Model):
    STATUS = (
        ('Pending', 'Pending'),
        ('Accept', 'Accept'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )

    PAYMENT_STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid (Full)', 'Paid (Full)'),
        ('Paid (Delivery Charge)', 'Paid (Delivery Charge)'),
        ('Refunded', 'Refunded'),
    ]

    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    order_number = models.CharField(max_length=20)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    email = models.CharField(max_length=50)
    address_line_1 = models.CharField(max_length=50)
    address_line_2 = models.CharField(max_length=50, blank=True)
    area = models.CharField(max_length=100, blank=True, help_text="Area/locality within district")
    country = models.CharField(max_length=50)
    state = models.CharField(max_length=50)  # This is the district
    order_note = models.CharField(max_length=100, blank=True)

    order_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    collected_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00"),
        help_text="Amount to be collected from customer (Total - Online Payment)"
    )

    status = models.CharField(max_length=10, choices=STATUS, default='New')
    ip = models.CharField(blank=True, max_length=45)
    
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default='Unpaid',
        help_text="Track payment progress (editable by admin)."
    )

    is_ordered = models.BooleanField(default=False)
    requires_advance = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self):
        parts = [self.address_line_1, self.address_line_2, self.area]
        return ' '.join(p.strip() for p in parts if p and p.strip())

    def items_subtotal(self):
        total = Decimal("0.00")
        for op in self.orderproduct_set.all():
            total += (op.product_price or Decimal("0.00")) * Decimal(op.quantity or 0)
        return total

    def get_delivery_charge(self):
        """Calculate delivery charge based on district (state field)."""
        try:
            dc = DeliveryCharge.objects.get(district__iexact=(self.state or "").strip())
            return dc.charge
        except DeliveryCharge.DoesNotExist:
            try:
                default_dc = DeliveryCharge.objects.get(is_default=True)
                return default_dc.charge
            except DeliveryCharge.DoesNotExist:
                return Decimal("150.00")

    def calculate_collected_amount(self):
        if not self.payment:
            return self.order_total
        
        # COD: collect everything on delivery
        if self.payment.payment_method == 'COD':
            return self.order_total
        
        # Online payment: subtract what was already paid online
        amount_already_paid = self.payment.amount_paid or Decimal("0.00")
        amount_to_collect = self.order_total - amount_already_paid
        
        # Never return negative (in case of overpayment)
        return max(Decimal("0.00"), amount_to_collect)

    def update_totals(self, commit=True):
        self.delivery_charge = self.get_delivery_charge()
        sub_total = self.items_subtotal()
        self.order_total = (sub_total + (self.delivery_charge or Decimal("0.00")))
        self.collected_amount = self.calculate_collected_amount()
        if commit:
            self.save(update_fields=["delivery_charge", "order_total", "collected_amount"])
        return self.order_total

    def save(self, *args, **kwargs):
        self.delivery_charge = self.get_delivery_charge()
        district_norm = (self.state or "").strip().lower()
        self.requires_advance = bool(district_norm and district_norm != 'dhaka')

        # Detect status change (against DB value) BEFORE saving
        if self.pk:
            try:
                old = Order.objects.only('status').get(pk=self.pk)
                status_changed = (old.status != self.status)
            except Order.DoesNotExist:
                status_changed = False
        else:
            status_changed = False

        # Persist
        super().save(*args, **kwargs)
        
        # Calculate collected amount AFTER order is saved (so payment is available)
        new_collected = self.calculate_collected_amount()
        if new_collected != self.collected_amount:
            self.collected_amount = new_collected
            Order.objects.filter(pk=self.pk).update(collected_amount=new_collected)

        # Send email AFTER successful save if status changed
        if status_changed:
            self.send_status_update_email()
            
    def send_status_update_email(self):
        subject = f'Order {self.order_number} Status Update'
        context = {
            'order': self,
            'status': self.get_status_display(),
            'domain': getattr(settings, 'SITE_URL', 'https://yourdomain.com'),
            'now': timezone.now(),
        }
        html_body = render_to_string('orders/order_status_email.html', context)
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[self.email],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()

    def __str__(self):
        return f"Order {self.order_number} ({self.full_name()})"
    
    @property
    def admin_payment_status(self) -> str:
        """
        Returns the exact Payment.status stored in DB (editable in admin).
        Falls back to a reasonable default when missing.
        """
        if not self.payment:
            return "Unpaid"
        status = (self.payment.status or "").strip()
        return status if status else "Unpaid"

    @property
    def admin_payment_status_badge(self) -> str:
        s = self.admin_payment_status.lower()
        if any(k in s for k in ("paid (delivery", "delivery charge")):
            return "primary"
        if any(k in s for k in ("paid (full)", "paid", "approved", "success", "completed")):
            return "success"
        if any(k in s for k in ("unpaid", "pending", "await", "process", "hold")):
            return "warning text-dark"
        if any(k in s for k in ("reject", "fail", "cancel", "void", "refunded", "chargeback")):
            return "danger"
        return "secondary"
    
    @property
    def payment_status_label(self) -> str:
        """
        Replicates your template logic, driven by Payment.status first.
        Falls back to payment_method / payment_type when needed.
        """
        payment = getattr(self, 'payment', None)
        if not payment:
            return "Unpaid"

        ps = (payment.status or "").strip().lower()
        method = (payment.payment_method or "").strip().upper()
        ptype = (payment.payment_type or "").strip().upper()

        if ps == "paid (full)":
            return "Paid (Full)"
        if ps == "paid (delivery charge)":
            return "Paid (Delivery Charge)"
        if ps == "unpaid":
            return "Unpaid"

        if method == "COD":
            return "Unpaid"
        if ptype == "FULL":
            return "Paid (Full)"
        if ptype == "ADVANCE":
            return "Paid (Delivery Charge)"

        if any(k in ps for k in ("refund", "chargeback", "reject", "fail", "cancel")):
            return payment.status or "Unpaid"
        if any(k in ps for k in ("pending", "hold", "await", "review", "process")):
            return payment.status or "Unpaid"
        if any(k in ps for k in ("approve", "complete", "success")):
            return payment.status or "Paid (Full)"

        return payment.status or "Unpaid"

    @property
    def payment_status_badge(self) -> str:
        label = (self.payment_status_label or "").lower()
        if "paid (full)" in label:
            return "bg-success"
        if "paid (delivery charge)" in label:
            return "bg-primary"
        if label == "unpaid":
            return "bg-warning text-dark"

        if any(k in label for k in ("refund", "chargeback", "reject", "fail", "cancel")):
            return "bg-danger"
        if any(k in label for k in ("pending", "hold", "await", "review", "process")):
            return "bg-warning text-dark"
        if any(k in label for k in ("approve", "complete", "success")):
            return "bg-success"

        return "bg-secondary"


class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_products', null=True, blank=True)
    variations = models.ManyToManyField(Variation, blank=True)
    quantity = models.IntegerField()
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
    
    class Meta:
        verbose_name = 'Order Product'
        verbose_name_plural = 'Order Products'