from django.urls import path
from . import views

urlpatterns = [
    path('', views.store, name='store'),
    path('category/<slug:category_slug>/', views.store, name = 'products_by_category'),
    path('category/<slug:category_slug>/<slug:product_slug>/', views.product_detail, name='product_detail'),
    path('search/',views.search,name='search'),
    path('submit_review/<int:product_id>/',views.submit_review, name='submit_review'),
    path("about/", views.about, name="about"),
    path("find-store/", views.find_store, name="find_store"),
    path("return-policy/", views.return_policy, name="return_policy"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("user-info-legal/", views.user_info_legal, name="user_info_legal"),
    path("terms-of-use/", views.terms_of_use, name="terms_of_use"),
]
