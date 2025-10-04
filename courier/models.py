# courier/models.py
from django.db import models
from orders.models import Order
from django.conf import settings

class REDXConfiguration(models.Model):
    """Store REDX API configuration"""
    MODE_CHOICES = (
        ('sandbox', 'Sandbox'),
        ('production', 'Production'),
    )
    
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='sandbox')
    sandbox_base_url = models.CharField(max_length=255, default='https://sandbox.redx.com.bd/v1.0.0-beta')
    sandbox_token = models.TextField()
    production_base_url = models.CharField(max_length=255, default='https://openapi.redx.com.bd/v1.0.0-beta')
    production_token = models.TextField()
    
    # Store Information (auto-filled in parcel)
    store_name = models.CharField(max_length=255, default='Your Store Name')
    store_phone = models.CharField(max_length=20, default='01XXXXXXXXX')
    store_address = models.TextField(default='Your Store Address')
    store_area = models.CharField(max_length=100, default='Dhaka')
    store_district = models.CharField(max_length=100, default='Dhaka')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'REDX Configuration'
        verbose_name_plural = 'REDX Configurations'
    
    def __str__(self):
        return f"REDX Config - {self.mode}"
    
    def get_base_url(self):
        """Get the appropriate base URL based on mode"""
        if self.mode == 'production':
            return self.production_base_url
        return self.sandbox_base_url
    
    def get_token(self):
        """Get the appropriate token based on mode"""
        if self.mode == 'production':
            return self.production_token
        return self.sandbox_token


class REDXParcel(models.Model):
    """Store REDX parcel/shipment information"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('created', 'Created'),
        ('picked', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    )
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='redx_parcel')
    tracking_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Customer Info
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=20)
    customer_address = models.TextField()
    customer_area = models.CharField(max_length=100)
    customer_district = models.CharField(max_length=100)
    
    # Parcel Info
    parcel_weight = models.DecimalField(max_digits=6, decimal_places=2, help_text='Weight in KG')
    cash_collection_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # REDX Response Data
    redx_response = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'REDX Parcel'
        verbose_name_plural = 'REDX Parcels'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Parcel #{self.order.order_number} - {self.tracking_id or 'No Tracking'}"