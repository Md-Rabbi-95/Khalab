from django.conf import settings

def contact_info(request):
    return {
        "contact_email": getattr(settings, "CONTACT_EMAIL", "rabbim913@gmail.com"),
        "contact_phone": getattr(settings, "CONTACT_PHONE", "01790360352"),
    }
