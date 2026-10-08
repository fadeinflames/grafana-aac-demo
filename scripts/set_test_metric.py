"""Задаёт значение управляемой тестовой метрики demo_test_value.

    python set_test_metric.py 100    # "авария": сработает DemoControlledTestAlert (порог 50)
    python set_test_metric.py 200    # сработает ещё и DemoControlledCriticalAlert (порог 150)
    python set_test_metric.py 0      # "всё хорошо"

Как это работает: скрипт кладёт значение в Pushgateway, Prometheus забирает его
раз в 15 секунд, а Grafana видит его как обычную метрику.
"""
import sys

from common import PUSHGATEWAY_URL, http, log


def push(value):
    url = f"{PUSHGATEWAY_URL}/metrics/job/demo-generator/scenario/default"
    body = (f"# TYPE demo_test_value gauge\n"
            f"# HELP demo_test_value Управляемая тестовая метрика стенда\n"
            f"demo_test_value {value}\n")
    status, data = http("PUT", url, body, headers={"Content-Type": "text/plain"}, raw=True)
    if status not in (200, 202):
        sys.exit(f"❌ Pushgateway вернул HTTP {status}: {data[:200]!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        v = float(sys.argv[1])
    except ValueError:
        sys.exit(f"Значение должно быть числом, а не '{sys.argv[1]}'")
    push(v)
    log(f"✅ demo_test_value = {v:g} (Prometheus заберёт значение в течение 15 секунд)")
