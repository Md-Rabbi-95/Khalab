from django.contrib import admin
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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
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


@admin.register(OrderProduct)
class OrderProductAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'user', 'quantity', 'product_price', 'ordered', 'created_at']
    list_filter = ['ordered', 'created_at']
    search_fields = ['order__order_number', 'product__product_name', 'user__email']
