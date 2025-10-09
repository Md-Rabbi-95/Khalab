# D:\Django\khalab\orders\urls.py
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('place_order/', views.place_order, name='place_order'),
    path('payments/',views.payments,name="payments"),
    path('order_complete/',views.order_complete,name='order_complete'),
]


