from django.contrib import admin
from .models import Product, Variation

class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'price', 'stock', 'category', 'created_date', 'modified_date', 'is_available')
    prepopulated_fields = {'slug': ('product_name',)}
    search_fields = ('product_name', 'category__category_name')   # 🔍 quick search
    list_filter = ('category', 'is_available', 'created_date')    # 📊 filtering options
    ordering = ('-created_date',)   

class VariationAdmin(admin.ModelAdmin):   
    list_display = ('product', 'variation_category', 'variation_value', 'is_active', 'created_date')
    list_editable = ('is_active',)
    list_filter = ('product', 'variation_category', 'variation_value', 'is_active')



admin.site.register(Product, ProductAdmin)
admin.site.register(Variation,VariationAdmin)
