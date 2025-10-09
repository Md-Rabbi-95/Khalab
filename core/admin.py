# core/admin.py
from django.contrib import admin

# ========================================
# Django Admin Site Customization
# ========================================

# Site Branding
admin.site.site_header = "Khalab Admin Dashboard"
admin.site.site_title = "Khalab Admin"
admin.site.index_title = "Welcome to Khalab Administration"

# Disable default Django sidebar (we're using custom sidebar from base_site.html)
admin.site.enable_nav_sidebar = False

