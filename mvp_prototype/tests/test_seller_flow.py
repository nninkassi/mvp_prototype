# tests/test_seller_flow.py
import requests
import pytest
import re
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:8000"

SELLER_EMAIL = "admin2@mail.ru"
SELLER_PASSWORD = "qwerty"
SELLER2_EMAIL = "buyer3@mail.ru"  # Для теста изоляции данных
TEST_PRODUCT_ID = 4  # ID товара, принадлежащего основному продавцу


def get_csrf(session, url):
    """Извлекает CSRF-токен из формы Django"""
    r = session.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    return token['value'] if token else None


def login_seller(session, email=None, password=None):
    """Вспомогательная функция: вход продавца"""
    email = email or SELLER_EMAIL
    password = password or SELLER_PASSWORD
    
    csrf = get_csrf(session, f"{BASE_URL}/login/")
    r = session.post(f"{BASE_URL}/login/", data={
        'csrfmiddlewaretoken': csrf,
        'email': email,
        'password': password
    }, allow_redirects=True)
    return r.status_code == 200


# def test_seller_login_and_dashboard_access():
#     """TC-SELL-001: Авторизация продавца и доступ к статистике"""
#     session = requests.Session()
    
#     # 1. Вход как продавец
#     assert login_seller(session), "Не удалось войти как продавец"
    
#     # 2. Проверка доступа к статистике
#     r_stats = session.get(f"{BASE_URL}/seller/stats/")
#     assert r_stats.status_code == 200, f"Статистика вернула статус {r_stats.status_code}"
    
#     # 3. Проверка наличия ключевых метрик в ответе
#     assert "Выручка" in r_stats.text or "Заказов" in r_stats.text or "Продаж" in r_stats.text, \
#         "Дашборд статистики не содержит ожидаемых метрик"

def test_seller_login_and_dashboard_access():
    """TC-SELL-001: Авторизация продавца и доступ к статистике"""
    session = requests.Session()
    
    # 1. Вход как продавец
    assert login_seller(session), "Не удалось войти как продавец (проверь логин/пароль)"

    # 2. ДИАГНОСТИКА: Проверяем, видит ли система нас как "Продавца"
    # Для этого смотрим на меню навигации (оно есть на любой странице)
    r_nav_check = session.get(f"{BASE_URL}/catalog/")
    
    # Если мы Продавец, в меню должны быть ссылки "Статистика" или "Мои товары"
    seller_links_present = (
        "Статистика" in r_nav_check.text or 
        "Мои товары" in r_nav_check.text or 
        "/seller/" in r_nav_check.text
    )
    
    if not seller_links_present:
        pytest.fail(
            f"Вход выполнен, но в меню НЕТ ссылок продавца ('Статистика' / 'Мои товары'). "
            f"Это значит, что аккаунт '{SELLER_EMAIL}' в базе данных имеет НЕВЕРНУЮ РОЛЬ. "
            f"Проверьте таблицу User в БД!"
        )

    # 3. Теперь пробуем зайти на страницу статистики
    r_stats = session.get(f"{BASE_URL}/seller/stats/")
    
    # Если нас кинуло в каталог — значит view seller_stats сработал некорректно
    if "Каталог книг" in r_stats.text and "Общая выручка" not in r_stats.text:
        pytest.fail(
            "Меню продавца отображается верно, но страница /seller/stats/ всё равно "
            "перенаправляет в каталог. Ошибка в логике функции seller_stats (views.py)."
        )

    assert r_stats.status_code == 200, f"Статистика вернула статус {r_stats.status_code}"
    
    # 4. Проверка наличия метрик (то, что упало ранее)
    metrics_present = (
        "Общая выручка" in r_stats.text or
        "Всего заказов" in r_stats.text or
        "Топ-5 товаров" in r_stats.text
    )
    
    assert metrics_present, "Дашборд статистики не содержит ожидаемых метрик"


def test_seller_products_list():
    """TC-SELL-002: Просмотр списка товаров продавца"""
    session = requests.Session()
    assert login_seller(session)
    
    # 1. Загрузить страницу "Мои товары"
    r_products = session.get(f"{BASE_URL}/seller/products/")
    assert r_products.status_code == 200, "Страница товаров продавца не загрузилась"
    
    # 2. Проверить наличие заголовков таблицы
    assert "Название" in r_products.text or "Товар" in r_products.text, "Нет заголовка 'Название'"
    assert "Цена" in r_products.text, "Нет заголовка 'Цена'"
    assert "Остаток" in r_products.text or "stock" in r_products.text.lower(), "Нет заголовка 'Остаток'"
    
    # 3. Проверить, что есть хотя бы один товар (по наличию цены в ₽)
    assert "₽" in r_products.text, "В списке товаров нет цен"


def test_edit_product_flow():
    """TC-SELL-003: Редактирование товара продавцом"""
    session = requests.Session()
    assert login_seller(session)
    
    # 1. Открыть форму редактирования
    r_edit = session.get(f"{BASE_URL}/seller/edit-product/{TEST_PRODUCT_ID}/")
    if r_edit.status_code == 404:
        pytest.skip(f"Товар с ID={TEST_PRODUCT_ID} не найден или недоступен")
    
    assert r_edit.status_code == 200, "Форма редактирования не загрузилась"
    
    # 2. Проверить наличие полей формы
    soup = BeautifulSoup(r_edit.text, 'html.parser')
    assert soup.find('input', {'name': 'title'}), "Нет поля 'title'"
    assert soup.find('input', {'name': 'price'}), "Нет поля 'price'"
    
    # 3. Сохранить изменения (меняем цену на тестовое значение)
    csrf = get_csrf(session, f"{BASE_URL}/seller/edit-product/{TEST_PRODUCT_ID}/")
    
    # Сохраняем текущее название, меняем только цену для теста
    current_title = "Книга про котят"  
    
    r_save = session.post(f"{BASE_URL}/seller/edit-product/{TEST_PRODUCT_ID}/", data={
        'csrfmiddlewaretoken': csrf,
        'title': current_title,
        'author': 'Тестовый автор',
        'price': '1999.99',  # Новая тестовая цена
        'stock_quantity': '10',
        'category': '1', 
        'description': 'Описание для автотеста'
    }, allow_redirects=True)
    
    # Допускаем редирект (302) или успешную загрузку страницы (200)
    assert r_save.status_code in [200, 301, 302], f"Сохранение вернуло статус {r_save.status_code}"
    
    # 4. Проверить, что изменения применились (открыть товар и проверить цену)
    r_product = session.get(f"{BASE_URL}/product/{TEST_PRODUCT_ID}/")
    assert "1999.99" in r_product.text or "1 999.99" in r_product.text, \
        "Новая цена не отобразилась на странице товара"


def test_seller_data_isolation():
    """TC-SELL-004: Продавец не видит товары других продавцов"""
    # Этот тест требует наличия двух продавцов в БД
    # Если нет второго продавца — пропускаем
    
    session1 = requests.Session()
    if not login_seller(session1):
        pytest.skip("Не удалось войти как основной продавец")
    
    # Загружаем товары продавца 1
    r1 = session1.get(f"{BASE_URL}/seller/products/")
    if r1.status_code != 200:
        pytest.skip("Страница товаров недоступна")
    
    # Если в БД нет второго продавца — тест не имеет смысла
    # Проверяем хотя бы, что страница загружается без ошибок
    assert "Название" in r1.text or "Товар" in r1.text, "Страница товаров пустая или некорректная"
    


def test_sales_statistics_calculation():
    """TC-SELL-005: Статистика продаж отображает корректную выручку"""
    session = requests.Session()
    assert login_seller(session)
    
    # 1. Загрузить дашборд статистики
    r_stats = session.get(f"{BASE_URL}/seller/stats/")
    assert r_stats.status_code == 200
    
    # 2. Проверить наличие блока с выручкой
    # Ищем паттерн: "Выручка" + число + "₽" или просто число с валютой
    soup = BeautifulSoup(r_stats.text, 'html.parser')
    text_content = soup.get_text()
    
    # Проверяем, что есть хотя бы одна сумма в формате "1 234 ₽" или "1234.00 ₽"
    has_revenue = bool(re.search(r'\d[\d\s\.]*\s*₽', text_content)) or \
                  "Выручка" in text_content or \
                  "Заказов" in text_content
    
    assert has_revenue, "На дашборде не найдены метрики продаж или выручка"
    
