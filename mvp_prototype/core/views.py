from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Category, Cart, CartItem, Order, OrderItem, User
from django.db.models import Q
from .services import process_payment_mock, send_notification_mock
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .services import process_payment_mock, send_notification_mock, wms_reserve_stock_mock
from django.contrib.auth.decorators import login_required  
# ================= АВТОРИЗАЦИЯ =================


def register_user(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        name = request.POST.get('name')
        password = request.POST.get('password')
        consent = request.POST.get('consent')
        
        if not consent:
            return render(request, 'core/register.html', {'error': 'Необходимо дать согласие на обработку ПДн'})
            
        if User.objects.filter(email=email).exists():
            return render(request, 'core/register.html', {'error': 'Этот Email уже занят'})
            
        from .models import Role
        default_role = Role.objects.first()
        if not default_role:
            default_role = Role.objects.create(name="Покупатель", description="Стандартная роль")
            
        User.objects.create(
            email=email,
            name=name,
            password_hash=make_password(password),
            role=default_role,
            consent_date=timezone.now()  # Фиксируем дату согласия
        )
        
        user = User.objects.get(email=email)
        request.session['user_id'] = user.id
        return redirect('catalog')
        
    return render(request, 'core/register.html')

def login_user(request, portal='buyer'):
    """Единая аутентификация с ролевой маршрутизацией"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user = User.objects.get(email=email)
            if check_password(password, user.password_hash):
                request.session['user_id'] = user.id
                
                # Ролевая маршрутизация после входа
                if user.role.name == 'seller':
                    return redirect('seller_stats')
                else:
                    return redirect('catalog')
                    
            else:
                return render(request, 'core/login.html', {
                    'error': 'Неверный пароль', 
                    'portal': portal
                })
        except User.DoesNotExist:
            return render(request, 'core/login.html', {
                'error': 'Пользователь не найден', 
                'portal': portal
            })
            
    return render(request, 'core/login.html', {'portal': portal})

def logout_user(request):
    """Выход"""
    if 'user_id' in request.session:
        del request.session['user_id']
    return redirect('catalog')

def get_current_user(request):
    """Хелпер для получения текущего юзера"""
    user_id = request.session.get('user_id')
    if user_id:
        return User.objects.get(id=user_id)
    return None

# ================= КАТАЛОГ =================

def catalog(request):
    """Каталог с фильтрацией по категории и поиском"""
    category_id = request.GET.get('category')
    query = request.GET.get('q', '').strip()  # Получаем поисковый запрос
    
    products = Product.objects.all()

    # Фильтр по категории
    if category_id:
        products = products.filter(category_id=category_id)

    # Поиск по названию ИЛИ автору
    if query:
        products = products.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )

    categories = Category.objects.all()
    
    # Данные корзины (без изменений)
    cart_items_count = {}
    user = get_current_user(request)
    if user:
        try:
            cart = Cart.objects.get(user=user)
            cart_items_count = {item.product_id: item.quantity for item in cart.items.all()}
        except Cart.DoesNotExist:
            pass
    
    return render(request, 'core/catalog.html', {
        'products': products, 
        'categories': categories,
        'active_category': int(category_id) if category_id else None,
        'cart_items_count': cart_items_count,
        'query': query  # Передаём запрос, чтобы он оставался в поле ввода
    })

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Считаем, сколько этого товара уже в корзине
    cart_quantity = 0
    user = get_current_user(request)
    if user:
        try:
            cart = Cart.objects.get(user=user)
            item = CartItem.objects.get(cart=cart, product_id=product_id)
            cart_quantity = item.quantity
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            pass
            
    return render(request, 'core/product.html', {
        'product': product,
        'cart_quantity': cart_quantity
    })

# ================= КОРЗИНА =================

def add_to_cart(request, product_id):
    user = get_current_user(request)
    if not user:
        return redirect('login') # Требует входа
        
    # Ищем корзину пользователя
    cart, created = Cart.objects.get_or_create(user=user)
    
    # Ищем товар в корзине
    item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)
    if not created:
        item.quantity += 1
    item.save()

    return redirect(request.META.get('HTTP_REFERER', 'catalog'))

def cart(request):
    """Экран корзины: только товары и кнопка перехода к оформлению"""
    user = get_current_user(request)
    cart_items = []
    total = 0
    
    if user:
        try:
            cart = Cart.objects.get(user=user)
            items = cart.items.all().select_related('product')
            for item in items:
                item.total_price = item.product.price * item.quantity
                total += item.total_price
                cart_items.append(item)
        except Cart.DoesNotExist:
            pass
            
    return render(request, 'core/cart.html', {
        'cart_items': cart_items,
        'total': total,
        'user': user
    })
    \

def checkout(request):
    """Оформление заказа: форма + логика оплаты"""
    user = get_current_user(request)
    if not user:
        return redirect('login')

    # === Вспомогательная функция для получения корзины ===
    def get_cart_data(user):
        """Возвращает (cart_items, total) или (None, 0)"""
        cart_items = []
        total = 0
        try:
            cart = Cart.objects.get(user=user)
            items = cart.items.all().select_related('product')
            for item in items:
                item.total_price = item.product.price * item.quantity
                total += item.total_price
                cart_items.append(item)
        except Cart.DoesNotExist:
            pass
        return cart_items, total

    # Получаем данные корзины СРАЗУ (для отображения формы и ошибок)
    cart_items, total = get_cart_data(user)

    if request.method == 'POST':
        address = request.POST.get('address')
        print(f"📦 POST получен. Адрес: {address}")  # ← ОТЛАДКА
        
        # Проверяем, что корзина не пуста
        if not cart_items:
            print("⚠️ Корзина пуста → редирект на cart")
            return redirect('cart')
            
        try:
            # Получаем "сырые" элементы для WMS (без вычислений)
            cart = Cart.objects.get(user=user)
            items = cart.items.all()
            
            if not items:
                print("⚠️ В базе нет элементов корзины → редирект на cart")
                return redirect('cart')

            # 1. Обращаемся к WMS для резервирования
            wms_result = wms_reserve_stock_mock(items)
            print(f"🚚 WMS ответ: {wms_result}")  # ← ОТЛАДКА: СМОТРИ СЮДА
            
            # Проверяем, хватило ли товара
            if any(r["status"] == "out_of_stock" for r in wms_result):
                print("⚠️ Сработала проверка: НЕТ ТОВАРА НА СКЛАДЕ")
                return render(request, 'core/checkout.html', {
                    'user': user,
                    'cart_items': cart_items,
                    'total': total,
                    'error': 'Недостаточно товара на складе. Остатки обновлены.'
                })

            total_cost = sum(item.product.price * item.quantity for item in items)
            print(f"💰 Сумма заказа: {total_cost} ₽")

            # 2. Создаём заказ
            order = Order.objects.create(
                buyer=user,
                status='processing',
                total_cost=total_cost,
                delivery_address=address,
                payment_method='card'
            )
            print(f"📦 Заказ создан: ID={order.id}")

            # 3. Создаём позиции заказа
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_purchase=item.product.price
                )
            print(f"📋 Создано позиций заказа: {items.count()}")

            # 4. Платёж и уведомления
            payment_result = process_payment_mock(total_cost, order.id)
            print(f"💳 ПЛАТЁЖ ответ: {payment_result}")  # ← ОТЛАДКА: И СЮДА
            
            if payment_result["status"] == "success":
                print("✅ Платёж успешен → переход на success.html")
                order.status = 'paid'
                order.save()
                send_notification_mock(user, "order_confirmation", {"order_id": order.id})
                cart.items.all().delete()
                
                # return render(request, 'core/success.html', {
                #     'order_id': order.id,
                #     'transaction_id': payment_result['transaction_id']
                # })

                return redirect('payment_gateway_mock', order_id=order.id)

            else:
                print("❌ Платёж НЕ успешен → возврат на форму с ошибкой")
                # В реальном проекте: откат резерва WMS
                order.status = 'failed'
                order.save()
                return render(request, 'core/checkout.html', {
                    'user': user,
                    'cart_items': cart_items,
                    'total': total,
                    'error': 'Платёж не прошёл. Товар зарезервирован на 30 мин.'
                })
                
        except Cart.DoesNotExist:
            print("❌ Ошибка: корзина не найдена в БД")
            return redirect('cart')
        except Exception as e:
            print(f"💥 КРИТИЧЕСКАЯ ОШИБКА в checkout: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()  # Покажет полный стектрейс в консоли
            return render(request, 'core/checkout.html', {
                'user': user,
                'cart_items': cart_items,
                'total': total,
                'error': f'Произошла ошибка при оформлении: {e}'
            })

    # GET-запрос: просто показываем форму
    print("📄 GET-запрос: показываем форму checkout")
    return render(request, 'core/checkout.html', {
        'user': user,
        'cart_items': cart_items,
        'total': total
    })

# @login_required
def profile(request):
    user = get_current_user(request)
    if not user:
        return redirect('login')
    
    # Берем заказы пользователя
    orders = Order.objects.filter(buyer=user).order_by('-created_at')
    
    return render(request, 'core/profile.html', {'user': user, 'orders': orders})



def update_cart_item(request, product_id, action):
    """Изменение количества товара в корзине (+ или -)"""
    user = get_current_user(request)
    if not user:
        return redirect('login')
    
    try:
        cart = Cart.objects.get(user=user)
        item = CartItem.objects.get(cart=cart, product_id=product_id)
        
        if action == 'add':
            item.quantity += 1
            item.save()
        elif action == 'remove':
            item.quantity -= 1
            if item.quantity <= 0:
                item.delete()
            else:
                item.save()
        elif action == 'delete':
            item.delete()
            
    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        pass
    
    # Возвращаемся на ту же страницу, откуда пришли
    return redirect(request.META.get('HTTP_REFERER', 'catalog'))

def policy_page(request):
    """Страница политики обработки ПДн"""
    return render(request, 'core/policy.html')

from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from decimal import Decimal, ROUND_HALF_UP

from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from .models import OrderItem, Order
# ... остальные ваши импорты ...

def seller_stats(request):
    """Статистика продавца: продажи, товары, статусы"""
    user = get_current_user(request)
    if not user:
        return redirect('login')
    
    if user.role.name != 'seller':
        return redirect('catalog')
    
    # 1. ПРОДАЖИ ПО ПЕРИОДАМ (последние 7 дней)
    sales_by_period = OrderItem.objects.filter(
        product__seller=user,
        order__status='paid',
        order__created_at__gte=timezone.now() - timedelta(days=7)
    ).annotate(
        date=TruncDate('order__created_at')
    ).values('date').annotate(
        total_sales=Sum(F('quantity') * F('price_at_purchase')),
        orders_count=Count('order_id', distinct=True)
    ).order_by('date')

    for item in sales_by_period:
        item['total_sales'] = float(Decimal(str(item['total_sales'] or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    # 2. ВСЕ ПРОДАННЫЕ ТОВАРЫ (ограничение [:5] убрано для корректной суммы)
    top_products = OrderItem.objects.filter(
        product__seller=user,
        order__status='paid'
    ).values(
        'product__title',
        'product__id',
        'product__stock_quantity'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('price_at_purchase'))
    ).order_by('-total_revenue')  # <-- Убрали [:5]
    
    for item in top_products:
        item['total_revenue'] = float(Decimal(str(item['total_revenue'] or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    # 3. СТАТУСЫ ЗАКАЗОВ
    orders_by_status = Order.objects.filter(
        items__product__seller=user
    ).values('status').annotate(
        count=Count('id', distinct=True)
    ).order_by('-count')
    
    # Общие цифры
    total_revenue = OrderItem.objects.filter(
        product__seller=user,
        order__status='paid'
    ).aggregate(
        total=Sum(F('quantity') * F('price_at_purchase'))
    )['total'] or 0
    
    total_revenue = float(Decimal(str(total_revenue)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    total_orders = Order.objects.filter(
        items__product__seller=user
    ).distinct().count()
    
    return render(request, 'core/seller_stats.html', {
        'sales_by_period': sales_by_period,
        'top_products': top_products,
        'orders_by_status': orders_by_status,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
    })
def add_product(request):
    """Страница добавления товара для продавца"""
    user = get_current_user(request)
    
    # Только продавец может добавить товар
    if not user or user.role.name != 'seller':
        return redirect('catalog')

    # Получаем категории для выбора в форме
    categories = Category.objects.all()

    if request.method == 'POST':
        # Создаем товар
        Product.objects.create(
            seller=user, # Привязываем к текущему продавцу
            category_id=request.POST.get('category'),
            title=request.POST.get('title'),
            author=request.POST.get('author'),
            price=request.POST.get('price'),
            description=request.POST.get('description'),
            stock_quantity=int(request.POST.get('stock_quantity', 0)),
            image_url=request.POST.get('image_url') or 'https://via.placeholder.com/150'
        )
        # После добавления возвращаем на статистику
        return redirect('seller_stats')

    return render(request, 'core/add_product.html', {'categories': categories})
# @login_required
def edit_product(request, product_id):
    user = get_current_user(request)
    if not user or user.role.name != 'seller':  # Убедись, что в БД роль называется именно так
        return redirect('catalog')
        
    product = get_object_or_404(Product, id=product_id, seller=user)
    
    if request.method == 'POST':
        product.title = request.POST.get('title')
        product.author = request.POST.get('author')
        product.price = request.POST.get('price')
        product.stock_quantity = request.POST.get('stock_quantity')
        product.description = request.POST.get('description')
        product.category_id = request.POST.get('category')  # Важно: сохраняем выбранную категорию
        product.save()
        return redirect('seller_stats')

    categories_data = []
    for cat in Category.objects.all():
        categories_data.append({
            'id': cat.id,
            'name': cat.name,
            'is_selected': (cat.id == product.category_id)  # Сравнение здесь, в Python
        })
        
    return render(request, 'core/edit_product.html', {
        'product': product,
        'categories': categories_data  # Передаём готовый список в шаблон
    })

# @login_required 
def seller_products(request):
    """Главная страница продавца: список всех его товаров"""
    user = get_current_user(request)
    if not user or user.role.name != 'seller':
        return redirect('catalog')
        
    products = Product.objects.filter(seller=user).order_by('-created_at')
    return render(request, 'core/seller_products.html', {'products': products})


def payment_gateway_mock(request, order_id):
    """Имитация страницы платежного шлюза"""
    user = get_current_user(request)
    if not user:
        return redirect('login')
        
    try:
        order = Order.objects.get(id=order_id, buyer=user)
        return render(request, 'core/payment_gateway.html', {'order': order})
    except Order.DoesNotExist:
        return redirect('catalog') # Если заказ не найден или чужой





def payment_success(request):
    """Страница успешной оплаты"""
    order_id = request.GET.get('order_id')
    transaction_id = request.GET.get('transaction_id', 'N/A')
    
    # Получаем заказ для отображения деталей (опционально)
    order = None
    if order_id:
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            pass
    
    return render(request, 'core/success.html', {
        'order_id': order_id,
        'transaction_id': transaction_id,
        'order': order
    })