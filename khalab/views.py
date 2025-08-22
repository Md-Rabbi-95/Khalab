from django.http import HttpResponse
from django.shortcuts import render
from store.models import Product

def home(request):
     products = Product.objects.all().filter(is_available=True)
     context = {
         'products': products,
     }
     return render(request,"home.html",context)

def aboutUs(request):
    return HttpResponse("<strong>Welcome to Khalab1</strong>")

def Category(request, categoryid):
    return HttpResponse(f"Welcome to Category Page and Category ID: {categoryid}")