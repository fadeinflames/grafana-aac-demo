#!/usr/bin/env python3
"""Проверка JSON-дашбордов в dashboards/ (запускается в CI на каждый PR и командой `make validate`).

Ловит самые частые ошибки джуниора:
  * битый JSON;
  * нет "uid" / "title" или дубликаты uid;
  * остался блок "__inputs" (экспорт "для внешнего использования") или переменные ${DS_...};
  * датасорс указан ИМЕНЕМ (строкой) или чужим uid — а должен быть uid из Terraform.

Работает на любом Python 3.8+ без установки пакетов. Запуск:
    make validate                                   (внутри контейнера, Python на хосте не нужен)
    python3 scripts/validate_dashboards.py          (если Python есть — напрямую; в CI так)
"""
import glob
import json
import os
import sys

# REPO_ROOT задаётся в контейнере `tools` (там репозиторий смонтирован в /repo)
ROOT = os.environ.get("REPO_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# uid датасорсов, на которые можно ссылаться (см. terraform/modules/datasource-prometheus)
ALLOWED_DS_UIDS = {"prometheus-main", "grafana", "-- Grafana --", "-- Mixed --", "-- Dashboard --"}
# встроенные "датасорсы" Grafana (есть в любом дашборде, экспортированном из UI: аннотация "Annotations & Alerts")
BUILTIN_DS_NAMES = {"-- Grafana --", "-- Mixed --", "-- Dashboard --"}

errors = []


def err(path, msg):
    errors.append(f"{os.path.relpath(path, ROOT)}: {msg}")


def walk(path, node, trail=""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else key
            if key == "datasource":
                check_datasource(path, here, value)
            walk(path, value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk(path, item, f"{trail}[{i}]")


def check_datasource(path, where, value):
    if value is None or (isinstance(value, str) and value in BUILTIN_DS_NAMES):
        return
    if isinstance(value, str):
        err(path, f'{where}: датасорс указан строкой "{value}". Нужен объект {{"type": "prometheus", "uid": "prometheus-main"}}')
    elif isinstance(value, dict):
        uid = value.get("uid")
        if uid is None:
            err(path, f"{where}: у датасорса нет uid")
        elif "${" in str(uid) or str(uid).startswith("$"):
            err(path, f'{where}: uid датасорса — переменная "{uid}". Замените на "prometheus-main"')
        elif uid not in ALLOWED_DS_UIDS:
            err(path, f'{where}: неизвестный uid датасорса "{uid}". Допустимо: {sorted(ALLOWED_DS_UIDS)}')


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "dashboards", "*", "*.json")))
    stray = [p for p in glob.glob(os.path.join(ROOT, "dashboards", "**", "*.json"), recursive=True) if p not in files]
    for p in stray:
        err(p, "JSON лежит не в подкаталоге dashboards/<Папка>/ — Terraform его не увидит")
    if not files:
        print("Нет дашбордов в dashboards/*/*.json")
    uids = {}
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                dash = json.load(f)
        except ValueError as e:
            err(path, f"невалидный JSON: {e}")
            continue
        if not isinstance(dash, dict):
            err(path, "ожидался JSON-объект на верхнем уровне")
            continue
        uid = dash.get("uid")
        if not uid or not isinstance(uid, str):
            err(path, 'нет строкового поля "uid" на верхнем уровне')
        elif len(uid) > 40:
            err(path, f'"uid" длиннее 40 символов ({len(uid)})')
        elif uid in uids:
            err(path, f'"uid" "{uid}" уже используется в {uids[uid]}')
        else:
            uids[uid] = os.path.relpath(path, ROOT)
        if not dash.get("title"):
            err(path, 'нет поля "title"')
        if "__inputs" in dash or "__requires" in dash:
            err(path, 'есть "__inputs"/"__requires" — это экспорт «для внешнего использования». Экспортируйте без этой галочки')
        walk(path, dash)

    if errors:
        print("❌ Найдены проблемы в дашбордах:\n")
        for e in errors:
            print("  - " + e)
        sys.exit(1)
    print(f"✅ Дашборды в порядке: проверено файлов — {len(files)}")


if __name__ == "__main__":
    main()
