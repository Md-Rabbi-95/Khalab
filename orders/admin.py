# orders/admin.py
'''
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django import forms
from .models import Payment, Order, OrderProduct, PaymentSettings, DeliveryCharge


@admin.register(DeliveryCharge)
class DeliveryChargeAdmin(admin.ModelAdmin):
    list_display = ('district', 'charge', 'is_default', 'updated_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('district',)
    list_editable = ('charge', 'is_default')
    
    def save_model(self, request, obj, form, change):
        if obj.district:
            obj.district = obj.district.strip()  # Clean whitespace
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
    list_display = (
        'payment_id', 'user', 'payment_method', 'payment_type',
        'amount_paid', 'transaction_id', 'status', 'is_approved', 'created_at'
    )
    list_filter = ('payment_method', 'payment_type', 'status', 'is_approved', 'created_at')
    search_fields = ('payment_id', 'transaction_id', 'user__email', 'user__first_name', 'user__last_name')
    list_editable = ('transaction_id', 'is_approved', 'status')
    readonly_fields = ('payment_id', 'created_at')
    
    fields = (
        'user',
        'payment_id',
        'payment_method',
        'payment_type',
        'amount_paid',
        'transaction_id',
        'status',
        'payment_status',
        'is_approved',
        'created_at',
        'redx_parcel_button',
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

        if payment and (payment.status or '').strip().title() in dict(self.TRANSACTION_STATUS_CHOICES):
            self.fields['transaction_status'].initial = (payment.status or '').strip().title()
        else:
            self.fields['transaction_status'].initial = self._auto_status_from_payment(payment)


# orders/admin.py (append to your existing OrderAdmin)
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # ... your existing config ...
    actions = ['mark_status_new', 'mark_status_accept', 'mark_status_completed', 'mark_status_cancelled']
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # If admin edited Order.payment_status, mirror it to Payment.status
        if obj.payment and hasattr(obj, 'payment_status'):
            # keep the same exact labels you use in admin
            desired = (obj.payment_status or '').strip()
            if desired and (obj.payment.status or '').strip() != desired:
                obj.payment.status = desired
                obj.payment.save(update_fields=['status'])

    def _bulk_set_status(self, request, queryset, status_value, human_label):
        count = 0
        for order in queryset:
            old = order.status
            if old != status_value:
                order.status = status_value
                # Trigger Order.save() which will send email on change
                order.save(update_fields=['status', 'updated_at'])
                count += 1
        self.message_user(request, f"{count} order(s) marked as {human_label} and customers notified.")

    def mark_status_new(self, request, queryset):
        self._bulk_set_status(request, queryset, 'New', 'New')
    mark_status_new.short_description = "Set status to New (sends email)"

    def mark_status_accept(self, request, queryset):
        self._bulk_set_status(request, queryset, 'Accept', 'Accept')
    mark_status_accept.short_description = "Set status to Accept (sends email)"

    def mark_status_completed(self, request, queryset):
        self._bulk_set_status(request, queryset, 'Completed', 'Completed')
    mark_status_completed.short_description = "Set status to Completed (sends email)"

    def mark_status_cancelled(self, request, queryset):
        self._bulk_set_status(request, queryset, 'Cancelled', 'Cancelled')
    mark_status_cancelled.short_description = "Set status to Cancelled (sends email)"

'''

# orders/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django import forms
from .models import Payment, Order, OrderProduct, PaymentSettings, DeliveryCharge


@admin.register(DeliveryCharge)
class DeliveryChargeAdmin(admin.ModelAdmin):
    list_display = ('district', 'charge', 'is_default', 'updated_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('district',)
    list_editable = ('charge', 'is_default')
    
    def save_model(self, request, obj, form, change):
        if obj.district:
            obj.district = obj.district.strip()  # Clean whitespace
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
    list_display = (
        'payment_id', 'user', 'payment_method', 'payment_type',
        'amount_paid', 'transaction_id', 'status', 'is_approved', 'created_at'
    )
    list_filter = ('payment_method', 'payment_type', 'status', 'is_approved', 'created_at')
    search_fields = ('payment_id', 'transaction_id', 'user__email', 'user__first_name', 'user__last_name')
    list_editable = ('transaction_id', 'is_approved', 'status')
    readonly_fields = ('payment_id', 'created_at')
    
    fields = (
        'user',
        'payment_id',
        'payment_method',
        'payment_type',
        'amount_paid',
        'transaction_id',
        'status',
        'payment_status',
        'is_approved',
        'created_at',
        'redx_parcel_button',
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

        if payment and (payment.status or '').strip().title() in dict(self.TRANSACTION_STATUS_CHOICES):
            self.fields['transaction_status'].initial = (payment.status or '').strip().title()
        else:
            self.fields['transaction_status'].initial = self._auto_status_from_payment(payment)


# ✅ Final OrderAdmin with redx_parcel_button integrated
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = ['mark_status_new', 'mark_status_accept', 'mark_status_completed', 'mark_status_cancelled']
    inlines = [OrderProductInline]

    list_display = (
        'order_number',
        'full_name',
        'phone',
        'email',
        'order_total',
        'collected_amount',
        'status',
        'is_ordered',
        'created_at',
        'redx_parcel_button',  # ✅ added parcel button column
    )
    list_filter = ['status', 'is_ordered', 'created_at']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email']
    list_per_page = 20
    readonly_fields = ('collected_amount',)

    # ✅ Add REDX courier button (create or track)
    def redx_parcel_button(self, obj):
        """Show REDX parcel creation/tracking button in admin."""
        if hasattr(obj, 'redx_parcel'):
            parcel = obj.redx_parcel
            track_url = reverse('courier:track_parcel', args=[parcel.id])
            status_colors = {
                'pending': '#fbbf24',
                'created': '#3b82f6',
                'picked': '#8b5cf6',
                'in_transit': '#0ea5e9',
                'delivered': '#10b981',
                'cancelled': '#ef4444',
                'failed': '#dc2626',
            }
            color = status_colors.get(parcel.status, '#6b7280')
            return format_html(
                '<a href="{}" target="_blank" style="background:{};color:white;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:600;">📦 {}</a>',
                track_url,
                color,
                parcel.tracking_id or 'Track Parcel'
            )
        else:
            create_url = reverse('courier:create_redx_parcel', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank" style="background:#10b981;color:white;padding:5px 10px;border-radius:4px;text-decoration:none;font-weight:600;">➕ Create REDX Parcel</a>',
                create_url
            )
    redx_parcel_button.short_description = 'REDX Courier'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.payment and hasattr(obj, 'payment_status'):
            desired = (obj.payment_status or '').strip()
            if desired and (obj.payment.status or '').strip() != desired:
                obj.payment.status = desired
                obj.payment.save(update_fields=['status'])

    def _bulk_set_status(self, request, queryset, status_value, human_label):
        count = 0
        for order in queryset:
            old = order.status
            if old != status_value:
                order.status = status_value
                order.save(update_fields=['status', 'updated_at'])
                count += 1
        self.message_user(request, f"{count} order(s) marked as {human_label} and customers notified.")

    def mark_status_new(self, request, queryset):
        self._bulk_set_status(request, queryset, 'New', 'New')
    mark_status_new.short_description = "Set status to New (sends email)"

    def mark_status_accept(self, request, queryset):
        self._bulk_set_status(request, queryset, 'Accept', 'Accept')
    mark_status_accept.short_description = "Set status to Accept (sends email)"

    def mark_status_completed(self, request, queryset):
        self._bulk_set_status(request, queryset, 'Completed', 'Completed')
    mark_status_completed.short_description = "Set status to Completed (sends email)"

    def mark_status_cancelled(self, request, queryset):
        self._bulk_set_status(request, queryset, 'Cancelled', 'Cancelled')
    mark_status_cancelled.short_description = "Set status to Cancelled (sends email)"
