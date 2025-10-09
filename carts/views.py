# carts/views.py
'''
from collections import defaultdict

from django.contrib.auth.decorators import login_required  # used elsewhere
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404

from store.models import Product, Variation
from .models import Cart, CartItem


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


def _iter_selected_variations(product, data):
    """
    Yield Variation objects for keys/values from form data.
    Keys like 'size', 'color' should match Variation.variation_category.
    """
    skip_keys = {"csrfmiddlewaretoken", "quantity"}
    for key, value in data.items():
        if key in skip_keys or not value:
            continue
        try:
            yield Variation.objects.get(
                product=product,
                variation_category__iexact=key,
                variation_value__iexact=value
            )
        except Variation.DoesNotExist:
            # Ignore keys that aren't valid variations for this product
            continue


def _merge_duplicate_rows(qs):
    """
    Merge duplicate CartItem rows that have the same (product + variation set)
    by summing quantities and keeping the earliest row.
    Returns nothing; it mutates the DB and the caller should re-query.
    """
    items = qs.select_related('product').prefetch_related('variations')
    groups = defaultdict(list)

    for ci in items:
        sig = (ci.product_id, tuple(sorted(ci.variations.values_list('id', flat=True))))
        groups[sig].append(ci)

    for _, bucket in groups.items():
        if len(bucket) <= 1:
            continue
        bucket.sort(key=lambda x: x.id)
        keeper, *dupes = bucket
        new_qty = sum(i.quantity for i in bucket)
        if keeper.quantity != new_qty:
            keeper.quantity = new_qty
            keeper.save(update_fields=['quantity'])
        for d in dupes:
            d.delete()


# ------------------------------------------------------------
# Cart pages
# ------------------------------------------------------------
def cart(request, total=0, quantity=0, cart_items=None):
    """
    Show the cart page (for both guest and logged-in users) and merge duplicates.
    """
    try:
        tax = 0
        grand_total = 0

        if request.user.is_authenticated:
            base_qs = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            base_qs = CartItem.objects.filter(cart=cart, is_active=True)

        # Merge duplicate rows for a clean view
        _merge_duplicate_rows(base_qs)

        # Re-fetch after dedupe
        cart_items = base_qs.select_related('product').prefetch_related('variations')

        for ci in cart_items:
            total += (ci.product.price * ci.quantity)
            quantity += ci.quantity

        tax = (2 * total) / 100
        grand_total = total + tax

    except ObjectDoesNotExist:
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
    return render(request, 'store/cart.html', context)


# ------------------------------------------------------------
# Add to cart
# ------------------------------------------------------------
def add_cart(request, product_id):
    """
    Add a product to the cart, merging rows by variation combination.
    Works for both authenticated users and guests (session cart).
    """
    current_user = request.user
    product = get_object_or_404(Product, id=product_id)

    # Collect selected variations from POST (if any)
    product_variation = []
    if request.method == "POST":
        product_variation = list(_iter_selected_variations(product, request.POST))

    # Use an order-independent signature for selected variations
    pv_sig = tuple(sorted(v.id for v in product_variation))

    # Authenticated branch
    if current_user.is_authenticated:
        is_cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()
        if is_cart_item_exists:
            cart_item_qs = CartItem.objects.filter(product=product, user=current_user)

            ex_var_list = []
            id_list = []
            for item in cart_item_qs:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            ex_var_list_sigs = [tuple(sorted(v.id for v in lst)) for lst in ex_var_list]

            if pv_sig in ex_var_list_sigs:
                index = ex_var_list_sigs.index(pv_sig)
                item_id = id_list[index]
                item = CartItem.objects.get(product=product, id=item_id, user=current_user)
                item.quantity += 1
                item.is_active = True
                item.save(update_fields=['quantity', 'is_active'])
            else:
                item = CartItem.objects.create(product=product, quantity=1, user=current_user, is_active=True)
                if product_variation:
                    item.variations.set(product_variation)
                item.save()
        else:
            item = CartItem.objects.create(product=product, quantity=1, user=current_user, is_active=True)
            if product_variation:
                item.variations.set(product_variation)
            item.save()

        return redirect('cart')

    # Guest (session) branch
    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()

        is_cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()
        if is_cart_item_exists:
            cart_item_qs = CartItem.objects.filter(product=product, cart=cart)

            ex_var_list = []
            id_list = []
            for item in cart_item_qs:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            ex_var_list_sigs = [tuple(sorted(v.id for v in lst)) for lst in ex_var_list]

            if pv_sig in ex_var_list_sigs:
                index = ex_var_list_sigs.index(pv_sig)
                item_id = id_list[index]
                item = CartItem.objects.get(product=product, id=item_id, cart=cart)
                item.quantity += 1
                item.is_active = True
                item.save(update_fields=['quantity', 'is_active'])
            else:
                item = CartItem.objects.create(product=product, quantity=1, cart=cart, is_active=True)
                if product_variation:
                    item.variations.set(product_variation)
                item.save()
        else:
            item = CartItem.objects.create(product=product, quantity=1, cart=cart, is_active=True)
            if product_variation:
                item.variations.set(product_variation)
            item.save()

        return redirect('cart')


# ------------------------------------------------------------
# Remove / delete
# ------------------------------------------------------------
def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save(update_fields=['quantity'])
        else:
            cart_item.delete()
    except CartItem.DoesNotExist:
        pass
    return redirect('cart')


def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        CartItem.objects.filter(product=product, user=request.user, id=cart_item_id).delete()
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        CartItem.objects.filter(product=product, cart=cart, id=cart_item_id).delete()
    return redirect('cart')


# ------------------------------------------------------------
# Unified CHECKOUT (supports Buy Now for guests & users)
# ------------------------------------------------------------
@login_required
def checkout(request, total=0, quantity=0, cart_items=None):
    """
    Shows the checkout page.
    If query string contains ?product_id=<id> (or ?buy_now=<id>), it will:
      - For logged-in users: add/increment that product (qty=1) in their cart
      - For guests: add/increment that product (qty=1) in the session cart
    Then it renders the same checkout template you already have, so images,
    names, quantities, and prices appear in the Order Review.
    """
    # Accept both keys so old/new links work
    target_id = request.GET.get("product_id") or request.GET.get("buy_now")
    if target_id:
        product = get_object_or_404(Product, id=target_id)

        if request.user.is_authenticated:
            ci, created = CartItem.objects.get_or_create(
                user=request.user,
                product=product,
                defaults={'quantity': 1, 'is_active': True}
            )
            if not created:
                # If you want Buy Now to force qty=1 instead of incrementing, replace the next two lines:
                ci.quantity += 1
                ci.is_active = True
                ci.save(update_fields=["quantity", "is_active"])

                # Force-to-1 variant (optional):
                # ci.quantity = 1
                # ci.is_active = True
                # ci.save(update_fields=["quantity", "is_active"])
        else:
            cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))
            ci, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={'quantity': 1, 'is_active': True}
            )
            if not created:
                # (Same optional "force-to-1" note applies here)
                ci.quantity += 1
                ci.is_active = True
                ci.save(update_fields=["quantity", "is_active"])

                # Force-to-1 variant (optional):
                # ci.quantity = 1
                # ci.is_active = True
                # ci.save(update_fields=["quantity", "is_active"])

    # Build the order review from the cart (user or session)
    try:
        tax = 0
        grand_total = 0

        if request.user.is_authenticated:
            base_qs = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            base_qs = CartItem.objects.filter(cart=cart, is_active=True)

        # Safety: merge duplicate rows
        _merge_duplicate_rows(base_qs)

        # Re-fetch after merge
        cart_items = base_qs.select_related('product').prefetch_related('variations')

        for ci in cart_items:
            total += ci.product.price * ci.quantity
            quantity += ci.quantity

        tax = (2 * total) / 100
        grand_total = total + tax

    except ObjectDoesNotExist:
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
'''



# carts/views.py
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models
from django.conf import settings
from django.urls import reverse
from store.models import Product, Variation
from .models import Cart, CartItem
from django.contrib.auth.views import redirect_to_login


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
                variation_category__iexact=key,
                variation_value__iexact=value
            )
        except Variation.DoesNotExist:
            continue


def _merge_duplicate_rows(qs):
    items = qs.select_related('product').prefetch_related('variations')
    groups = defaultdict(list)

    for ci in items:
        sig = (ci.product_id, tuple(sorted(ci.variations.values_list('id', flat=True))))
        groups[sig].append(ci)

    for _, bucket in groups.items():
        if len(bucket) <= 1:
            continue
        bucket.sort(key=lambda x: x.id)
        keeper, *dupes = bucket
        new_qty = sum(i.quantity for i in bucket)
        if keeper.quantity != new_qty:
            keeper.quantity = new_qty
            keeper.save(update_fields=['quantity'])
        for d in dupes:
            d.delete()


def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0

        if request.user.is_authenticated:
            base_qs = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            base_qs = CartItem.objects.filter(cart=cart, is_active=True)

        _merge_duplicate_rows(base_qs)
        cart_items = base_qs.select_related('product').prefetch_related('variations')

        for ci in cart_items:
            total += (ci.product.price * ci.quantity)
            quantity += ci.quantity

        tax = (2 * total) / 100
        grand_total = total + tax

    except ObjectDoesNotExist:
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
    return render(request, 'store/cart.html', context)


def add_cart(request, product_id):
    current_user = request.user
    product = get_object_or_404(Product, id=product_id)

    # Check stock availability
    if product.stock <= 0:
        messages.error(request, f'{product.product_name} is out of stock!')
        return redirect(request.META.get('HTTP_REFERER', 'store'))

    product_variation = []
    if request.method == "POST":
        product_variation = list(_iter_selected_variations(product, request.POST))

    pv_sig = tuple(sorted(v.id for v in product_variation))

    if current_user.is_authenticated:
        # Calculate current cart quantity for this product
        current_cart_qty = CartItem.objects.filter(
            product=product,
            user=current_user
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

        # Check if adding one more exceeds stock
        if current_cart_qty >= product.stock:
            messages.warning(request, f'Cannot add more. Only {product.stock} units available in stock!')
            return redirect(request.META.get('HTTP_REFERER', 'store'))

        is_cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()
        if is_cart_item_exists:
            cart_item_qs = CartItem.objects.filter(product=product, user=current_user)

            ex_var_list = []
            id_list = []
            for item in cart_item_qs:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            ex_var_list_sigs = [tuple(sorted(v.id for v in lst)) for lst in ex_var_list]

            if pv_sig in ex_var_list_sigs:
                index = ex_var_list_sigs.index(pv_sig)
                item_id = id_list[index]
                item = CartItem.objects.get(product=product, id=item_id, user=current_user)
                
                # Check stock before incrementing
                if item.quantity >= product.stock:
                    messages.warning(request, f'Cannot add more. Only {product.stock} units available!')
                    return redirect(request.META.get('HTTP_REFERER', 'store'))
                
                item.quantity += 1
                item.is_active = True
                item.save(update_fields=['quantity', 'is_active'])
                messages.success(request, f'{product.product_name} quantity updated in cart!')
            else:
                item = CartItem.objects.create(product=product, quantity=1, user=current_user, is_active=True)
                if product_variation:
                    item.variations.set(product_variation)
                item.save()
                messages.success(request, f'{product.product_name} added to cart!')
        else:
            item = CartItem.objects.create(product=product, quantity=1, user=current_user, is_active=True)
            if product_variation:
                item.variations.set(product_variation)
            item.save()
            messages.success(request, f'{product.product_name} added to cart!')

        return redirect('cart')

    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()

        # Calculate current cart quantity for this product (guest)
        current_cart_qty = CartItem.objects.filter(
            product=product,
            cart=cart
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

        if current_cart_qty >= product.stock:
            messages.warning(request, f'Cannot add more. Only {product.stock} units available in stock!')
            return redirect(request.META.get('HTTP_REFERER', 'store'))

        is_cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()
        if is_cart_item_exists:
            cart_item_qs = CartItem.objects.filter(product=product, cart=cart)

            ex_var_list = []
            id_list = []
            for item in cart_item_qs:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            ex_var_list_sigs = [tuple(sorted(v.id for v in lst)) for lst in ex_var_list]

            if pv_sig in ex_var_list_sigs:
                index = ex_var_list_sigs.index(pv_sig)
                item_id = id_list[index]
                item = CartItem.objects.get(product=product, id=item_id, cart=cart)
                
                if item.quantity >= product.stock:
                    messages.warning(request, f'Cannot add more. Only {product.stock} units available!')
                    return redirect(request.META.get('HTTP_REFERER', 'store'))
                
                item.quantity += 1
                item.is_active = True
                item.save(update_fields=['quantity', 'is_active'])
                messages.success(request, f'{product.product_name} quantity updated!')
            else:
                item = CartItem.objects.create(product=product, quantity=1, cart=cart, is_active=True)
                if product_variation:
                    item.variations.set(product_variation)
                item.save()
                messages.success(request, f'{product.product_name} added to cart!')
        else:
            item = CartItem.objects.create(product=product, quantity=1, cart=cart, is_active=True)
            if product_variation:
                item.variations.set(product_variation)
            item.save()
            messages.success(request, f'{product.product_name} added to cart!')

        return redirect('cart')


def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save(update_fields=['quantity'])
        else:
            cart_item.delete()
    except CartItem.DoesNotExist:
        pass
    return redirect('cart')


def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        CartItem.objects.filter(product=product, user=request.user, id=cart_item_id).delete()
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        CartItem.objects.filter(product=product, cart=cart, id=cart_item_id).delete()
    return redirect('cart')


def buy_now(request, product_id):
    if not request.user.is_authenticated:
        # Sends them to settings.LOGIN_URL and appends ?next=<current path>
        return redirect_to_login(request.get_full_path())

    product = get_object_or_404(Product, id=product_id)

    cart_items = CartItem.objects.filter(user=request.user, product=product)

    if cart_items.exists():
        main_item = cart_items.first()
        total_qty = sum(item.quantity for item in cart_items)
        if main_item.quantity != total_qty:
            main_item.quantity = total_qty
            main_item.save(update_fields=['quantity'])
        cart_items.exclude(pk=main_item.pk).delete()
    else:
        main_item = CartItem.objects.create(
            user=request.user,
            product=product,
            quantity=1,
            is_active=True
        )

    return redirect('orders:checkout')