"""Намеренно "ломает" стенд руками — чтобы потренироваться находить и лечить drift.

    python drift.py dashboard    # переименовать дашборд "через UI" (на самом деле через API)
    python drift.py datasource   # поменять URL датасорса
    python drift.py rule         # поменять `for` у правила через provisioning API (как это сделал бы скрипт)
    python drift.py rule-ui      # попытаться отредактировать правило так, как это делает UI (должно НЕ получиться)

После любой из первых трёх команд `make plan` покажет расхождение, а `make apply` вернёт всё как в Git.
"""
import sys

from common import grafana


def dashboard():
    status, data = grafana("GET", "/api/dashboards/uid/host-overview")
    dash = data["dashboard"]
    dash["title"] = dash["title"] + " (EDITED BY HAND)"
    status, data = grafana("POST", "/api/dashboards/db",
                           {"dashboard": dash, "folderUid": data["meta"]["folderUid"], "overwrite": True})
    print("дашборд:", status, data if status != 200 else "переименован")


def datasource():
    status, ds = grafana("GET", "/api/datasources/uid/prometheus-main")
    ds["url"] = "http://prometheus:9999"
    status, data = grafana("PUT", f"/api/datasources/uid/prometheus-main", ds)
    print("датасорс:", status, data.get("message", data) if isinstance(data, dict) else data)


def _rule(title):
    status, rules = grafana("GET", "/api/v1/provisioning/alert-rules")
    return next(r for r in rules if r["title"] == title)


def rule():
    r = _rule("HostHighCpuUsage")
    r["for"] = "42m"
    # Provisioning API — тот самый, которым пользуется и Terraform. Правило с
    # provenance=api через него править МОЖНО (а через UI — нельзя, см. rule-ui).
    # Т.е. от человека с токеном/админским паролем provenance не защищает —
    # он защищает от случайных правок в интерфейсе. Такие правки ловит drift detection.
    status, data = grafana("PUT", f"/api/v1/provisioning/alert-rules/{r['uid']}", r)
    print("правило:", status, "for изменён на 42m" if status == 200 else data)


def rule_ui():
    """Повторяем то, что делает UI при сохранении правила: PUT группы через ruler API."""
    r = _rule("HostHighMemoryUsage")
    status, group = grafana("GET", f"/api/ruler/grafana/api/v1/rules/{r['folderUID']}/{r['ruleGroup']}")
    for rule_ in group["rules"]:
        rule_["grafana_alert"]["title"] = rule_["grafana_alert"]["title"] + "-edited"
    status, data = grafana("POST", f"/api/ruler/grafana/api/v1/rules/{r['folderUID']}", group)
    if status in (400, 403, 409):
        print(f"✅ Grafana ОТКАЗАЛА (HTTP {status}): {data.get('message', data)}")
        print("   Так выглядит защита provenance: через UI правило, созданное Terraform, не поменять.")
    else:
        print(f"⚠ Неожиданно: HTTP {status} {data}. Защита не сработала!")


if __name__ == "__main__":
    actions = {"dashboard": dashboard, "datasource": datasource, "rule": rule, "rule-ui": rule_ui}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        sys.exit(__doc__)
    actions[sys.argv[1]]()
