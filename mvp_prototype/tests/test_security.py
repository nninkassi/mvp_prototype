import requests
import pytest

BASE_URL = "http://127.0.0.1:8000"

# === ПРОВЕРКА ДОСТУПА К СТРАНИЦАМ (GET-запросы) ===

def test_anonymous_cannot_view_seller_stats():
    """TC-SEC-001: Статистика продавца недоступна без авторизации"""
    r = requests.get(f"{BASE_URL}/seller/stats/")
    assert r.status_code != 200, "Статистика продавца доступна анониму"

def test_anonymous_cannot_view_checkout():
    """TC-SEC-002: Страница оформления заказа недоступна без авторизации"""
    r = requests.get(f"{BASE_URL}/checkout/")
    assert r.status_code != 200, "Оформление заказа доступно анониму"

def test_anonymous_cannot_view_profile():
    """TC-SEC-003: Личный профиль недоступен без авторизации"""
    r = requests.get(f"{BASE_URL}/profile/")
    assert r.status_code != 200, "Профиль пользователя доступен анониму"

# === ПРОВЕРКА ЗАЩИТЫ ДЕЙСТВИЙ (POST-запросы) ===

def test_anonymous_cannot_add_to_cart():
    """TC-SEC-004: Добавление в корзину блокируется без авторизации"""
    # Пытаемся добавить товар с любым ID (например, 1)
    r = requests.post(f"{BASE_URL}/add_to_cart/1/")
    # Должен быть редирект на вход (302) или ошибка (403)
    assert r.status_code != 200, "Добавление в корзину доступно без входа"

def test_anonymous_cannot_checkout():
    """TC-SEC-005: Оформление заказа (POST) блокируется без авторизации"""
    r = requests.post(f"{BASE_URL}/checkout/", data={"address": "тест"})
    assert r.status_code != 200, "Оформление заказа (POST) доступно без входа"

# === ПРОВЕРКА ЗАЩИТЫ КАБИНЕТА ПРОДАВЦА ===

def test_anonymous_cannot_view_seller_products():
    """TC-SEC-006: Список товаров продавца недоступен без авторизации"""
    r = requests.get(f"{BASE_URL}/seller/products/")
    assert r.status_code != 200, "Кабинет продавца доступен анониму"

def test_anonymous_cannot_edit_product():
    """TC-SEC-007: Редактирование товара недоступно без авторизации"""
    # Пытаемся открыть форму редактирования товара с ID=1
    r = requests.get(f"{BASE_URL}/seller/edit-product/1/")
    assert r.status_code != 200, "Редактирование товара доступно без входа"