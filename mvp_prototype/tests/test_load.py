# tests/test_load.py
import requests
import pytest
import time
import statistics
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8000"

TEST_BUYER_EMAIL = "buyer2@mail.ru"
TEST_BUYER_PASSWORD = "qwerty"

@pytest.fixture(scope="session")
def session():
    """Создаём сессию для всех тестов в этом файле"""
    return requests.Session()

def login_buyer(session):
    """Авторизация тестового покупателя для доступа к защищённым маршрутам"""
    # 1. Получаем страницу входа и CSRF-токен
    r = session.get(f"{BASE_URL}/login/")
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    assert csrf, "CSRF-токен не найден на странице входа"

    # 2. Отправляем форму входа
    r = session.post(f"{BASE_URL}/login/", data={
        'csrfmiddlewaretoken': csrf['value'],
        'email': TEST_BUYER_EMAIL,
        'password': TEST_BUYER_PASSWORD
    }, allow_redirects=True)
    
    assert r.status_code in [200, 301, 302], \
        f"Вход не выполнен. Статус: {r.status_code}. Проверь email/пароль в константах."

def get_existing_product_id(session):
    """Динамически находит ID любого существующего товара в каталоге"""
    r = session.get(f"{BASE_URL}/catalog/")
    assert r.status_code in [200, 302], "Каталог недоступен"
    
    # Ищем ссылку вида /product/123/ или /item/456/ в HTML
    # Регулярное выражение ищет цифры после /product/ или /item/
    match = re.search(r'/(?:product|item)/(\d+)/', r.text)
    if match:
        return match.group(1)
    
    # Если не нашли, пробуем найти кнопку "В корзину" с ID
    match = re.search(r'/cart/add/(\d+)/', r.text)
    if match:
        return match.group(1)
    
    # Если совсем ничего не нашли — возвращаем 1 (на удачу)
    return "1"

def test_load_baseline_response_time(session):
    """TC-LOAD-001: Базовый замер времени отклика (включая динамический товар)"""
    # 1. Авторизуемся, чтобы /cart/ стал доступен
    login_buyer(session)

    # 2. Находим реальный существующий товар
    product_id = get_existing_product_id(session)
    product_url = f"{BASE_URL}/product/{product_id}/"

    urls = [
        f"{BASE_URL}/catalog/",
        product_url,  # Динамический URL вместо хардкода
        f"{BASE_URL}/cart/"
    ]
    
    results = {}
    for url in urls:
        r = session.get(url, allow_redirects=True)
        # 200 = OK, 302 = редирект (допустимо для Django)
        assert r.status_code in [200, 302], f"{url} вернул статус {r.status_code}"
        
        elapsed = r.elapsed.total_seconds()
        results[url] = elapsed
        # Допускаем до 1.0 сек для Dev-сервера
        assert elapsed < 1.0, f"{url} отвечает дольше 1.0 сек ({elapsed:.3f}с)"

def test_load_sequential_50_requests(session):
    """TC-LOAD-002: Последовательная нагрузка (50 запросов)"""
    login_buyer(session)
    
    # Тестируем корзину под нагрузкой
    url = f"{BASE_URL}/cart/"
    times = []
    errors = 0
    
    for _ in range(50):
        try:
            r = session.get(url, allow_redirects=True)
            if r.status_code in [200, 302]:
                times.append(r.elapsed.total_seconds())
            else:
                errors += 1
        except requests.RequestException:
            errors += 1
    
    assert errors == 0, f"Зафиксировано {errors} ошибок при нагрузке"
    assert len(times) == 50, "Не все запросы были обработаны"
    
    avg_time = statistics.mean(times)
    max_time = max(times)
    
    print(f"\n📊 Нагрузка 50 запросов на /cart/: avg={avg_time:.3f}с, max={max_time:.3f}с")
    assert avg_time < 1.0, f"Среднее время отклика превышено: {avg_time:.3f}с"

def test_load_concurrent_5_users():
    """TC-LOAD-003: Эмуляция 5 параллельных пользователей"""
    url = f"{BASE_URL}/catalog/"
    n_threads = 5
    results = []
    
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        # Используем простую лямбду для запроса
        futures = [
            executor.submit(lambda u: (requests.get(u, allow_redirects=True, timeout=10).status_code, time.time()), url) 
            for _ in range(n_threads)
        ]
        for future in as_completed(futures):
            status, _ = future.result()
            results.append(status)
    
    for status in results:
        assert status in [200, 302], f"Запрос вернул статус {status}"

def test_load_production_capacity_estimate():
    """TC-LOAD-004: Расчёт теоретической пропускной способности"""
    r = requests.get(f"{BASE_URL}/catalog/", timeout=10, allow_redirects=True)
    assert r.status_code in [200, 302], f"Каталог вернул статус {r.status_code}"
    
    avg_dev_time = r.elapsed.total_seconds()
    rps_dev = 1 / avg_dev_time if avg_dev_time > 0 else 0
    n_workers = 4
    k_optimization = 2.5
    
    rps_prod = rps_dev * n_workers * k_optimization
    
    print(f"\n🚀 Оценка производительности:")
    print(f"   Dev server: {rps_dev:.1f} RPS (время отклика: {avg_dev_time*1000:.0f} мс)")
    print(f"   Production (Gunicorn ×4 + opt): ~{rps_prod:.0f} RPS")
    
    assert rps_prod >= 10, "Оценка пропускной способности слишком низкая для продакшена"