"""Общие мелочи для скриптов стенда. Только стандартная библиотека Python —
ничего ставить через pip не нужно.

Какие переменные окружения понимают скрипты (значения по умолчанию подходят
для запуска ИЗНУТРИ docker-сети, то есть через `make ...`):

  GRAFANA_URL       адрес Grafana              (в CI: http://grafana:3000 или свой)
  GRAFANA_AUTH      токен service account       (если не задан — берётся admin:пароль)
  WEBHOOK_URL       адрес приёмника вебхуков
  PUSHGATEWAY_URL   адрес Pushgateway
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://grafana:3000").rstrip("/")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://webhook:8080").rstrip("/")
PUSHGATEWAY_URL = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091").rstrip("/")

# UUID "почтовых ящиков" в приёмнике вебхуков. Должны совпадать с terraform/envs/test/variables.tf
WEBHOOK_DEFAULT_ID = os.environ.get("WEBHOOK_DEFAULT_ID", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WEBHOOK_CRITICAL_ID = os.environ.get("WEBHOOK_CRITICAL_ID", "cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def grafana_auth_header():
    """Bearer-токен (как в CI) или basic admin:пароль (как на локальном стенде)."""
    token = os.environ.get("GRAFANA_AUTH", "")
    if token and ":" not in token:
        return "Bearer " + token
    if not token:
        user = os.environ.get("GRAFANA_ADMIN_USER", "admin")
        password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "admin12345")
        token = f"{user}:{password}"
    return "Basic " + base64.b64encode(token.encode()).decode()


def http(method, url, body=None, headers=None, auth=None, timeout=15, raw=False):
    """Мини-обёртка над urllib. Возвращает (status, данные).
    Данные — разобранный JSON (или текст/bytes, если JSON не получился)."""
    hdrs = dict(headers or {})
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        else:
            data = body if isinstance(body, bytes) else str(body).encode()
    if auth:
        hdrs["Authorization"] = auth
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, payload = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, payload = e.code, e.read()
    except urllib.error.URLError as e:
        raise SystemExit(f"НЕ УДАЛОСЬ подключиться к {url}: {e.reason}")
    if raw:
        return status, payload
    try:
        return status, json.loads(payload)
    except (ValueError, TypeError):
        return status, payload.decode(errors="replace")


def grafana(method, path, body=None, headers=None):
    return http(method, GRAFANA_URL + path, body, headers, auth=grafana_auth_header())


def wait_until(description, check, timeout=120, interval=3):
    """Повторяет check() пока он не вернёт что-то "истинное". Печатает прогресс."""
    deadline = time.time() + timeout
    while True:
        result = check()
        if result:
            return result
        if time.time() > deadline:
            raise SystemExit(f"ТАЙМАУТ ({timeout}с): {description}")
        time.sleep(interval)


def log(msg):
    print(msg, flush=True)


def fail(msg):
    print(f"❌ {msg}", flush=True)
    sys.exit(1)
