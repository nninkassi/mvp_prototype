from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    """Получение значения из словаря по ключу"""
    return dictionary.get(key)