# D:\Django\khalab\orders\views.py
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from carts.models import CartItem
from carts.views import _cart_id
from .forms import OrderForm, PaymentForm
from .models import Order, Payment, OrderProduct, PaymentSettings, DeliveryCharge
from store.models import Product

import datetime
import uuid


def _d(val) -> Decimal:
    """Coerce to Decimal and round to 2dp."""
    if isinstance(val, Decimal):
        x = val
    else:
        x = Decimal(str(val or "0"))
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _compute_delivery_charge_by_city(city: str) -> Decimal:
    """
    Mirror Order.get_delivery_charge(), but usable before an Order exists.
    """
    city_norm = (city or "").lower()
    try:
        dc = DeliveryCharge.objects.get(location=city_norm)
        return dc.charge
    except DeliveryCharge.DoesNotExist:
        try:
            default_dc = DeliveryCharge.objects.get(is_default=True)
            return default_dc.charge
        except DeliveryCharge.DoesNotExist:
            return Decimal("150.00")  # Fallback if no default is set


class _PreviewOrder:
    """
    Small helper object so payments.html can keep using `order.*` and
    `order.full_name()` / `order.full_address()` before a real Order exists.
    """
    def __init__(self, data: dict):
        self.first_name = data.get('first_name', '')
        self.last_name = data.get('last_name', '')
        self.phone = data.get('phone', '')
        self.email = data.get('email', '')
        self.address_line_1 = data.get('address_line_1', '')
        self.address_line_2 = data.get('address_line_2', '')
        self.country = data.get('country', '')
        self.state = data.get('state', '')
        self.city = data.get('city', '')
        self.order_note = data.get('order_note', '')
        # fields used in templates but not known yet:
        self.order_number = ''          # filled after real order is created
        self.delivery_charge = Decimal("0.00")
        self.order_total = Decimal("0.00")
        self.is_ordered = False

    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def full_address(self):
        return f"{self.address_line_1} {self.address_line_2}".strip()


@transaction.atomic
def payments(request):
    """
    GET  : show payment page using data saved in session at checkout.
    POST : create the Order, then create Payment, move cart -> OrderProducts, finish.
    """
    # Ensure any anonymous cart items are adopted to the logged-in user
    if request.user.is_authenticated:
        CartItem.objects.filter(
            cart__cart_id=_cart_id(request),
            user__isnull=True
        ).update(user=request.user)

    # Read checkout data from session (saved by place_order)
    checkout_data = request.session.get('checkout_data')

    if request.method == 'GET':
        if not checkout_data:
            messages.error(request, 'No checkout information found. Please re-enter your address.')
            return redirect('checkout')

        # Build preview order for the template
        preview = _PreviewOrder(checkout_data)

        # Compute cart subtotal
        cart_items = CartItem.objects.filter(
            Q(user=request.user) | Q(cart__cart_id=_cart_id(request))
        ).distinct()

        total = Decimal("0.00")
        for item in cart_items.select_related('product'):
            if not item.product:
                continue
            total += _d(item.product.price) * Decimal(item.quantity or 0)

        # Compute delivery + grand total using the city from checkout_data
        delivery_charge = _compute_delivery_charge_by_city(preview.city)
        grand_total = _d(total) + _d(delivery_charge)

        # Fill preview monetary fields for display only
        preview.delivery_charge = _d(delivery_charge)
        preview.order_total = _d(grand_total)

        # Payment settings (bkash/nagad/rocket)
        payment_settings, _ = PaymentSettings.objects.get_or_create(
            defaults={
                'bkash_number': '01XXXXXXXXX',
                'nagad_number': '01XXXXXXXXX',
                'rocket_number': '01XXXXXXXXX'
            }
        )

        context = {
            'order': preview,                 # keep template variable name the same
            'cart_items': cart_items,
            'total': _d(total),
            'delivery_charge': _d(delivery_charge),
            'grand_total': _d(grand_total),
            'payment_settings': payment_settings,
        }
        return render(request, 'orders/payments.html', context)

    # POST: finalize — create Order, then Payment, then move items, etc.
    if not checkout_data:
        messages.error(request, 'Checkout session expired. Please try again.')
        return redirect('checkout')

    # Read posted payment fields
    payment_method = request.POST.get('payment_method')               # 'COD' or 'ONLINE'
    payment_type = request.POST.get('payment_type')                   # 'FULL' or 'ADVANCE'
    online_payment_method = request.POST.get('online_payment_method') # 'BKASH'|'NAGAD'|'ROCKET'
    transaction_id = request.POST.get('transaction_id')

    # Basic validation for ONLINE
    if payment_method == 'ONLINE':
        if not online_payment_method:
            messages.error(request, 'Please select an online payment method.')
            return redirect('payments')
        if not transaction_id:
            messages.error(request, 'Please enter transaction ID for online payment.')
            return redirect('payments')

    # Determine concrete method to store on Payment
    final_payment_method = 'COD' if payment_method == 'COD' else online_payment_method

    # Compute cart totals again (authoritative)
    cart_items = CartItem.objects.filter(
        Q(user=request.user) | Q(cart__cart_id=_cart_id(request))
    ).distinct()

    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('store')

    items_subtotal = Decimal("0.00")
    for item in cart_items.select_related('product'):
        if not item.product:
            continue
        items_subtotal += _d(item.product.price) * Decimal(item.quantity or 0)

    # Delivery + grand total based on city
    delivery_charge = _compute_delivery_charge_by_city(checkout_data.get('city'))
    grand_total = _d(items_subtotal) + _d(delivery_charge)

    # Amount rules: FULL = grand_total; ADVANCE = delivery_charge
    amount_paid = grand_total if payment_type == 'FULL' else _d(delivery_charge)
    amount_paid = _d(amount_paid)

    # --- Create the Order NOW (only at payment submit) ---
    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        first_name=checkout_data.get('first_name', ''),
        last_name=checkout_data.get('last_name', ''),
        phone=checkout_data.get('phone', ''),
        email=checkout_data.get('email', ''),
        address_line_1=checkout_data.get('address_line_1', ''),
        address_line_2=checkout_data.get('address_line_2', ''),
        country=checkout_data.get('country', ''),
        state=checkout_data.get('state', ''),
        city=checkout_data.get('city', ''),
        order_note=checkout_data.get('order_note', ''),
        order_number=datetime.date.today().strftime("%Y%m%d"),  # temp; finalize below
        order_total=_d(grand_total),
        delivery_charge=_d(delivery_charge),
        is_ordered=False,  # will switch to True after payment record
    )
    # Finalize order_number with DB id
    current_date = datetime.date.today().strftime("%Y%m%d")
    order.order_number = f"{current_date}{order.id}"
    order.save(update_fields=['order_number'])

    # --- Create Payment ---
    payment = Payment.objects.create(
        user=request.user if request.user.is_authenticated else None,
        payment_id=str(uuid.uuid4()),
        payment_method=final_payment_method,
        payment_type=payment_type,
        transaction_id=transaction_id if payment_method == 'ONLINE' else '',
        amount_paid=amount_paid,
        status='Pending' if payment_method == 'ONLINE' else 'Completed',
        is_approved=False if payment_method == 'ONLINE' else True
    )

    # Link order to payment & mark as ordered
    order.payment = payment
    order.is_ordered = True
    order.save(update_fields=['payment', 'is_ordered'])

    # Move cart items -> OrderProduct
    for item in cart_items.select_related('product'):
        if not item.product:
            continue
        unit_price = _d(item.product.price)
        op = OrderProduct.objects.create(
            order=order,
            payment=payment,
            user=request.user if request.user.is_authenticated else None,
            product=item.product,
            quantity=item.quantity,
            product_price=unit_price,
            ordered=True,
        )
        if hasattr(item, 'variations'):
            op.variations.set(item.variations.all())

        # Reduce stock if product has stock field
        if hasattr(item.product, 'stock'):
            item.product.stock = max(0, int(item.product.stock) - int(item.quantity))
            item.product.save(update_fields=['stock'])

    # Clear cart
    cart_items.delete()

    # Send confirmation email (best-effort)
    try:
        mail_subject = 'Order Confirmation - Thanks for your order!'
        message = render_to_string('orders/order_received_email.html', {
            'user': request.user,
            'order': order,
            'payment': payment,
        })
        to_email = order.email
        send_email = EmailMessage(mail_subject, message, to=[to_email])
        send_email.send()
    except Exception as e:
        print(f"Email sending failed: {e}")

    # Clear checkout session data
    request.session.pop('checkout_data', None)

    # Redirect to order complete
    request.session['order_number'] = order.order_number
    request.session['payment_id'] = payment.payment_id
    return redirect('order_complete')


@transaction.atomic
def place_order(request, total=0, quantity=0):
    """
    Previously created an Order here. Now it only VALIDATES and STORES the form
    data in session, then routes to the payments page.
    """
    current_user = request.user

    # Adopt session cart items to logged-in user
    if request.user.is_authenticated:
        CartItem.objects.filter(
            cart__cart_id=_cart_id(request),
            user__isnull=True
        ).update(user=request.user)

    # Validate we have items
    cart_items = CartItem.objects.filter(
        Q(user=request.user) | Q(cart__cart_id=_cart_id(request))
    ).distinct()
    if not cart_items.exists():
        return redirect('store')

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Save ONLY to session; do NOT create DB Order here
            request.session['checkout_data'] = form.cleaned_data
            return redirect('payments')
        else:
            messages.error(request, 'Please correct the errors in the form.')
            return redirect('checkout')

    # If someone GETs this view directly, send them back
    return redirect('checkout')


def order_complete(request):
    order_number = request.session.get('order_number')
    payment_id = request.session.get('payment_id')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = Decimal("0.00")
        for item in ordered_products:
            subtotal += _d(item.product_price) * Decimal(item.quantity or 0)

        payment = Payment.objects.get(payment_id=payment_id)

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'payment_id': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')


