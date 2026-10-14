# tests/test_non_functional.py
import requests
import pytest
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:8000"

@pytest.fixture(scope="session")
def session():
    """Создаем сессию для отправки HTTP-запросов"""
    return requests.Session()

def test_nf_security_headers_and_debug_leak(session):
    """TC-NF-002: Заголовки безопасности и отсутствие отладочной информации"""
    r = session.get(f"{BASE_URL}/catalog/")
    headers = r.headers
    
    # 1. Проверка заголовков безопасности, которые ДОЛЖНЫ быть в современном Django
    # X-Content-Type-Options предотвращает MIME-sniffing атаки
    assert headers.get('X-Content-Type-Options') == 'nosniff', \
        "Отсутствует заголовок безопасности X-Content-Type-Options"
    
    # Referrer-Policy контролирует передачу Referer-заголовка
    assert headers.get('Referrer-Policy') == 'same-origin', \
        "Отсутствует или неверен заголовок Referrer-Policy"
    
    # Cross-Origin-Opener-Policy защищает от атак через window.opener
    assert headers.get('Cross-Origin-Opener-Policy') == 'same-origin', \
        "Отсутствует или неверен заголовок Cross-Origin-Opener-Policy"
    
    # 2. Проверка на отсутствие отладочных данных в теле ответа
    response_text = r.text.lower()
    assert 'traceback' not in response_text, \
        "В ответе найдены отладочные данные (traceback) — потенциальная уязвимость"
    assert 'django.core' not in response_text, \
        "Утечка внутренних путей фреймворка в ответе"

def test_nf_xss_and_sqli_resistance(session):
    """TC-NF-003: Устойчивость к XSS и SQL-инъекциям"""
    
    # 1. Проверка XSS (Cross-Site Scripting) через форму поиска
    payload_xss = "<script>alert('XSS_TEST')</script>"
    r_xss = session.get(f"{BASE_URL}/catalog/", params={'q': payload_xss})
    
    assert r_xss.status_code == 200, "Сервер вернул ошибку при обработке ввода"
    
    # Django автоматически экранирует переменные в шаблонах
    # Поэтому в ответе не должно быть сырого тега <script>
    assert "<script>" not in r_xss.text, \
        "Уязвимость XSS: вредоносный скрипт не был экранирован!"
    
    # 2. Проверка SQL-инъекции
    payload_sqli = "' OR 1=1 --"
    r_sqli = session.get(f"{BASE_URL}/catalog/", params={'q': payload_sqli})
    
    assert r_sqli.status_code == 200, "Сервер упал при обработке спецсимволов"
    
    # Проверяем, что ORM не упал с ошибкой базы данных
    error_keywords = ['operationalerror', 'databaseerror', 'syntax error']
    response_lower = r_sqli.text.lower()
    for keyword in error_keywords:
        assert keyword not in response_lower, \
            f"Обнаружена ошибка СУБД в ответе ({keyword}) — возможна уязвимость"
    
    assert 'traceback' not in response_lower, \
        "Обнаружен стектрейс при попытке инъекции"
    
def test_nf_password_storage_via_auth_flow(session):
    """TC-NF-004: Косвенная проверка хеширования паролей через аутентификацию"""
    # 1. Получаем форму регистрации и CSRF-токен
    r_register_form = session.get(f"{BASE_URL}/register/")
    assert r_register_form.status_code == 200
    
    soup = BeautifulSoup(r_register_form.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    assert csrf_token, "CSRF-токен не найден на странице регистрации"
    
    # 2. Регистрируем тестового пользователя с уникальным паролем
    test_email = f"autotest_{hash('nf_password_check')}@test.ru"
    test_password = "SecureP@ssw0rd_2026!"  # Сложный пароль для проверки
    
    r_register = session.post(f"{BASE_URL}/register/", data={
        'csrfmiddlewaretoken': csrf_token['value'],
        'email': test_email,
        'name': 'AutoTest User',
        'password': test_password
    }, allow_redirects=True)
    
    # Регистрация должна пройти успешно (редирект или 200)
    assert r_register.status_code in [200, 301, 302], \
        f"Регистрация не удалась: статус {r_register.status_code}"
    
    # 3. Проверяем, что пароль НЕ отображается в ответе (защита от утечки)
    assert test_password not in r_register.text, \
        "Пароль обнаружен в ответе сервера — критическая уязвимость!"
    
    # 4. Выходим (если система автоматически авторизовала) и пробуем войти
    session.get(f"{BASE_URL}/logout/", allow_redirects=True)
    
    # 5. Вход с ПРАВИЛЬНЫМ паролем должен сработать
    r_login_form = session.get(f"{BASE_URL}/login/")
    soup = BeautifulSoup(r_login_form.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    
    r_login_success = session.post(f"{BASE_URL}/login/", data={
        'csrfmiddlewaretoken': csrf['value'],
        'email': test_email,
        'password': test_password
    }, allow_redirects=True)
    
    # Успешный вход = редирект или 200 с профилем
    assert r_login_success.status_code in [200, 301, 302], \
        "Вход с правильным паролем не сработал — возможно, пароль не сохранён или не захеширован"
    
    # 6. Вход с НЕПРАВИЛЬНЫМ паролем должен быть отклонён
    session2 = requests.Session()  # Новая сессия для чистого входа
    r_login_form2 = session2.get(f"{BASE_URL}/login/")
    soup2 = BeautifulSoup(r_login_form2.text, 'html.parser')
    csrf2 = soup2.find('input', {'name': 'csrfmiddlewaretoken'})
    
    r_login_fail = session2.post(f"{BASE_URL}/login/", data={
        'csrfmiddlewaretoken': csrf2['value'],
        'email': test_email,
        'password': "WrongPassword123"
    }, allow_redirects=True)
    
    # Неудачный вход = редирект назад с ошибкой или 401/403
    # Главное: мы НЕ попали в профиль
    assert "Профиль" not in r_login_fail.text or r_login_fail.status_code in [301, 302], \
        "Вход с неправильным паролем прошёл — критическая ошибка аутентификации!"