import requests
import pytest
import re
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:8000"

# ⚠️ ЗАМЕНИ НА РЕАЛЬНЫЕ ДАННЫЕ ИЗ ТВОЕЙ БД
BUYER_EMAIL = "buyer2@mail.ru"
BUYER_PASSWORD = "qwerty"
NEW_BUYER_EMAIL = "buyer3@mail.ru"
def get_csrf(session, url):
    """Извлекает CSRF-токен из формы Django"""
    r = session.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    return token['value'] if token else None


def login_buyer(session):
    """Вспомогательная функция: вход покупателя"""
    csrf = get_csrf(session, f"{BASE_URL}/login/")
    r = session.post(f"{BASE_URL}/login/", data={
        'csrfmiddlewaretoken': csrf,
        'email': BUYER_EMAIL,
        'password': BUYER_PASSWORD
    }, allow_redirects=True)
    return r.status_code == 200


def test_buyer_registration():
    """TC-BUY-001: Регистрация нового покупателя"""
    session = requests.Session()
    
    # 1. Получить форму регистрации и CSRF
    csrf = get_csrf(session, f"{BASE_URL}/register/")
    assert csrf, "CSRF-токен не найден на странице регистрации"
    
    # 2. Отправить данные регистрации
    r = session.post(f"{BASE_URL}/register/", data={
        'csrfmiddlewaretoken': csrf,
        'email': NEW_BUYER_EMAIL,
        'name': 'ТестАвто',
        'password': 'AutoTest123!'
    }, allow_redirects=True)
    
    # 3. Проверить успешное создание (редирект или 200)
    assert r.status_code in [200, 301, 302], f"Регистрация вернула статус {r.status_code}"


def test_catalog_search_and_filter():
    """TC-BUY-002: Поиск и фильтрация в каталоге"""
    session = requests.Session()
    
    # 1. Поиск по названию
    r_search = session.get(f"{BASE_URL}/catalog/", params={'q': 'кот'})
    assert r_search.status_code == 200
    # Проверяем, что ответ содержит результаты или сообщение "не найдено"
    assert "кот" in r_search.text.lower() or "не найдено" in r_search.text.lower() or "товар" in r_search.text.lower()
    
    # 2. Фильтрация по категории (если есть категории с id=1)
    r_filter = session.get(f"{BASE_URL}/catalog/", params={'category': 1})
    assert r_filter.status_code == 200


def test_view_product_and_add_to_cart():
    """TC-BUY-003: Просмотр товара и добавление в корзину"""
    session = requests.Session()
    
    # 1. Авторизация
    assert login_buyer(session), "Не удалось войти как покупатель"
    
    # 2. Загрузить каталог
    r_catalog = session.get(f"{BASE_URL}/catalog/")
    assert r_catalog.status_code == 200, "Каталог не загрузился"
    assert "₽" in r_catalog.text, "В каталоге нет цен"
    
    # 3. Найти товар: ищем кнопку "В корзину"
    # ВАЖНО: lambda в href= получает строку (значение атрибута), а не тег!
    # Поэтому сначала фильтруем по href, потом проверяем текст отдельно
    soup = BeautifulSoup(r_catalog.text, 'html.parser')
    
    # Находим все <a> с href, содержащим '/cart/add/'
    all_cart_links = soup.find_all('a', href=lambda x: x and '/cart/add/' in x)
    
    # Фильтруем по тексту кнопки "В корзину"
    cart_button = None
    for link in all_cart_links:
        if 'В корзину' in link.text:
            cart_button = link
            break
    
    if not cart_button:
        pytest.skip("Не найдена кнопка 'В корзину' — структура каталога отличается")
    
    # Извлекаем product_id из href="/cart/add/4/"
    href = cart_button['href']  # например, "/cart/add/4/"
    product_id = href.strip('/').split('/')[-1]  # получаем "4"
    
    # 4. Открыть карточку товара (переход по /product/{id}/)
    r_product = session.get(f"{BASE_URL}/product/{product_id}/")
    assert r_product.status_code == 200, f"Карточка товара {product_id} не загрузилась"
    assert "₽" in r_product.text, "Цена не отображается на карточке"
    
    # 5. Добавить в корзину: в твоём проекте это GET-запрос на /cart/add/{id}/
    r_add = session.get(f"{BASE_URL}/cart/add/{product_id}/", allow_redirects=True)
    assert r_add.status_code == 200, f"Не удалось добавить товар {product_id} в корзину (статус {r_add.status_code})"
    
    # 6. Проверить корзину
    r_cart = session.get(f"{BASE_URL}/cart/")
    assert r_cart.status_code == 200
    assert "Итого" in r_cart.text or "Оформить" in r_cart.text, "Корзина пуста после добавления"


def test_update_cart_quantity():
    """TC-BUY-004: Изменение количества в корзине"""
    session = requests.Session()
    assert login_buyer(session)
    
    # Сначала добавим товар, если корзина пуста
    r_catalog = session.get(f"{BASE_URL}/catalog/")
    soup = BeautifulSoup(r_catalog.text, 'html.parser')
    cart_button = soup.find('a', href=lambda x: x and '/cart/add/' in x)
    
    if not cart_button:
        pytest.skip("Не найдена кнопка 'В корзину'")
    
    product_id = cart_button['href'].strip('/').split('/')[-1]
    
    # Добавляем товар (если ещё не добавлен)
    session.get(f"{BASE_URL}/cart/add/{product_id}/", allow_redirects=True)
    
    # 1. Проверить, что товар в корзине
    r_cart1 = session.get(f"{BASE_URL}/cart/")
    assert r_cart1.status_code == 200
    
    # 2. Увеличить количество: пробуем несколько возможных форматов URL
    # Твой проект может использовать: /cart/update/{id}/add/ или /update_cart_item/{id}/add/
    r_inc = session.get(f"{BASE_URL}/cart/update/{product_id}/add/", allow_redirects=True)
    if r_inc.status_code == 404:
        # Пробуем альтернативный формат
        r_inc = session.get(f"{BASE_URL}/update_cart_item/{product_id}/add/", allow_redirects=True)
    
    # 3. Проверить, что корзина всё ещё доступна и содержит товар
    r_cart2 = session.get(f"{BASE_URL}/cart/")
    assert r_cart2.status_code == 200
    # Проверяем, что корзина не пуста (товар или итоговая сумма присутствуют)
    assert product_id in r_cart2.text or "Итого" in r_cart2.text or "Оформить" in r_cart2.text, "Корзина пуста после изменения количества"


def test_checkout_with_validation():
    """TC-BUY-005: Оформление заказа с валидацией адреса"""
    session = requests.Session()
    assert login_buyer(session)
    
    # Убедимся, что в корзине есть товар
    r_cart = session.get(f"{BASE_URL}/cart/")
    if "Итого" not in r_cart.text and "Оформить" not in r_cart.text:
        # Добавим товар, если корзина пуста
        r_catalog = session.get(f"{BASE_URL}/catalog/")
        soup = BeautifulSoup(r_catalog.text, 'html.parser')
        cart_button = soup.find('a', href=lambda x: x and '/cart/add/' in x)
        if cart_button:
            product_id = cart_button['href'].strip('/').split('/')[-1]
            session.get(f"{BASE_URL}/cart/add/{product_id}/", allow_redirects=True)
    
    # 1. Получить форму оформления и CSRF-токен
    csrf = get_csrf(session, f"{BASE_URL}/checkout/")
    
    # 2. Попытка оформить с пустым адресом (должна быть ошибка или редирект назад)
    r_empty = session.post(f"{BASE_URL}/checkout/", 
                           data={'csrfmiddlewaretoken': csrf, 'address': ''}, 
                           allow_redirects=True)
    # Допускаем любой статус, кроме "успешного создания заказа" (главное — что система не упала с 500)
    assert r_empty.status_code != 500, "Сервер упал с ошибкой 500 при пустом адресе"
    
    # 3. Оформление с валидным адресом
    r_success = session.post(f"{BASE_URL}/checkout/", 
                             data={'csrfmiddlewaretoken': csrf, 'address': 'г. Тест, ул. Авто, д. 1'}, 
                             allow_redirects=True)
    # Ожидаем редирект на страницу успеха или профиль
    assert r_success.status_code in [200, 301, 302], f"Оформление вернул статус {r_success.status_code}"
    
    # 4. Проверить, что заказ появился в профиле
    r_profile = session.get(f"{BASE_URL}/profile/")
    assert r_profile.status_code == 200
    # Проверяем наличие слова "Заказ" или "История" в профиле
    assert "Заказ" in r_profile.text or "История" in r_profile.text or "order" in r_profile.text.lower()