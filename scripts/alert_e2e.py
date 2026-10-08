"""Сквозная проверка алертинга: метрика -> алерт -> уведомление в приёмнике вебхуков.

    python alert_e2e.py fire       # поднять метрику до 100 и дождаться Firing + уведомления
    python alert_e2e.py resolve    # опустить метрику до 0 и дождаться Normal + "resolved"
    python alert_e2e.py cycle      # полный автотест (его запускает `make test`)

Что значит "дождаться": скрипт каждые 3 секунды спрашивает у Grafana состояние
правила (Normal -> Pending -> Firing) и у приёмника вебхуков — не пришло ли новое
уведомление. Всё, что он видит, печатается с отметкой времени.
"""
import base64
import json
import sys
import time

from common import (WEBHOOK_CRITICAL_ID, WEBHOOK_DEFAULT_ID, WEBHOOK_URL, fail,
                    grafana, http, log)
from set_test_metric import push

WARN_RULE = "DemoControlledTestAlert"
CRIT_RULE = "DemoControlledCriticalAlert"
TIMEOUT = 240
POLL = 3


# ------------------------------------------------------------------ Grafana
def rule_state(name):
    """Состояние правила: 'inactive' (Normal), 'pending' или 'firing'. None — правила нет."""
    status, data = grafana("GET", "/api/prometheus/grafana/api/v1/rules")
    if status != 200:
        fail(f"Не удалось получить состояние правил: HTTP {status}: {data}")
    for group in data["data"]["groups"]:
        for rule in group["rules"]:
            if rule["name"] == name:
                return rule["state"]
    return None


# ------------------------------------------------------------- webhook box
def box_requests(box_id):
    status, data = http("GET", f"{WEBHOOK_URL}/api/session/{box_id}/requests")
    if status == 404:  # ящик ещё ни разу не использовался
        return []
    if status != 200:
        fail(f"Приёмник вебхуков вернул HTTP {status}: {data}")
    return data


def parse_notification(req):
    try:
        return json.loads(base64.b64decode(req["request_payload_base64"]))
    except (ValueError, KeyError):
        return None


def wait_for_notification(box_id, seen, alertname, status, t0):
    """Ждёт НОВОЕ уведомление (которого нет в `seen`) о `alertname` со статусом `status`."""
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        for req in box_requests(box_id):
            if req["uuid"] in seen:
                continue
            body = parse_notification(req)
            if not body:
                continue
            for alert in body.get("alerts", []):
                if alert["labels"].get("alertname") == alertname and alert["status"] == status:
                    seen.add(req["uuid"])
                    log(f"[{time.time()-t0:5.0f}s] 📨 вебхук ({box_id[:4]}…): {alertname} {status}")
                    return body
        time.sleep(POLL)
    fail(f"За {TIMEOUT}с в приёмнике не появилось уведомление {alertname}={status}")


def wait_for_state(name, wanted, t0):
    last = None
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        state = rule_state(name)
        if state != last:
            log(f"[{time.time()-t0:5.0f}s] 🔔 {name}: {last or '—'} → {state}")
            last = state
        if state in wanted:
            return
        time.sleep(POLL)
    fail(f"За {TIMEOUT}с правило {name} не перешло в {wanted} (сейчас: {last})")


def snapshot():
    return {b: {r["uuid"] for r in box_requests(b)} for b in (WEBHOOK_DEFAULT_ID, WEBHOOK_CRITICAL_ID)}


def check(cond, ok_msg, bad_msg):
    if not cond:
        fail(bad_msg)
    log("   ✅ " + ok_msg)


# ------------------------------------------------------------------ сценарии
def do_fire(value=100, expect_critical=False):
    t0 = time.time()
    seen = snapshot()
    log(f"▶ Поднимаем demo_test_value до {value}")
    push(value)
    wait_for_state(WARN_RULE, {"firing"}, t0)
    body = wait_for_notification(WEBHOOK_DEFAULT_ID, seen[WEBHOOK_DEFAULT_ID], WARN_RULE, "firing", t0)
    check("[FIRING]" in body.get("message", ""),
          "текст уведомления собран из нашего шаблона (aac.message)",
          f"в уведомлении нет текста шаблона: {body.get('message')!r}")
    alert = next(a for a in body["alerts"] if a["labels"]["alertname"] == WARN_RULE)
    check(alert["labels"].get("severity") == "warning" and alert["annotations"].get("summary"),
          "метка severity=warning и аннотация summary на месте",
          f"неожиданные метки/аннотации: {alert['labels']} {alert['annotations']}")
    if expect_critical:
        wait_for_state(CRIT_RULE, {"firing"}, t0)
        wait_for_notification(WEBHOOK_CRITICAL_ID, seen[WEBHOOK_CRITICAL_ID], CRIT_RULE, "firing", t0)
        check(True, "critical-алерт ушёл в ОТДЕЛЬНЫЙ ящик (маршрутизация по severity работает)", "")
        # и наоборот: warning-алерт не должен попасть в critical-ящик
        leaked = [r for r in box_requests(WEBHOOK_CRITICAL_ID) if r["uuid"] not in seen[WEBHOOK_CRITICAL_ID]
                  and WARN_RULE in json.dumps(parse_notification(r) or {})]
        check(not leaked, "warning-алерт НЕ попал в critical-ящик", "warning-алерт попал в critical-ящик!")
    log(f"✔ Готово за {time.time()-t0:.0f}с. Смотрите приёмник: http://localhost:8081/s/{WEBHOOK_DEFAULT_ID}")


def do_resolve(expect_critical=False):
    t0 = time.time()
    seen = snapshot()
    log("▶ Опускаем demo_test_value до 0")
    push(0)
    wait_for_state(WARN_RULE, {"inactive"}, t0)
    wait_for_notification(WEBHOOK_DEFAULT_ID, seen[WEBHOOK_DEFAULT_ID], WARN_RULE, "resolved", t0)
    if expect_critical:
        wait_for_state(CRIT_RULE, {"inactive"}, t0)
        wait_for_notification(WEBHOOK_CRITICAL_ID, seen[WEBHOOK_CRITICAL_ID], CRIT_RULE, "resolved", t0)
    log(f"✔ Готово за {time.time()-t0:.0f}с")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fire":
        do_fire()
    elif cmd == "fire-critical":
        do_fire(200, expect_critical=True)
    elif cmd == "resolve":
        do_resolve()
    elif cmd == "cycle":
        log("=== 1/3 Приводим стенд в исходное состояние (метрика = 0)")
        push(0)
        wait_for_state(WARN_RULE, {"inactive"}, time.time())
        log("=== 2/3 Срабатывание (warning + critical) и маршрутизация")
        do_fire(200, expect_critical=True)
        log("=== 3/3 Восстановление")
        do_resolve(expect_critical=True)
        log("✅ E2E: алерты срабатывают, доставляются по нужным маршрутам и восстанавливаются")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
