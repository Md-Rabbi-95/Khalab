# orders/views.py
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from .forms import OrderForm, PaymentForm, BANGLADESH_DISTRICTS
import datetime
import uuid
import json

from carts.models import Cart, CartItem
from carts.views import _cart_id
from .forms import OrderForm, PaymentForm
from .models import Order, Payment, OrderProduct, PaymentSettings, DeliveryCharge
from store.models import Product
from accounts.models import UserProfile


def _d(val) -> Decimal:
    """Coerce to Decimal and round to 2 decimal places."""
    if isinstance(val, Decimal):
        x = val
    else:
        x = Decimal(str(val or "0"))
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _compute_delivery_charge_by_district(district: str) -> Decimal:
    """Calculate delivery charge based on district."""
    district_norm = (district or "").strip()
    try:
        dc = DeliveryCharge.objects.get(district__iexact=district_norm)
        return dc.charge
    except DeliveryCharge.DoesNotExist:
        try:
            default_dc = DeliveryCharge.objects.get(is_default=True)
            return default_dc.charge
        except DeliveryCharge.DoesNotExist:
            return Decimal("150.00")


def _client_ip(request) -> str:
    """Best-effort client IP, honoring X-Forwarded-For if behind a proxy."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


class _PreviewOrder:
    """Helper object for payment preview before Order creation."""
    def __init__(self, data: dict):
        self.first_name = data.get('first_name', '')
        self.last_name = data.get('last_name', '')
        self.phone = data.get('phone', '')
        self.email = data.get('email', '')
        self.address_line_1 = data.get('address_line_1', '')
        self.address_line_2 = data.get('address_line_2', '')
        self.area = data.get('area', '')
        self.country = data.get('country', '')
        self.state = data.get('state', '')
        self.order_note = data.get('order_note', '')
        self.order_number = ''
        self.delivery_charge = Decimal("0.00")
        self.order_total = Decimal("0.00")
        self.is_ordered = False
        self.requires_advance = False

    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def full_address(self):
        parts = [self.address_line_1, self.address_line_2, self.area]
        return ' '.join(p.strip() for p in parts if p and p.strip())


def checkout(request, total=0, quantity=0, cart_items=None):
    """Display checkout page with billing form."""
    districts = BANGLADESH_DISTRICTS
    try:
        delivery_charge = Decimal("0.00")
        grand_total = Decimal("0.00")

        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity

        # Calculate delivery charge (default, will update based on district selection)
        delivery_charge = Decimal("150.00")
        grand_total = _d(total) + delivery_charge

    except ObjectDoesNotExist:
        pass


    # Prepare user data for auto-fill
    user_data = {}
    if request.user.is_authenticated:
        user_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': getattr(request.user, 'phone_number', ''),
        }

        # Try to get data from user profile
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_data.update({
                'address_line_1': profile.address_line_1 or '',
                'address_line_2': profile.address_line_2 or '',
                'area': profile.area or '',
                'state': profile.city or '',
                'country': profile.country or 'Bangladesh',
            })
        except UserProfile.DoesNotExist:
            pass

        # Try to get data from last order (override profile data)
        try:
            last_order = Order.objects.filter(
                user=request.user,
                is_ordered=True
            ).order_by('-created_at').first()

            if last_order:
                user_data.update({
                    'address_line_1': last_order.address_line_1 or user_data.get('address_line_1', ''),
                    'address_line_2': last_order.address_line_2 or user_data.get('address_line_2', ''),
                    'area': last_order.area or user_data.get('area', ''),
                    'state': last_order.state or user_data.get('state', ''),
                    'country': last_order.country or user_data.get('country', 'Bangladesh'),
                })
        except Exception:
            pass

    context = {
        'total': _d(total),
        'quantity': quantity,
        'cart_items': cart_items,
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
        'districts': districts, 
        'user_data': json.dumps(user_data),
        'form_data': request.session.get('checkout_data', {}),
    }
    return render(request, 'store/checkout.html', context) 


@transaction.atomic
def place_order(request, total=0, quantity=0):
    """Validate form and store in session, then redirect to payments."""
    # Merge anonymous cart with user cart if logged in
    if request.user.is_authenticated:
        CartItem.objects.filter(
            cart__cart_id=_cart_id(request),
            user__isnull=True
        ).update(user=request.user)

    # Get cart items
    cart_items = CartItem.objects.filter(
        Q(user=request.user) | Q(cart__cart_id=_cart_id(request))
    ).distinct()

    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('store')

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Store validated data in session
            checkout_data = {
                'first_name': form.cleaned_data['first_name'],
                'last_name': form.cleaned_data['last_name'],
                'phone': form.cleaned_data['phone'],
                'email': form.cleaned_data['email'],
                'address_line_1': form.cleaned_data['address_line_1'],
                'address_line_2': form.cleaned_data.get('address_line_2', ''),
                'area': form.cleaned_data['area'],
                'country': form.cleaned_data['country'],
                'state': form.cleaned_data['state'],
                'order_note': form.cleaned_data.get('order_note', ''),
            }
            request.session['checkout_data'] = checkout_data
            return redirect('orders:payments')
        else:
            # Show validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.replace("_", " ").title()}: {error}')
            
            # Preserve form data
            request.session['checkout_data'] = request.POST.dict()
            return redirect('checkout')

    return redirect('checkout')




@transaction.atomic
def payments(request):
    """GET: show payment page. POST: create Order and Payment."""
    # Merge anonymous cart with user cart if logged in
    if request.user.is_authenticated:
        CartItem.objects.filter(
            cart__cart_id=_cart_id(request),
            user__isnull=True
        ).update(user=request.user)

    checkout_data = request.session.get('checkout_data')

    if request.method == 'GET':
        if not checkout_data:
            messages.error(request, 'No checkout information found. Please re-enter your address.')
            return redirect('checkout')

        preview = _PreviewOrder(checkout_data)

        cart_items = CartItem.objects.filter(
            Q(user=request.user) | Q(cart__cart_id=_cart_id(request))
        ).distinct()

        if not cart_items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('store')

        total = Decimal("0.00")
        for item in cart_items.select_related('product'):
            if not item.product:
                continue
            total += _d(item.product.price) * Decimal(item.quantity or 0)

        delivery_charge = _compute_delivery_charge_by_district(preview.state)
        grand_total = _d(total) + _d(delivery_charge)

        preview.delivery_charge = _d(delivery_charge)
        preview.order_total = _d(grand_total)

        state_norm = (preview.state or '').strip().lower()
        preview.requires_advance = bool(state_norm and state_norm != 'dhaka')

        payment_settings, _ = PaymentSettings.objects.get_or_create(
            defaults={
                'bkash_number': '01XXXXXXXXX',
                'nagad_number': '01XXXXXXXXX',
                'rocket_number': '01XXXXXXXXX'
            }
        )

        context = {
            'order': preview,
            'cart_items': cart_items,
            'total': _d(total),
            'delivery_charge': _d(delivery_charge),
            'grand_total': _d(grand_total),
            'payment_settings': payment_settings,
        }
        return render(request, 'orders/payments.html', context)

    # POST: finalize order
    if not checkout_data:
        messages.error(request, 'Checkout session expired. Please try again.')
        return redirect('checkout')

    payment_method = request.POST.get('payment_method')
    payment_type = request.POST.get('payment_type')
    online_payment_method = request.POST.get('online_payment_method')
    transaction_id = (request.POST.get('transaction_id') or '').strip()

    # Enforce outside-Dhaka rule (no COD; must pay advance/full online)
    state_val = (checkout_data.get('state') or '').strip().lower()
    requires_advance = bool(state_val and state_val != 'dhaka')

    if requires_advance and payment_method == 'COD':
        messages.error(
            request,
            'Cash on Delivery is unavailable outside Dhaka. '
            'Please select Online Payment and pay the delivery charge in advance '
            'or complete the full payment online.'
        )
        return redirect('orders:payments')

    if payment_method == 'ONLINE':
        if not online_payment_method:
            messages.error(request, 'Please select an online payment method.')
            return redirect('orders:payments')
        if not transaction_id:
            messages.error(request, 'Please enter transaction ID for online payment.')
            return redirect('orders:payments')

    final_payment_method = 'COD' if payment_method == 'COD' else online_payment_method

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

    delivery_charge = _compute_delivery_charge_by_district(checkout_data.get('state'))
    grand_total = _d(items_subtotal) + _d(delivery_charge)

    amount_paid = grand_total if payment_type == 'FULL' else _d(delivery_charge)
    amount_paid = _d(amount_paid)

    # Determine payment status based on payment method and type
    if payment_method == 'COD':
        payment_status = 'Unpaid'
        is_approved = True
    elif payment_type == 'ADVANCE':
        payment_status = 'Paid (Delivery Charge)'
        is_approved = False
    elif payment_type == 'FULL':
        payment_status = 'Paid (Full)'
        is_approved = False
    else:
        payment_status = 'Pending'
        is_approved = False

    # Create Order
    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        first_name=checkout_data.get('first_name', ''),
        last_name=checkout_data.get('last_name', ''),
        phone=checkout_data.get('phone', ''),
        email=checkout_data.get('email', ''),
        address_line_1=checkout_data.get('address_line_1', ''),
        address_line_2=checkout_data.get('address_line_2', ''),
        area=checkout_data.get('area', ''),
        country=checkout_data.get('country', ''),
        state=checkout_data.get('state', ''),
        order_note=checkout_data.get('order_note', ''),
        order_number=datetime.date.today().strftime("%Y%m%d"),
        order_total=_d(grand_total),
        delivery_charge=_d(delivery_charge),
        payment_status=payment_status,
        is_ordered=False,
        ip=_client_ip(request)[:45],
    )

    # Generate proper order number
    current_date = datetime.date.today().strftime("%Y%m%d")
    order.order_number = f"{current_date}{order.id}"
    order.save(update_fields=['order_number'])

    # Create Payment with proper status
    payment = Payment.objects.create(
        user=request.user if request.user.is_authenticated else None,
        payment_id=str(uuid.uuid4()),
        payment_method=final_payment_method,
        payment_type=payment_type,
        transaction_id=transaction_id if payment_method == 'ONLINE' else '',
        amount_paid=amount_paid,
        status=payment_status,
        is_approved=is_approved
    )

    order.payment = payment
    order.is_ordered = True
    order.save(update_fields=['payment', 'is_ordered'])

    # Move cart items to OrderProduct
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

        # Update stock
        if hasattr(item.product, 'stock'):
            item.product.stock = max(0, int(item.product.stock) - int(item.quantity))
            item.product.save(update_fields=['stock'])

    # Clear cart
    cart_items.delete()

    # Send confirmation email
    try:
        subject = 'Order Confirmation - Thanks for your order!'
        ordered_products = order.orderproduct_set.select_related('product').prefetch_related('variations')
        subtotal_val = sum(
            (op.product_price or 0) * (op.quantity or 0)
            for op in ordered_products
        )

        context = {
            'order': order,
            'payment': payment,
            'ordered_products': ordered_products,
            'subtotal': subtotal_val,
            'domain': getattr(settings, 'SITE_URL', 'https://yourdomain.com'),
            'now': timezone.now(),
        }

        html_body = render_to_string('orders/order_received_email.html', context)
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[order.email],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
    except Exception as e:
        print(f"Email sending failed: {e}")

    # Clear session and redirect
    request.session.pop('checkout_data', None)
    request.session['order_number'] = order.order_number
    request.session['payment_id'] = payment.payment_id

    return redirect('orders:order_complete')



def order_complete(request):
    """Display order confirmation page."""
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
    