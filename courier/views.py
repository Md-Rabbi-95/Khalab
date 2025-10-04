# courier/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from orders.models import Order
from .models import REDXConfiguration, REDXParcel
from .services import REDXService
import logging

logger = logging.getLogger(__name__)


@staff_member_required
def create_redx_parcel(request, order_id):
    """Create REDX parcel for an order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if parcel already exists
    if hasattr(order, 'redx_parcel'):
        messages.warning(request, f"REDX parcel already exists for order {order.order_number}")
        return redirect('admin:orders_order_change', order_id)
    
    if request.method == 'POST':
        return _handle_parcel_creation(request, order)
    
    # GET request - show form with pre-filled data
    return _render_parcel_form(request, order)


def _handle_parcel_creation(request, order):
    """Handle POST request for parcel creation"""
    try:
        # Get form data
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_address = request.POST.get('customer_address', '').strip()
        customer_area = request.POST.get('customer_area', '').strip()
        customer_district = request.POST.get('customer_district', 'Dhaka').strip()
        
        # Validate required fields
        if not all([customer_name, customer_phone, customer_address, customer_area]):
            messages.error(request, "Please fill in all required fields.")
            return redirect('courier:create_redx_parcel', order_id=order.id)
        
        # Parse numeric fields
        try:
            parcel_weight = float(request.POST.get('parcel_weight', 0.5))
            cash_collection_amount = float(request.POST.get('cash_collection_amount', 0))
        except ValueError:
            messages.error(request, "Invalid weight or cash collection amount.")
            return redirect('courier:create_redx_parcel', order_id=order.id)
        
        # Get REDX service
        redx_service = REDXService()
        
        # Find area ID from REDX
        area = redx_service.find_area_by_name(customer_area, customer_district)
        if not area:
            messages.error(request, f"Area '{customer_area}' not found in REDX. Please select a valid area.")
            return redirect('courier:create_redx_parcel', order_id=order.id)
        
        # Prepare REDX API payload with correct field names
        parcel_payload = {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_address": customer_address,
            "delivery_area": area['name'],  # Area name (text)
            "delivery_area_id": area['id'],  # Area ID (number)
            "merchant_invoice_id": order.order_number,
            "parcel_weight": parcel_weight,
            "cash_collection_amount": cash_collection_amount,
            "value": float(order.order_total)  # Required: parcel value
        }
        
        # Create parcel via REDX API
        result = redx_service.create_parcel(parcel_payload)
        
        if result['success']:
            # Extract tracking ID from response
            tracking_id = result.get('tracking_id')
            response_data = result.get('data', {})
            
            # Check if we got a tracking ID
            if not tracking_id:
                logger.error(f"No tracking ID in REDX response: {response_data}")
                messages.error(request, "⚠️ Parcel created but no tracking ID received.")
                
                # Save as failed parcel for review
                REDXParcel.objects.create(
                    order=order,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    customer_address=customer_address,
                    customer_area=area['name'],
                    customer_district=customer_district,
                    parcel_weight=parcel_weight,
                    cash_collection_amount=cash_collection_amount,
                    status='failed',
                    error_message='No tracking ID received from REDX',
                    redx_response=response_data
                )
                return redirect('admin:orders_order_change', order.id)
            
            # Save parcel information with tracking ID
            parcel = REDXParcel.objects.create(
                order=order,
                tracking_id=tracking_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                customer_area=area['name'],
                customer_district=customer_district,
                parcel_weight=parcel_weight,
                cash_collection_amount=cash_collection_amount,
                status='created',
                redx_response=response_data
            )
            
            logger.info(f"REDX parcel created successfully for order {order.order_number}: {tracking_id}")
            messages.success(request, f"✅ REDX parcel created successfully! Tracking ID: {tracking_id}")
            return redirect('admin:orders_order_change', order.id)
        else:
            # Save failed parcel for debugging
            error_message = result.get('error', 'Unknown error')
            
            REDXParcel.objects.create(
                order=order,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                customer_area=customer_area,
                customer_district=customer_district,
                parcel_weight=parcel_weight,
                cash_collection_amount=cash_collection_amount,
                status='failed',
                error_message=error_message
            )
            
            logger.error(f"Failed to create REDX parcel for order {order.order_number}: {error_message}")
            messages.error(request, f"❌ Failed to create REDX parcel: {error_message}")
            return redirect('admin:orders_order_change', order.id)
            
    except Exception as e:
        logger.exception(f"Error creating parcel for order {order.order_number}")
        messages.error(request, f"⚠️ Error creating parcel: {str(e)}")
        return redirect('admin:orders_order_change', order.id)


def _render_parcel_form(request, order):
    """Render the parcel creation form with pre-filled data"""
    try:
        # Get REDX configuration
        config = REDXConfiguration.objects.filter(is_active=True).first()
        if not config:
            messages.error(request, "REDX is not configured. Please configure it in admin panel first.")
            return redirect('admin:orders_order_change', order.id)
        
        # Get location field safely - try multiple possible field names
        location = _get_order_location(order)
        
        # Build customer address
        address_parts = [order.address_line_1]
        if hasattr(order, 'address_line_2') and order.address_line_2:
            address_parts.append(order.address_line_2)
        customer_address = ', '.join(filter(None, address_parts))
        
        # Prepare context with pre-filled data
        context = {
            'order': order,
            'config': config,
            'customer_name': f"{order.first_name} {order.last_name}".strip(),
            'customer_phone': order.phone,
            'customer_address': customer_address,
            'customer_area': order.area,
            'customer_district': location,
            'cash_collection_amount': float(order.collected_amount),
            'parcel_weight': 0.5,  # Default weight in KG
        }
        
        return render(request, 'courier/create_parcel.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading parcel form for order {order.id}")
        messages.error(request, f"⚠️ Error loading form: {str(e)}")
        return redirect('admin:orders_order_change', order.id)


def _get_order_location(order):
    """
    Safely extract location from order.
    Tries multiple field names: district, city, state
    """
    # Try different possible field names in order of preference
    for field_name in ['district', 'city', 'state', 'area']:
        if hasattr(order, field_name):
            value = getattr(order, field_name, None)
            if value and str(value).strip():
                return str(value).strip()
    
    # Default fallback
    return 'Dhaka'


@staff_member_required
def track_parcel(request, parcel_id):
    """Track REDX parcel status"""
    parcel = get_object_or_404(REDXParcel, id=parcel_id)
    
    if not parcel.tracking_id:
        messages.error(request, "❌ No tracking ID available for this parcel.")
        return redirect('admin:courier_redxparcel_change', parcel_id)
    
    try:
        # Fetch tracking information from REDX
        redx_service = REDXService()
        result = redx_service.track_parcel(parcel.tracking_id)
        
        if result['success']:
            tracking_data = result.get('data', {})
            
            # Update parcel with latest tracking info
            parcel.redx_response = tracking_data
            
            # Update status if available in tracking data
            if 'status' in tracking_data:
                status_mapping = {
                    'pending': 'pending',
                    'picked_up': 'picked',
                    'in_transit': 'in_transit',
                    'delivered': 'delivered',
                    'cancelled': 'cancelled',
                }
                new_status = status_mapping.get(tracking_data['status'].lower(), parcel.status)
                if new_status != parcel.status:
                    parcel.status = new_status
            
            parcel.save()
            
            context = {
                'parcel': parcel,
                'tracking_data': tracking_data,
                'order': parcel.order,
            }
            
            return render(request, 'courier/track_parcel.html', context)
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Tracking failed for parcel {parcel.tracking_id}: {error_msg}")
            messages.error(request, f"❌ Tracking failed: {error_msg}")
            return redirect('admin:courier_redxparcel_change', parcel_id)
            
    except Exception as e:
        logger.exception(f"Error tracking parcel {parcel.tracking_id}")
        messages.error(request, f"⚠️ Error tracking parcel: {str(e)}")
        return redirect('admin:courier_redxparcel_change', parcel_id)


@staff_member_required
def cancel_parcel(request, parcel_id):
    """Cancel REDX parcel"""
    parcel = get_object_or_404(REDXParcel, id=parcel_id)
    
    # Check if parcel can be cancelled
    if parcel.status in ['delivered', 'cancelled']:
        messages.warning(request, f"Cannot cancel parcel. Current status: {parcel.get_status_display()}")
        return redirect('admin:courier_redxparcel_change', parcel_id)
    
    if not parcel.tracking_id:
        messages.error(request, "No tracking ID available. Cannot cancel parcel.")
        return redirect('admin:courier_redxparcel_change', parcel_id)
    
    # Require confirmation parameter for GET requests
    if request.method == 'GET' and request.GET.get('confirm') != 'yes':
        messages.error(request, "Cancellation not confirmed.")
        return redirect('admin:courier_redxparcel_change', parcel_id)
    
    try:
        redx_service = REDXService()
        result = redx_service.cancel_parcel(parcel.tracking_id)
        
        if result['success']:
            parcel.status = 'cancelled'
            parcel.redx_response = result.get('data', parcel.redx_response)
            parcel.save()
            
            logger.info(f"Parcel {parcel.tracking_id} cancelled successfully")
            messages.success(request, f"Parcel {parcel.tracking_id} cancelled successfully.")
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Failed to cancel parcel {parcel.tracking_id}: {error_msg}")
            messages.error(request, f"Failed to cancel parcel: {error_msg}")
        
        return redirect('admin:courier_redxparcel_change', parcel_id)
            
    except Exception as e:
        logger.exception(f"Error cancelling parcel {parcel.tracking_id}")
        messages.error(request, f"Error cancelling parcel: {str(e)}")
        return redirect('admin:courier_redxparcel_change', parcel_id)


@staff_member_required
def parcel_list(request):
    """List all REDX parcels with filters"""
    parcels = REDXParcel.objects.select_related('order').all()
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        parcels = parcels.filter(status=status_filter)
    
    search_query = request.GET.get('q')
    if search_query:
        parcels = parcels.filter(
            tracking_id__icontains=search_query
        ) | parcels.filter(
            customer_name__icontains=search_query
        ) | parcels.filter(
            customer_phone__icontains=search_query
        ) | parcels.filter(
            order__order_number__icontains=search_query
        )
    
    context = {
        'parcels': parcels,
        'status_choices': REDXParcel.STATUS_CHOICES,
        'current_status': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'courier/parcel_list.html', context)