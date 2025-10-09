# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Account, UserProfile

class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    search_fields = ('email', 'first_name', 'last_name', 'username')
    readonly_fields = ('date_joined', 'last_login')
    ordering = ('-date_joined',)
    filter_horizontal = ()
    list_filter = ('is_active', 'is_admin')
    fieldsets = ()

class UserProfileAdmin(admin.ModelAdmin):
    @admin.display(description='Profile Picture')
    def thumbnail(self, obj: UserProfile):
        img = getattr(obj, 'profile_picture', None)

        # Only attempt to read .url if a file is actually present
        if img:
            try:
                if hasattr(img, 'url') and img.name:   # img.name implies a stored file
                    return format_html(
                        '<img src="{}" width="30" height="30" '
                        'style="border-radius:50%; object-fit:cover;" />',
                        img.url
                    )
            except ValueError:
                # No file associated; fall through to placeholder
                pass

        # Fallback placeholder (no external assets needed)
        return format_html(
            '<div style="width:30px;height:30px;border-radius:50%;'
            'background:#e5e7eb;display:inline-block;text-align:center;'
            'line-height:30px;font-size:11px;color:#6b7280;">—</div>'
        )

    list_display = ('thumbnail', 'user', 'area', 'city', 'country')

admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)

