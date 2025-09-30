from django.contrib import admin
from django import forms  # <-- added
from .models import Payment, Order, OrderProduct, PaymentSettings, DeliveryCharge


@admin.register(DeliveryCharge)
class DeliveryChargeAdmin(admin.ModelAdmin):
    list_display = ('location', 'charge', 'is_default', 'updated_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('location',)
    list_editable = ('charge', 'is_default')
    
    def save_model(self, request, obj, form, change):
        obj.location = obj.location.lower()  # Ensure lowercase
        super().save_model(request, obj, form, change)


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ('bkash_number', 'nagad_number', 'rocket_number', 'updated_at')
    fields = ('bkash_number', 'nagad_number', 'rocket_number')
    
    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # Show transaction_id and make it editable in list view
    list_display = (
        'payment_id', 'user', 'payment_method', 'payment_type',
        'amount_paid', 'transaction_id', 'status', 'is_approved', 'created_at'
    )
    list_filter = ('payment_method', 'payment_type', 'status', 'is_approved', 'created_at')
    search_fields = ('payment_id', 'transaction_id', 'user__email', 'user__first_name', 'user__last_name')

    # Editable right from the list page (cannot be the first column)
    list_editable = ('transaction_id', 'is_approved', 'status')

    # Keep these read-only in the detail form
    readonly_fields = ('payment_id', 'created_at')

    # Arrange fields in the detail form (includes transaction_id so staff can input it)
    fields = (
        'user',
        'payment_id',
        'payment_method',
        'payment_type',
        'amount_paid',
        'transaction_id',   # <- editable in the form
        'status',
        'is_approved',
        'created_at',
    )

    actions = ['approve_payments', 'reject_payments']

    def approve_payments(self, request, queryset):
        updated = queryset.update(is_approved=True, status='Approved')
        self.message_user(request, f"{updated} payments approved successfully.")
    approve_payments.short_description = "Approve selected payments"
    
    def reject_payments(self, request, queryset):
        updated = queryset.update(is_approved=False, status='Rejected')
        self.message_user(request, f"{updated} payments rejected.")
    reject_payments.short_description = "Reject selected payments"


class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = ('payment', 'user', 'product', 'quantity', 'product_price', 'ordered')
    extra = 0


# ----------------------- Added: Order admin form with editable "Transaction status" -----------------------

class OrderAdminForm(forms.ModelForm):
    TRANSACTION_STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Unpaid', 'Unpaid'),
        ('Paid (Delivery Charge)', 'Paid (Delivery Charge)'),
    ]
    transaction_status = forms.ChoiceField(
        choices=TRANSACTION_STATUS_CHOICES,
        required=False,
        label='Transaction status'
    )

    class Meta:
        model = Order
        fields = "__all__"

    def _auto_status_from_payment(self, payment):
        """
        Auto rules:
          - No payment or COD -> 'Unpaid'
          - Online + ADVANCE  -> 'Paid (Delivery Charge)'
          - Online + FULL     -> 'Paid'
        """
        if not payment:
            return 'Unpaid'
        if payment.payment_method == 'COD':
            return 'Unpaid'
        if payment.payment_type == 'ADVANCE':
            return 'Paid (Delivery Charge)'
        if payment.payment_type == 'FULL':
            return 'Paid'
        return 'Unpaid'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        payment = getattr(self.instance, 'payment', None)

        # If Payment.status already one of our display labels, use it; else auto-compute.
        if payment and (payment.status or '').strip().title() in dict(self.TRANSACTION_STATUS_CHOICES):
            self.fields['transaction_status'].initial = (payment.status or '').strip().title()
        else:
            self.fields['transaction_status'].initial = self._auto_status_from_payment(payment)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm  # <-- use the form with "transaction_status"

    list_display = [
        'order_number', 'full_name', 'phone', 'email', 'city',
        'delivery_charge', 'requires_advance', 'order_total',
        'status', 'is_ordered', 'created_at'
    ]
    list_filter = ['status', 'is_ordered', 'requires_advance', 'city', 'created_at']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email']
    list_per_page = 20
    inlines = [OrderProductInline]
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'ip', 'requires_advance', 'delivery_charge')
    list_editable = ['status']

    # Persist the selected "Transaction status" back to Payment.status
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        payment = getattr(obj, 'payment', None)
        picked = form.cleaned_data.get('transaction_status', None)
        if payment and picked:
            # Save exactly what admin chose: Paid / Unpaid / Paid (Delivery Charge)
            if (payment.status or '').strip().title() != picked:
                payment.status = picked
                payment.save(update_fields=['status'])
