# courier/urls.py
from django.urls import path
from . import views

app_name = 'courier'

urlpatterns = [
    # Create REDX parcel for an order
    path('redx/create/<int:order_id>/', views.create_redx_parcel, name='create_redx_parcel'),
    
    # Track existing parcel
    path('redx/track/<int:parcel_id>/', views.track_parcel, name='track_parcel'),
    
    # Cancel parcel
    path('redx/cancel/<int:parcel_id>/', views.cancel_parcel, name='cancel_parcel'),
]