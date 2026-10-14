from django import template
from ..models import User

register = template.Library()

@register.simple_tag
def get_current_user(request):
    """Возвращает объект пользователя из сессии для использования в шаблоне"""
    user_id = request.session.get('user_id')
    if user_id:
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
    return None