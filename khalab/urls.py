#khalab/urls.py
from django.contrib import admin
from django.urls import path,include
from khalab import views
from django.conf.urls.static import static
from django.conf import settings
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home,name='home'),  
    path('store/', include('store.urls')),
    path('cart/',include('carts.urls')),
    path('accounts/',include('accounts.urls')),
    path('about-us/', views.aboutUs),
    path('category/<int:categoryid>', views.Category),
    path('orders/', include(('orders.urls', 'orders'), namespace='orders')),
    path('cart/', include('carts.urls')),
    
    #orders
    path('orders/',include('orders.urls')),
    path('courier/', include('courier.urls')),
] + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)