#category/views.py
from django.http import HttpResponse
from django.shortcuts import render

def home(request):
     data= {
         'title': 'Khalab'
     }
     return render(request,"index.html",data)