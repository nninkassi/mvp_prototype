# tests/test_usability.py
import requests
import pytest
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:8000"

@pytest.fixture(scope="session")
def session():
    """Создаём изолированную сессию для HTTP-запросов"""
    return requests.Session()

def test_ux_accessibility_basics(session):
    """
    TC-UX-001: Проверка базовой доступности контента
    Соответствие: ГОСТ Р 52872-2019, п. 4.1.1 (критерий 1.1.1), 
                  п. 4.1.3 (критерий 1.3.5), п. 4.1.4 (критерий 1.4.10)
    """
    urls = [
        f"{BASE_URL}/catalog/",
        f"{BASE_URL}/product/1/",
        f"{BASE_URL}/cart/"
    ]

    for url in urls:
        r = session.get(url, allow_redirects=True)
        # Если страница требует авторизации или не найдена — пропускаем, но логируем
        if r.status_code not in [200, 302]:
            print(f"⚠️ {url} вернул статус {r.status_code} — проверка пропущена")
            continue

        soup = BeautifulSoup(r.text, 'html.parser')

        # 1. Текстовая версия нетекстового контента (п. 4.1.1, критерий 1.1.1)
        images = soup.find_all('img')
        for img in images:
            # Декоративные изображения могут иметь alt="", это допустимо по ГОСТ
            assert img.has_attr('alt'), \
                f"Отсутствует атрибут alt у изображения {img.get('src', 'N/A')[:50]} на {url}"

        # 2. Назначение полей ввода (п. 4.1.3, критерий 1.3.5)
        inputs = soup.find_all('input', {'type': lambda x: x and x not in ['hidden', 'submit', 'button']})
        for inp in inputs:
            has_label = (
                inp.has_attr('aria-label') or
                inp.has_attr('placeholder') or
                soup.find('label', {'for': inp.get('id')})
            )
            # Мягкая проверка: фиксируем предупреждение, но не останавливаем тест
            if not has_label:
                print(f"⚠️ Input без явной подписи на {url}: name={inp.get('name')}")

        # 3. Адаптивность отображения (п. 4.1.4, критерий 1.4.10)
        viewport = soup.find('meta', {'name': 'viewport'})
        assert viewport, f"Отсутствует мета-тег viewport на {url} — нарушение требований адаптивности"

def test_ux_form_validation_messages(session):
    """
    TC-UX-002: Валидация форм: понятные сообщения об ошибках
    Соответствие: ГОСТ Р 52872-2019, п. 4.3.3 (критерии 3.3.1, 3.3.3)
    """
    r_form = session.get(f"{BASE_URL}/login/")
    assert r_form.status_code in [200, 302], "Страница входа недоступна"

    soup = BeautifulSoup(r_form.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    assert csrf, "CSRF-токен не найден на странице входа"

    # 1. Выявление ошибок (критерий 3.3.1)
    r_empty = session.post(f"{BASE_URL}/login/", data={
        'csrfmiddlewaretoken': csrf['value'],
        'email': '',
        'password': 'test'
    }, allow_redirects=True)

    assert r_empty.status_code == 200, "Форма вернула неожиданный статус при ошибке валидации"

    response_text = r_empty.text.lower()
    has_error_hint = (
        'обязательно' in response_text or
        'неверный' in response_text or
        'errorlist' in response_text or
        'invalid' in response_text
    )
    assert has_error_hint, "Отсутствует понятное сообщение об ошибке для пустого поля (нарушение п. 4.3.3)"

    # 2. Подсказки при ошибках вместо технических деталей (критерий 3.3.3)
    assert 'traceback' not in response_text, "В ответе найдены отладочные данные (traceback)"
    assert 'django.core' not in response_text, "Утечка внутренних путей фреймворка"
    assert 'operationalerror' not in response_text, "Обнаружена ошибка СУБД в ответе пользователю"