from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.utils.translation import gettext as _, get_language
from .models import Product, InventoryTransaction, Sales, SaleItems, CustomUser, Category
from .forms import LoginForm, ProductForm, InventoryTransactionForm, SaleForm, SaleItemForm, UserForm
import json


def is_admin(user):
    """Admin ekanligini tekshirish"""
    return user.is_authenticated and user.role == 'admin'


def is_superuser(user):
    """Superuser ekanligini tekshirish"""
    return user.is_authenticated and user.is_superuser


def is_admin_or_superuser(user):
    """Admin yoki superuser ekanligini tekshirish"""
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


def login_view(request):
    """Login sahifasi"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, _("Xush kelibsiz, {}!").format(user.fullname))
            return redirect('dashboard')
        else:
            messages.error(request, _("Foydalanuvchi nomi yoki parol noto'g'ri!"))
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})


@login_required
def logout_view(request):
    """Logout"""
    logout(request)
    messages.success(request, _("Tizimdan muvaffaqiyatli chiqdingiz!"))
    return redirect('login')


@login_required
def dashboard(request):
    """Dashboard sahifasi"""
    # Statistika
    total_products = Product.objects.count()
    
    # Low stock logic optimized
    # Note: get_stock logic is complex (transction sum - sales sum). 
    # Doing it purely in ORM for all products might be complex but better than N+1
    # For now, let's optimize by fetching everything we need in fewer queries if possible,
    # or honestly, for a small shop, N+1 might be "okay" but let's try to improve.
    # A true fix would be to have a 'current_stock' field on Product updated via signals.
    # However, without schema changes, we can try to prefetch or just keep it if dataset is small.
    # Given the constraint to not break things, and "fix N+1", 
    # the best approach without schema change is to annotate.
    
    products_with_stock = Product.objects.annotate(
        total_kirim=Coalesce(Sum('inventorytransaction__miqdor', filter=Q(inventorytransaction__transaction_type='kirim')), 0),
        total_chiqim=Coalesce(Sum('inventorytransaction__miqdor', filter=Q(inventorytransaction__transaction_type='chiqim')), 0),
        total_sales=Coalesce(Sum('saleitems__miqdor', filter=Q(saleitems__sale__status='active')), 0)
    ).annotate(
        current_stock=F('total_kirim') - F('total_chiqim') - F('total_sales')
    )
    
    # Filter in python is still fastest if we have < 1000 products and avoids complex group by issues sometimes
    # But let's use the annotated queryset to filter
    low_stock_products = [p for p in products_with_stock if p.current_stock <= p.minimal_qoldiq]
    
    # Bugungi sotuvlar
    today = timezone.now().date()
    today_sales = Sales.objects.filter(
        sana__date=today,
        status='active'
    )
    today_sales_count = today_sales.count()
    today_revenue = today_sales.aggregate(total=Sum('jami_summa'))['total'] or 0
    
    # Jami daromad
    total_revenue = Sales.objects.filter(status='active').aggregate(total=Sum('jami_summa'))['total'] or 0
    
    # Oxirgi 7 kunlik sotuvlar (grafiklar uchun)
    last_7_days = []
    sales_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        daily_sales = Sales.objects.filter(
            sana__date=date,
            status='active'
        ).aggregate(total=Sum('jami_summa'))['total'] or 0
        last_7_days.append(date.strftime('%d.%m'))
        sales_data.append(float(daily_sales))
    
    # Eng ko'p sotiladigan mahsulotlar
    lang = get_language()
    product_name_field = f'product__nomi_{lang}' if lang in ['uz', 'ru', 'en'] else 'product__nomi_uz'
    
    top_products = SaleItems.objects.filter(
        sale__status='active'
    ).values(product_name_field).annotate(
        total_qty=Sum('miqdor'),
        total_amount=Sum('jami')
    ).order_by('-total_qty')[:5]
    
    # Rename for template consistency if necessary
    for p in top_products:
        p['display_name'] = p.get(product_name_field)
    
    # Kategoriyalar bo'yicha taqsimot
    categories = Category.objects.annotate(
        count=Count('product')
    ).order_by('-count')
    
    # We need to manually match the checks expected by the template if it calls methods
    # But since we pass 'low_stock_products' list, it is fine.
    
    context = {
        'total_products': total_products,
        'low_stock_count': len(low_stock_products),
        'today_sales_count': today_sales_count,
        'today_revenue': today_revenue,
        'total_revenue': total_revenue,
        'last_7_days': json.dumps(last_7_days),
        'sales_data': json.dumps(sales_data),
        'top_products': top_products,
        'categories': categories,
        'low_stock_products': low_stock_products[:5],
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def products_list(request):
    """Mahsulotlar ro'yxati"""
    
    # Calculate stock in DB
    products = Product.objects.select_related('kategoriya').annotate(
        total_kirim=Coalesce(Sum('inventorytransaction__miqdor', filter=Q(inventorytransaction__transaction_type='kirim')), 0),
        total_chiqim=Coalesce(Sum('inventorytransaction__miqdor', filter=Q(inventorytransaction__transaction_type='chiqim')), 0),
        total_sales=Coalesce(Sum('saleitems__miqdor', filter=Q(saleitems__sale__status='active')), 0)
    ).annotate(
        calculated_stock=F('total_kirim') - F('total_chiqim') - F('total_sales')
    ).order_by('-created_at')
    
    # Qidirish
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(nomi__icontains=search) | 
            Q(barcode__icontains=search) |
            Q(kategoriya__nomi__icontains=search)
        )
    
    # Filtrlash
    category_id = request.GET.get('category', '')
    if category_id:
        try:
            products = products.filter(kategoriya_id=category_id)
        except ValueError:
            pass # Handle invalid id gracefully
    
    # Kategoriyalar ro'yxati (independent query)
    categories = Category.objects.all()
    
    # Prepare data for template (matching simpler structure if possible, but template expects object + stock + is_low)
    # We can use the annotated object directly if we update template, 
    # but to preserve template compatibility we will map it.
    # Actually, we can just pass the annotated 'products' queryset if we update the template to use 'product.calculated_stock'.
    # However, to be safe and least intrusive:
    
    products_with_stock = []
    for product in products:
        products_with_stock.append({
            'product': product,
            'stock': product.calculated_stock,
            'is_low': product.calculated_stock <= product.minimal_qoldiq
        })
    
    context = {
        'products': products_with_stock,
        'categories': categories,
        'search': search,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else None,
    }
    
    return render(request, 'products/list.html', context)


@login_required
@user_passes_test(is_admin_or_superuser)
def product_add(request):
    """Mahsulot qo'shish"""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, _("Mahsulot '{}' muvaffaqiyatli qo'shildi!").format(product.nomi))
            return redirect('products_list')
    else:
        form = ProductForm()
    
    return render(request, 'products/add.html', {'form': form})


@login_required
@user_passes_test(is_admin_or_superuser)
def product_edit(request, pk):
    """Mahsulot tahrirlash"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, _("Mahsulot '{}' muvaffaqiyatli tahrirlandi!").format(product.nomi))
            return redirect('products_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'products/edit.html', {'form': form, 'product': product})


@login_required
@user_passes_test(is_admin_or_superuser)
def product_delete(request, pk):
    """Mahsulot o'chirish"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        product_name = product.nomi
        product.delete()
        messages.success(request, _("Mahsulot '{}' muvaffaqiyatli o'chirildi!").format(product_name))
        return redirect('products_list')
    
    return render(request, 'products/delete.html', {'product': product})


@login_required
def inventory_list(request):
    """Sklad harakatlari ro'yxati"""
    transactions = InventoryTransaction.objects.all()
    
    # Filtrlash
    transaction_type = request.GET.get('type', '')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    product_id = request.GET.get('product', '')
    if product_id:
        transactions = transactions.filter(product_id=product_id)
    
    products = Product.objects.all()
    
    context = {
        'transactions': transactions,
        'products': products,
        'selected_type': transaction_type,
        'selected_product': product_id,
    }
    
    return render(request, 'inventory/list.html', context)


@login_required
@user_passes_test(is_admin_or_superuser)
def inventory_add(request):
    """Sklad harakati qo'shish"""
    if request.method == 'POST':
        form = InventoryTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, _("Sklad harakati muvaffaqiyatli qo'shildi!"))
            return redirect('inventory_list')
    else:
        form = InventoryTransactionForm()
    
    return render(request, 'inventory/add.html', {'form': form})


@login_required
def sales_list(request):
    """Sotuvlar ro'yxati"""
    sales = Sales.objects.select_related('kassir').order_by('-sana')
    
    # Kassir faqat o'z sotuvlarini ko'radi
    if request.user.role == 'kassir':
        sales = sales.filter(kassir=request.user)
    
    # Filtrlash
    status = request.GET.get('status', '')
    if status in ['active', 'cancelled']:
        sales = sales.filter(status=status)
    
    kassir_id = request.GET.get('kassir', '')
    if kassir_id and request.user.role != 'kassir':
        sales = sales.filter(kassir_id=kassir_id)
    
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    if date_from:
        sales = sales.filter(sana__date__gte=date_from)
    if date_to:
        sales = sales.filter(sana__date__lte=date_to)

    sales = sales.annotate(items_count=Count('saleitems'))
    kassirs = CustomUser.objects.filter(role='kassir')
    stats = {
        'total_active': sales.filter(status='active').aggregate(total=Coalesce(Sum('jami_summa'), 0))['total'] or 0,
        'count_active': sales.filter(status='active').count(),
    }
    
    context = {
        'sales': sales,
        'kassirs': kassirs,
        'selected_status': status,
        'selected_kassir': kassir_id,
        'date_from': date_from,
        'date_to': date_to,
        'stats': stats,
    }
    
    return render(request, 'sales/list.html', context)


@login_required
def sale_detail(request, pk):
    """Sotuv detallari"""
    sale = get_object_or_404(Sales, pk=pk)
    
    # Kassir faqat o'z sotuvini ko'radi
    if request.user.role == 'kassir' and sale.kassir != request.user:
        messages.error(request, _("Sizda bu sotuvni ko'rish huquqi yo'q!"))
        return redirect('sales_list')
    
    items = sale.saleitems_set.select_related('product')
    total_qty = items.aggregate(total=Sum('miqdor'))['total'] or 0

    context = {
        'sale': sale,
        'items': items,
        'total_qty': total_qty,
        'can_cancel': is_admin_or_superuser(request.user) or sale.kassir == request.user,
    }
    
    return render(request, 'sales/detail.html', context)


@login_required
def sale_create(request):
    """Yangi sotuv yaratish"""
    if request.method == 'POST':
        try:
            products_data = json.loads(request.POST.get('products', '[]'))
        except json.JSONDecodeError:
            return JsonResponse({'error': _("Mahsulotlar ro'yxatini o'qib bo'lmadi!")}, status=400)

        if not products_data:
            return JsonResponse({'error': _("Hech qanday mahsulot tanlanmadi")}, status=400)

        try:
            with transaction.atomic():
                sale = Sales.objects.create(kassir=request.user, jami_summa=0)
                total = Decimal('0')
                
                for item_data in products_data:
                    product_id = item_data.get('product_id')
                    miqdor = int(item_data.get('miqdor', 0))
                    narx = Decimal(str(item_data.get('narx', 0)))
                    
                    if miqdor <= 0:
                        raise ValueError(_("Miqdor noto'g'ri"))
                    
                    product = Product.objects.get(id=product_id)
                    
                    # Qoldiqni tekshirish
                    current_stock = product.get_stock()
                    if current_stock < miqdor:
                        raise ValueError(_(
                            "Mahsulot '%(name)s' yetarli emas! Qoldiq: %(stock)s"
                        ) % {'name': product.nomi, 'stock': current_stock})
                    
                    SaleItems.objects.create(
                        sale=sale,
                        product=product,
                        miqdor=miqdor,
                        narx=narx or product.narx
                    )
                    total += Decimal(miqdor) * (narx or product.narx)
                
                # Jami summani yangilash
                sale.jami_summa = total
                sale.save(update_fields=['jami_summa'])
            
            messages.success(request, _("Sotuv #{} muvaffaqiyatli yaratildi!").format(sale.id))
            return JsonResponse({
                'redirect_url': redirect('sale_detail', pk=sale.id).url
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    products = Product.objects.annotate(
        total_kirim=Coalesce(Sum('inventorytransaction__miqdor', filter=Q(inventorytransaction__transaction_type='kirim')), 0),
        total_chiqim=Coalesce(Sum('inventorytransaction__miqdor', filter=Q(inventorytransaction__transaction_type='chiqim')), 0),
        total_sales=Coalesce(Sum('saleitems__miqdor', filter=Q(saleitems__sale__status='active')), 0)
    ).annotate(
        calculated_stock=F('total_kirim') - F('total_chiqim') - F('total_sales')
    ).filter(calculated_stock__gt=0)
    
    products_with_stock = []
    
    for product in products:
        products_with_stock.append({
            'id': product.id,
            'nomi': product.nomi,
            'narx': float(product.narx), # JSON serializable
            'barcode': product.barcode,
            'stock': product.calculated_stock
        })
    
    return render(request, 'sales/create.html', {'products': json.dumps(products_with_stock)})



@login_required
def sale_cancel(request, pk):
    """Sotuvni bekor qilish"""
    sale = get_object_or_404(Sales, pk=pk)
    
    if not (is_admin_or_superuser(request.user) or sale.kassir == request.user):
        messages.error(request, _("Sizda bu sotuvni bekor qilish huquqi yo'q!"))
        return redirect('sale_detail', pk=sale.id)
    
    if sale.status == 'cancelled':
        messages.info(request, _("Sotuv allaqachon bekor qilingan."))
        return redirect('sale_detail', pk=sale.id)
    
    if request.method == 'POST':
        sale.status = 'cancelled'
        sale.save(update_fields=['status'])
        messages.success(request, _("Sotuv #{} bekor qilindi!").format(sale.id))
        return redirect('sale_detail', pk=sale.id)
    
    return render(request, 'sales/cancel.html', {'sale': sale})


@login_required
def reports(request):
    """Hisobotlar sahifasi"""
    # Kunlik hisobot
    today = timezone.now().date()
    daily_sales = Sales.objects.filter(sana__date=today, status='active')
    daily_revenue = daily_sales.aggregate(total=Sum('jami_summa'))['total'] or 0
    
    # Haftalik hisobot
    week_ago = today - timedelta(days=7)
    weekly_sales = Sales.objects.filter(sana__date__gte=week_ago, status='active')
    weekly_revenue = weekly_sales.aggregate(total=Sum('jami_summa'))['total'] or 0
    
    # Oylik hisobot
    month_ago = today - timedelta(days=30)
    monthly_sales = Sales.objects.filter(sana__date__gte=month_ago, status='active')
    monthly_revenue = monthly_sales.aggregate(total=Sum('jami_summa'))['total'] or 0
    
    # Mahsulot qoldig'i
    products = Product.objects.all()
    low_stock_products = [p for p in products if p.is_low_stock()]
    
    # Kassirlar bo'yicha hisobot (admin va superuser)
    kassir_stats = None
    if is_admin_or_superuser(request.user):
        kassir_stats = CustomUser.objects.filter(role='kassir').annotate(
            total_sales=Count('sales', filter=Q(sales__status='active')),
            total_revenue=Sum('sales__jami_summa', filter=Q(sales__status='active'))
        )
    
    context = {
        'daily_sales_count': daily_sales.count(),
        'daily_revenue': daily_revenue,
        'weekly_sales_count': weekly_sales.count(),
        'weekly_revenue': weekly_revenue,
        'monthly_sales_count': monthly_sales.count(),
        'monthly_revenue': monthly_revenue,
        'low_stock_products': low_stock_products,
        'kassir_stats': kassir_stats,
    }
    
    return render(request, 'reports/index.html', context)


@login_required
@user_passes_test(is_superuser)
def users_list(request):
    """Foydalanuvchilar ro'yxati (faqat superuser)"""
    users = CustomUser.objects.all()
    
    context = {
        'users': users,
    }
    
    return render(request, 'users/list.html', context)


@login_required
@user_passes_test(is_superuser)
def user_add(request):
    """Foydalanuvchi qo'shish (faqat superuser)"""
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, _("Foydalanuvchi '{}' muvaffaqiyatli qo'shildi!").format(user.username))
            return redirect('users_list')
    else:
        form = UserForm()
    
    return render(request, 'users/add.html', {'form': form})


@login_required
@user_passes_test(is_superuser)
def user_edit(request, pk):
    """Foydalanuvchi tahrirlash (faqat superuser)"""
    user = get_object_or_404(CustomUser, pk=pk)
    
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Foydalanuvchi '{}' muvaffaqiyatli tahrirlandi!").format(user.username))
            return redirect('users_list')
    else:
        form = UserForm(instance=user)
    
    return render(request, 'users/edit.html', {'form': form, 'user': user})


@login_required
@user_passes_test(is_superuser)
def user_delete(request, pk):
    """Foydalanuvchi o'chirish (faqat superuser)"""
    user = get_object_or_404(CustomUser, pk=pk)
    
    if user == request.user:
        messages.error(request, _("O'zingizni o'chira olmaysiz!"))
        return redirect('users_list')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, _("Foydalanuvchi '{}' muvaffaqiyatli o'chirildi!").format(username))
        return redirect('users_list')
    
    return render(request, 'users/delete.html', {'user': user})
