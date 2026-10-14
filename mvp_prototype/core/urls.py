from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.catalog, name='home'), 
    path('catalog/', views.catalog, name='catalog'),
    path('register/', views.register_user, name='register'),
    # path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('product/<int:product_id>/', views.product_detail, name='product'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:product_id>/<str:action>/', views.update_cart_item, name='update_cart_item'),
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('policy/', views.policy_page, name='policy'),
    path('seller/stats/', views.seller_stats, name='seller_stats'),

    path('login/', views.login_user, {'portal': 'buyer'}, name='login'),
    path('login/buyer/', views.login_user, {'portal': 'buyer'}, name='login_buyer'),
    path('login/seller/', views.login_user, {'portal': 'seller'}, name='login_seller'),

    path('seller/add-product/', views.add_product, name='add_product'),

    path('seller/edit-product/<int:product_id>/', views.edit_product, name='edit_product'),

    path('seller/products/', views.seller_products, name='seller_products'),
    path('payment/mock/<int:order_id>/', views.payment_gateway_mock, name='payment_gateway_mock'),
    path('success/', views.payment_success, name='success'),
]   

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)