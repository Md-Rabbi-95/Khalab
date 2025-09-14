from django.shortcuts import render, redirect
from django.http import HttpResponse
from carts.models import CartItem
from .forms import OrderForm
from .models import Order
import datetime

# <<< add:
from django.db.models import Q
from carts.views import _cart_id


def payments(request):
    return render(request,'orders/payments.html')

def place_order(request, total=0, quantity=0):
    current_user = request.user

    # if the cart count is less than or equal to 0, then redirect back to shop
    # <<< adopt any session cart items to the logged-in user (no behavioral change for guests)
    if request.user.is_authenticated:
        CartItem.objects.filter(
            cart__cart_id=_cart_id(request),
            user__isnull=True
        ).update(user=request.user)

    # <<< look up items by user OR session cart_id (covers both logged-in and guest)
    cart_items = CartItem.objects.filter(
        Q(user=request.user) | Q(cart__cart_id=_cart_id(request))
    ).distinct()

    if not cart_items.exists():
        return redirect('store')

    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():

            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']              # <<< fix (was stae)
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total                       # <<< fix (was total)
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')

            # <<< ensure non-empty order_number for first save (keeps your logic)
            data.order_number = datetime.date.today().strftime("%Y%m%d")
            data.save()

            # Generate order number (your original approach, just using correct datetime)
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            order = Order.objects.get(user=current_user,is_ordered=False,order_number=order_number)
            context = {
                'order': order,
                'cart_items':cart_items,
                'total': total,
                'tax': tax,
                'grand_total': grand_total
                
            }
            #print("ORDER SAVED ID =", data.id)                   

            return render(request,'orders/payments.html',context)
        else:
            return redirect('checkout')
