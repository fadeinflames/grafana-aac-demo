"""Проверка "ресурсы реально появились в Grafana". Запускается после `terraform apply`
(локально — `make smoke`, в CI — шагом после apply).

Ожидаемый состав берётся из репозитория:
  * правила — из alerts/*.yaml,
  * дашборды — из dashboards/*/*.json,
плюс жёстко заданные имена контактных точек и т.п. (см. EXPECTED_* ниже).
Если вы добавили алерт/дашборд в Git и сделали apply — smoke сам проверит, что он есть.

Код возврата: 0 — всё на месте, 1 — чего-то не хватает.
"""
import glob
import json
import os
import re
import sys

from common import grafana

ROOT = os.environ.get("REPO_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
EXPECTED_DATASOURCE_UID = "prometheus-main"
EXPECTED_CONTACT_POINTS = {"team-webhook", "critical-webhook"}
EXPECTED_MUTE_TIMINGS = {"nightly-maintenance"}
EXPECTED_TEMPLATES = {"aac"}

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("✅ " if ok else "❌ ") + name + (f"  — {detail}" if detail and not ok else ""))


def get(path):
    status, data = grafana("GET", path)
    if status != 200:
        print(f"❌ GET {path} -> HTTP {status}: {str(data)[:200]}")
        sys.exit(1)
    return data


def expected_rules():
    """{имя правила: файл} из alerts/*.yaml. YAML не парсим целиком (нужен PyYAML),
    достаточно найти строки "  - name: Имя"."""
    found = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "alerts", "*.y*ml"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\s+-\s+name:\s*['\"]?([^'\"#\s]+)", line)
                if m:
                    found[m.group(1)] = os.path.basename(path)
    return found


def main():
    # --- датасорс ---------------------------------------------------------
    ds = get("/api/datasources")
    uids = {d["uid"]: d for d in ds}
    check(f"датасорс {EXPECTED_DATASOURCE_UID} существует", EXPECTED_DATASOURCE_UID in uids)
    check("датасорсов ровно один (только Prometheus, без логов/трейсов)",
          len(ds) == 1 and ds[0]["type"] == "prometheus", f"найдено: {[d['type'] for d in ds]}")
    status, health = grafana("GET", f"/api/datasources/uid/{EXPECTED_DATASOURCE_UID}/health")
    check("health датасорса = OK (Grafana достучалась до Prometheus)",
          status == 200 and health.get("status") == "OK", str(health))

    # --- папки и дашборды -------------------------------------------------
    folders = {f["title"] for f in get("/api/folders")}
    dash_dirs = {os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(ROOT, "dashboards", "*", "*.json"))}
    for d in sorted(dash_dirs):
        check(f"папка «{d}» существует", d in folders)

    existing = {d["uid"]: d for d in get("/api/search?type=dash-db&limit=5000")}
    for path in sorted(glob.glob(os.path.join(ROOT, "dashboards", "*", "*.json"))):
        with open(path, encoding="utf-8") as f:
            uid = json.load(f)["uid"]
        rel = os.path.relpath(path, ROOT)
        check(f"дашборд {rel} (uid={uid}) существует", uid in existing)

    # --- алерты -----------------------------------------------------------
    rules = {r["title"]: r for r in get("/api/v1/provisioning/alert-rules")}
    for name, file in expected_rules().items():
        check(f"правило {name} (из {file}) существует", name in rules)
        if name in rules:
            check(f"правило {name} защищено от правки в UI (provenance=api)",
                  rules[name].get("provenance") == "api", f"provenance={rules[name].get('provenance')!r}")

    # --- уведомления ------------------------------------------------------
    cps = {c["name"]: c for c in get("/api/v1/provisioning/contact-points")}
    for name in sorted(EXPECTED_CONTACT_POINTS):
        check(f"contact point {name} существует (provenance=api)",
              name in cps and cps[name].get("provenance") == "api")

    policy = get("/api/v1/provisioning/policies")
    check("notification policy: корень ведёт в team-webhook", policy.get("receiver") == "team-webhook")
    check("notification policy: есть маршрут severity=critical -> critical-webhook",
          any(r.get("receiver") == "critical-webhook" and ["severity", "=", "critical"] in (r.get("object_matchers") or [])
              for r in policy.get("routes") or []))
    check("notification policy создана Terraform (provenance=api)", policy.get("provenance") == "api")

    mutes = {m["name"] for m in get("/api/v1/provisioning/mute-timings")}
    for name in sorted(EXPECTED_MUTE_TIMINGS):
        check(f"mute timing {name} существует", name in mutes)

    templates = {t["name"] for t in get("/api/v1/provisioning/templates")}
    for name in sorted(EXPECTED_TEMPLATES):
        check(f"шаблон уведомлений {name} существует", name in templates)

    total, ok = len(results), sum(results)
    print(f"\nИтог: {ok}/{total} проверок пройдено")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
