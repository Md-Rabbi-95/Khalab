# courier/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import REDXConfiguration, REDXParcel


@admin.register(REDXConfiguration)
class REDXConfigurationAdmin(admin.ModelAdmin):
    list_display = ('mode', 'store_name', 'store_phone', 'is_active', 'created_at')
    list_filter = ('mode', 'is_active')
    search_fields = ('store_name', 'store_phone')
    
    fieldsets = (
        ('Mode Selection', {
            'fields': ('mode', 'is_active'),
            'description': 'Select Sandbox for testing or Production for live operations'
        }),
        ('Sandbox Configuration', {
            'fields': ('sandbox_base_url', 'sandbox_token'),
            'classes': ('collapse',),
            'description': 'Configuration for testing environment'
        }),
        ('Production Configuration', {
            'fields': ('production_base_url', 'production_token'),
            'classes': ('collapse',),
            'description': 'Configuration for live environment'
        }),
        ('Store Information', {
            'fields': ('store_name', 'store_phone', 'store_address', 'store_area', 'store_district'),
            'description': 'Your store details for pickup and sender information'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Ensure only one config is active at a time
        if obj.is_active:
            REDXConfiguration.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(REDXParcel)
class REDXParcelAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'tracking_id_display',
        'customer_name',
        'customer_phone',
        'status_badge',
        'cash_collection_amount',
        'created_at',
        'actions_buttons'
    )
    list_filter = ('status', 'created_at', 'customer_district')
    search_fields = ('tracking_id', 'customer_name', 'customer_phone', 'order__order_number')
    readonly_fields = ('tracking_id', 'redx_response', 'error_message', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'tracking_id', 'status')
        }),
        ('Customer Information', {
            'fields': ('customer_name', 'customer_phone', 'customer_address', 'customer_area', 'customer_district')
        }),
        ('Parcel Details', {
            'fields': ('parcel_weight', 'cash_collection_amount', 'delivery_charge')
        }),
        ('REDX Response', {
            'fields': ('redx_response', 'error_message'),
            'classes': ('collapse',),
            'description': 'Raw response data from REDX API'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def order_number(self, obj):
        """Display order number"""
        return obj.order.order_number
    order_number.short_description = 'Order #'
    
    def tracking_id_display(self, obj):
        """Display tracking ID with styling"""
        if obj.tracking_id:
            return format_html(
                '<strong style="color: #0ea5e9;">{}</strong>',
                obj.tracking_id
            )
        return format_html('<span style="color: #999;">Not Generated</span>')
    tracking_id_display.short_description = 'Tracking ID'
    
    def status_badge(self, obj):
        """Display status with color-coded badge"""
        colors = {
            'pending': '#fbbf24',
            'created': '#3b82f6',
            'picked': '#8b5cf6',
            'in_transit': '#0ea5e9',
            'delivered': '#10b981',
            'cancelled': '#ef4444',
            'failed': '#dc2626',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def actions_buttons(self, obj):
        """Display action buttons for tracking"""
        if obj.tracking_id:
            track_url = reverse('courier:track_parcel', args=[obj.id])
            
            buttons = []
            
            # Track button
            buttons.append(format_html(
                '<a class="button" href="{}" target="_blank" style="margin-right: 5px; background: #0ea5e9; color: white; padding: 5px 12px; border-radius: 4px; text-decoration: none; display: inline-block;">📍 Track</a>',
                track_url
            ))
            
            # Note: Cancel not available via API
            if obj.status not in ['cancelled', 'delivered']:
                buttons.append(format_html(
                    '<span style="color: #6b7280; font-size: 11px; font-style: italic;">Cancel via REDX Dashboard</span>'
                ))
            
            return format_html(' '.join(buttons))
        return format_html('<span style="color: #999; font-style: italic;">No actions available</span>')
    actions_buttons.short_description = 'Actions'
    
    def has_add_permission(self, request):
        """Disable manual adding - parcels should be created through orders"""
        return False

