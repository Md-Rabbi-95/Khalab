from django.shortcuts import render,redirect
from store.models import Product,Variation
from .models import Cart,CartItem
from django.http import HttpResponse
from collections import defaultdict
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def _iter_selected_variations(product, data):
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
    
'''def add_cart(request, product_id):
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
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
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
    return render(request, 'store/cart.html', context)'''
    
def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0

        # Fetch items for this user/guest as you already do
        if request.user.is_authenticated:
            base_qs = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            base_qs = CartItem.objects.filter(cart=cart, is_active=True)

        # Prefetch to avoid N+1 queries
        cart_items = base_qs.select_related('product').prefetch_related('variations')

        # --- NEW: merge duplicates (same product + same variation set) ---
        groups = defaultdict(list)
        for ci in cart_items:
            sig = (ci.product_id, tuple(sorted(ci.variations.values_list('id', flat=True))))
            groups[sig].append(ci)

        for _, items in groups.items():
            if len(items) > 1:
                items.sort(key=lambda x: x.id)  # keep earliest
                keeper, *dupes = items
                new_qty = sum(i.quantity for i in items)
                if keeper.quantity != new_qty:
                    keeper.quantity = new_qty
                    keeper.save(update_fields=['quantity'])
                for d in dupes:
                    d.delete()
        # --- END NEW ---

        # Re-fetch after dedupe so totals and template show the single merged rows
        cart_items = base_qs.select_related('product').prefetch_related('variations')

        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity

        tax = (2 * total) / 100
        grand_total = total + tax

    except ObjectDoesNotExist:
        pass

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/cart.html', context)


def remove_cart(request, product_id,cart_item_id):
    
    product = get_object_or_404(Product, id=product_id)

    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user,id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
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

    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        CartItem.objects.filter(product=product, user=request.user,id=cart_item_id).delete()
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        CartItem.objects.filter(product=product, cart=cart,id=cart_item_id).delete()
    return redirect('cart')


    
@login_required
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0

        # Since this view is login_required, the "else" won't run, but keeping it is harmless.
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True) \
                                         .select_related('product') \
                                         .prefetch_related('variations')
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True) \
                                         .select_related('product') \
                                         .prefetch_related('variations')

        for cart_item in cart_items:
            total += cart_item.product.price * cart_item.quantity
            quantity += cart_item.quantity

        tax = (2 * total) / 100
        grand_total = total + tax

    except ObjectDoesNotExist:
        # No cart yet, or empty
        cart_items = []
        tax = 0
        grand_total = 0

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/checkout.html', context)



def add_cart(request, product_id):

    current_user = request.user
    product = Product.objects.get(id=product_id)

    if current_user.is_authenticated:
        product_variation = []
        if request.method == "POST":
            for item in request.POST:
                key = item
                value = request.POST[key]
                try:
                    variation = Variation.objects.get(
                        product=product,
                        variation_category__iexact=key,
                        variation_value__iexact=value
                    )
                    product_variation.append(variation)
                except:
                    pass

        # order-independent signature for selected variations
        pv_sig = tuple(sorted(v.id for v in product_variation))

        is_cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()
        if is_cart_item_exists:
            cart_item = CartItem.objects.filter(product=product, user=current_user)
            ex_var_list = []
            id_list = []
            for item in cart_item:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            # compare by signatures so same combo merges correctly
            ex_var_list_sigs = [tuple(sorted(v.id for v in lst)) for lst in ex_var_list]

            if pv_sig in ex_var_list_sigs:
                index = ex_var_list_sigs.index(pv_sig)
                item_id = id_list[index]
                item = CartItem.objects.get(product=product, id=item_id)
                item.quantity += 1
                item.save()
            else:
                item = CartItem.objects.create(product=product, quantity=1, user=current_user)
                if len(product_variation) > 0:
                    item.variations.clear()
                    item.variations.add(*product_variation)
                    item.save()

        else:
            # create for authenticated user (no 'cart' in this branch)
            cart_item = CartItem.objects.create(
                product=product,
                quantity=1,
                user=current_user,
            )
            if len(product_variation) > 0:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)
            cart_item.save()
        return redirect('cart')

    # if the user is not authenticated
    else:
        product_variation = []
        if request.method == "POST":
            for item in request.POST:
                key = item
                value = request.POST[key]
                try:
                    variation = Variation.objects.get(
                        product=product,
                        variation_category__iexact=key,
                        variation_value__iexact=value
                    )
                    product_variation.append(variation)
                except:
                    pass

        # order-independent signature for selected variations
        pv_sig = tuple(sorted(v.id for v in product_variation))

        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()

        is_cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()
        if is_cart_item_exists:
            cart_item = CartItem.objects.filter(product=product, cart=cart)

            ex_var_list = []
            id_list = []
            for item in cart_item:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            # compare by signatures so same combo merges correctly
            ex_var_list_sigs = [tuple(sorted(v.id for v in lst)) for lst in ex_var_list]

            if pv_sig in ex_var_list_sigs:
                index = ex_var_list_sigs.index(pv_sig)
                item_id = id_list[index]
                item = CartItem.objects.get(product=product, id=item_id)
                item.quantity += 1
                item.save()
            else:
                item = CartItem.objects.create(product=product, quantity=1, cart=cart)
                if len(product_variation) > 0:
                    item.variations.clear()
                    item.variations.add(*product_variation)
                    item.save()

        else:
            cart_item = CartItem.objects.create(
                product=product,
                quantity=1,
                cart=cart,
            )
            if len(product_variation) > 0:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)
            cart_item.save()
        return redirect('cart')