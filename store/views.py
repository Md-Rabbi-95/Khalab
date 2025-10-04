# store/views.py

from django.shortcuts import render, get_object_or_404, redirect
from store.models import Product, ReviewRating, ProductGallery, Variation
from category.models import Category
from django.db.models import Min, Max, Sum
from django.db import models
from carts.views import _cart_id
from carts.models import Cart, CartItem
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from .forms import ReviewForm
from django.contrib import messages
from orders.models import OrderProduct


def store(request, category_slug=None):
    categories = None

    if category_slug:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True)
    else:
        products = Product.objects.filter(is_available=True).order_by('id')

    # === Apply Size Filter ===
    size_filter = request.GET.getlist("size")
    if size_filter:
        products = products.filter(
            variation__variation_category__iexact="size",
            variation__variation_value__in=size_filter
        ).distinct()

    # === Apply Price Filter ===
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    price_filter_applied = False
    
    if min_price:
        products = products.filter(price__gte=min_price)
        price_filter_applied = True
    if max_price:
        products = products.filter(price__lte=max_price)
        price_filter_applied = True
    
    # === Apply Price Ordering when price filter is used ===
    if price_filter_applied:
        products = products.order_by('price')

    # === Pagination AFTER filtering ===
    paginator = Paginator(products, 6)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    product_count = products.count()

    # === Dynamic Sizes ===
    sizes = Variation.objects.filter(
        variation_category__iexact="size", is_active=True
    ).values_list("variation_value", flat=True).distinct()

    # === Dynamic Price Range ===
    price_range = Product.objects.aggregate(
        min_price=Min("price"),
        max_price=Max("price")
    )

    context = {
        'products': paged_products,
        'product_count': product_count,
        'sizes': sizes,
        'price_range': price_range,
        'selected_sizes': size_filter,   
        'selected_min': min_price,
        'selected_max': max_price,
    }
    return render(request, 'store/store.html', context)


def product_detail(request, category_slug, product_slug):
    single_product = get_object_or_404(
        Product,
        category__slug=category_slug,
        slug=product_slug
    )

    # Get current cart quantity for this product
    cart_quantity = 0
    if request.user.is_authenticated:
        cart_quantity = CartItem.objects.filter(
            user=request.user,
            product=single_product
        ).aggregate(total=models.Sum('quantity'))['total'] or 0
    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_quantity = CartItem.objects.filter(
                cart=cart,
                product=single_product
            ).aggregate(total=models.Sum('quantity'))['total'] or 0
        except:
            pass

    in_cart = cart_quantity > 0
    available_stock = max(0, single_product.stock - cart_quantity)

    orderproduct = False
    if request.user.is_authenticated:
        orderproduct = OrderProduct.objects.filter(
            user=request.user,
            product_id=single_product.id
        ).exists()
    
    reviews = ReviewRating.objects.filter(product_id=single_product.id, status=True)
    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)
    
    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'cart_quantity': cart_quantity,
        'available_stock': available_stock,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
    }
    return render(request, 'store/product_detail.html', context)


def search(request):
    products = Product.objects.none()
    product_count = 0
    search_performed = False
    matched_category = None

    if 'keyword' in request.GET:
        keyword = request.GET['keyword'].strip()
        if keyword:
            search_performed = True
            
            # Try to find matching category first
            try:
                matched_category = Category.objects.filter(
                    Q(category_name__icontains=keyword) |
                    Q(slug__icontains=keyword)
                ).first()
            except:
                pass
            
            # Build comprehensive product search query
            product_query = Q(product_name__icontains=keyword) | Q(description__icontains=keyword)
            
            # If category matched, include all products from that category
            if matched_category:
                product_query |= Q(category=matched_category)
            else:
                # Also search by category name in products
                product_query |= Q(category__category_name__icontains=keyword)
            
            # Get products matching the search criteria
            products = Product.objects.filter(
                product_query,
                is_available=True
            ).distinct().order_by('-created_date')
            
            # === Apply Size Filter ===
            size_filter = request.GET.getlist("size")
            if size_filter:
                products = products.filter(
                    variation__variation_category__iexact="size",
                    variation__variation_value__in=size_filter
                ).distinct()

            # === Apply Price Filter ===
            min_price = request.GET.get("min_price")
            max_price = request.GET.get("max_price")
            price_filter_applied = False
            
            if min_price:
                products = products.filter(price__gte=min_price)
                price_filter_applied = True
            if max_price:
                products = products.filter(price__lte=max_price)
                price_filter_applied = True
            
            # Apply price ordering when price filter is used
            if price_filter_applied:
                products = products.order_by('price')
            
            product_count = products.count()

    # === Pagination ===
    paginator = Paginator(products, 6)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)

    # === Dynamic Sizes from search results ===
    if products.exists():
        sizes = Variation.objects.filter(
            product__in=products,
            variation_category__iexact="size",
            is_active=True
        ).values_list("variation_value", flat=True).distinct()
    else:
        sizes = []

    # === Dynamic Price Range from search results ===
    if products.exists():
        price_range = products.aggregate(
            min_price=Min("price"),
            max_price=Max("price")
        )
    else:
        price_range = {'min_price': 0, 'max_price': 0}

    context = {
        'products': paged_products,
        'product_count': product_count,
        'sizes': sizes,
        'price_range': price_range,
        'selected_sizes': request.GET.getlist("size"),
        'selected_min': request.GET.get("min_price"),
        'selected_max': request.GET.get("max_price"),
        'keyword': request.GET.get('keyword', ''),
        'search_performed': search_performed,
        'matched_category': matched_category,
    }
    return render(request, 'store/store.html', context)


def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == "POST":
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Thank You! Your review has been updated.')
            return redirect(url)
        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Thank You! Your review has been submitted.')
                return redirect(url)

                
def about(request):
    context = {
        "contact_email": "rabbim913@gmail.com"  
    }
    return render(request, "store/about.html", context)

def find_store(request):
    return render(request, "store/find_store.html")

def return_policy(request):
    return render(request, "store/return_policy.html")

def privacy_policy(request):
    return render(request, "store/privacy_policy.html")

def user_info_legal(request):
    return render(request, "store/user_info_legal.html")

def terms_of_use(request):
    return render(request, "store/terms_of_use.html")