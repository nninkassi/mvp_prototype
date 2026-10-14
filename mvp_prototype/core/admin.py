from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Role, User, Category, Product, Cart, Order
from .models import NotificationLog
admin.site.register(NotificationLog)
admin.site.register(Role)
admin.site.register(User)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Cart)
admin.site.register(Order)