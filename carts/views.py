from django.shortcuts import render,redirect
from store.models import Product,Variation
from .models import Cart,CartItem
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def _iter_selected_variations(product, data):
    """
    Yield Variation objects from POST data, skipping non-variation fields.
    """
    skip_keys = {"csrfmiddlewaretoken", "quantity"}
    for key, value in data.items():
        if key in skip_keys or not value:
            continue
        try:
            yield Variation.objects.get(
                product=product,
                variation_category__iexact=key,   # fixed typo here
                variation_value__iexact=value
            )
        except Variation.DoesNotExist:
            # Ignore keys that aren't valid variations for this product
            continue
    
def add_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    selected_variations = []
    if request.method == "POST":
        selected_variations = list(_iter_selected_variations(product, request.POST))

    # Get or create cart
    cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))

    # All cart items for this product in this cart
    cart_items_qs = CartItem.objects.filter(cart=cart, product=product)

    if selected_variations:
        # Compare by variation ID sets to find an identical combination
        desired_ids = sorted(v.id for v in selected_variations)
        matching_item = None
        for item in cart_items_qs:
            item_ids = sorted(item.variations.values_list("id", flat=True))
            if item_ids == desired_ids:
                matching_item = item
                break

        if matching_item:
            matching_item.quantity += 1
            matching_item.save()
        else:
            new_item = CartItem.objects.create(cart=cart, product=product, quantity=1)
            new_item.variations.add(*selected_variations)  # shows up in admin
    else:
        simple_item = cart_items_qs.filter(variations__isnull=True).first()
        if simple_item:
            simple_item.quantity += 1
            simple_item.save()
        else:
            CartItem.objects.create(cart=cart, product=product, quantity=1)

    return redirect('cart')


def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax=0
        grand_total = 0
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity
        tax = (2 * total)/100
        grand_total = total + tax
    except ObjectDoesNotExist:
        pass
    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax' : tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/cart.html', context)

def remove_cart(request, product_id,cart_item_id):
    cart = Cart.objects.get(cart_id=_cart_id(request))
    product = get_object_or_404(Product, id=product_id)

    try:
        cart_item = CartItem.objects.get(product=product, cart=cart,id=cart_item_id)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except CartItem.DoesNotExist:
        pass

    return redirect('cart')

def remove_cart_item(request, product_id,cart_item_id):
    cart = Cart.objects.get(cart_id=_cart_id(request))
    product = get_object_or_404(Product, id=product_id)
    CartItem.objects.filter(product=product, cart=cart,id=cart_item_id).delete()
    return redirect('cart')

@login_required
def checkout(request,total=0, quantity=0, cart_items=None):
    try:
        tax=0
        grand_total = 0
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity
        tax = (2 * total)/100
        grand_total = total + tax
    except ObjectDoesNotExist:
        pass
    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax' : tax,
        'grand_total': grand_total,
    }
    return render(request,'store/checkout.html',context)