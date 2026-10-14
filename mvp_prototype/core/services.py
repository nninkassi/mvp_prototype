import time
from django.utils import timezone
from .models import NotificationLog

def process_payment_mock(total_amount, order_id):
    """
    Имитация запроса к внешнему платёжному шлюзу.
    В продакшене здесь: requests.post(url, json=payload, headers=auth_headers)
    """
    time.sleep(0.6)  # Имитация сетевой задержки и обработки на стороне банка
    transaction_id = f"TXN-{order_id}-{timezone.now().strftime('%H%M%S')}"
    return {
        "status": "success",
        "transaction_id": transaction_id,
        "message": "Оплата проведена успешно"
    }

def send_notification_mock(user, event_type, context_data):
    """
    Имитация отправки уведомления (Email / SMS / Push).
    В продакшене здесь: rabbitmq.publish() или celery.delay()
    """
    time.sleep(0.3)
    NotificationLog.objects.create(
        user=user,
        event_type=event_type,
        status="sent",
        created_at=timezone.now()
    )
    return True

def wms_reserve_stock_mock(items):
    """
    Имитация обращения к складской системе (WMS).
    В проде: POST /api/wms/reserve {"order_id": ..., "lines": [...]}
    """
    time.sleep(0.4)  # Имитация сетевого latency
    result = []
    
    for item in items:
        product = item.product
        if product.stock_quantity >= item.quantity:
            product.stock_quantity -= item.quantity
            product.save()
            result.append({"sku": product.title, "qty": item.quantity, "status": "reserved"})
        else:
            result.append({"sku": product.title, "qty": item.quantity, "status": "out_of_stock"})
            
    return result