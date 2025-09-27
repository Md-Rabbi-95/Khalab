from django.shortcuts import render, get_object_or_404,redirect
from store.models import Product, ReviewRating, ProductGallery, Variation
from category.models import Category
from django.db.models import Min, Max
from carts.views import _cart_id
from django.http import HttpResponse
from carts.models import CartItem
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
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # === Pagination AFTER filtering ===
    paginator = Paginator(products, 6)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    product_count = products.count()

    # === Dynamic Sizes ===
    sizes = Variation.objects.filter(
        variation_category__iexact="size", is_active=True
    ).values_list("variation_value", flat=True).distinct()

    # === Dynamic Price Range (from ALL products, not filtered ones) ===
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

    in_cart = CartItem.objects.filter(
        cart__cart_id=_cart_id(request),
        product=single_product
    ).exists()

    orderproduct = False
    if request.user.is_authenticated:
        orderproduct = OrderProduct.objects.filter(
        user=request.user,
        product_id=single_product.id
    ).exists()
    
    # Get the reviews
    reviews = ReviewRating.objects.filter(product_id=single_product.id, status=True)
    
    # get the product gallery
    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)
    
    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
    }
    return render(request, 'store/product_detail.html', context)


def search(request):
    products = Product.objects.none()
    product_count = 0

    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products = Product.objects.order_by('-created_date').filter(
                Q(description__icontains=keyword) |
                Q(product_name__icontains=keyword)
            )
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
        'products': products,
        'product_count': product_count,
        'sizes': sizes,
        'price_range': price_range,
        # keep filters consistent
        'selected_sizes': request.GET.getlist("size"),
        'selected_min': request.GET.get("min_price"),
        'selected_max': request.GET.get("max_price"),
    }
    return render(request, 'store/store.html', context)



def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == "POST":
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id,product__id=product_id)
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
    return render(request, "store/about.html",context)

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




