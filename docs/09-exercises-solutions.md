# 09 (решения). Упражнения: ответы

> Сначала попробуйте сами: [09-exercises.md](09-exercises.md). Все решения ниже выполнены на живом стенде; приведённые выводы — реальные.

После каждого упражнения возвращайте стенд к исходному виду: `git checkout . && make apply` (если вы меняли `.tf`/YAML) и `make plan` → `No changes`.

---

## Решение 1. Поменять порог

В `alerts/host-resources.yaml` у `HostHighCpuUsage` замените `threshold: 85` на `threshold: 80`.

`make plan` показывает ровно одно изменение:
```
  # module.alert_rules.grafana_rule_group.this["host-resources.yaml"] will be updated in-place
      ~ rule {
            name = "HostHighCpuUsage"
          ~ data {
              ~ model = jsonencode(
                  ~ {
                      ~ conditions = [
                          ~ {
                              ~ evaluator = {
                                  ~ params = [
                                      ~ 85 -> 80,
Plan: 0 to add, 1 to change, 0 to destroy.
```
`make apply` → `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.` Повторный `make plan` → `No changes`.

**Почему так:** порог хранится внутри JSON-модели шага C правила (Threshold) — поэтому в плане он виден как `85 -> 80` внутри `model`.

---

## Решение 2. Добавить свой алерт

Добавьте в конец `rules:` в `alerts/host-resources.yaml` (с отступом как у соседних правил):

```yaml
  - name: HostHighLoadAverage
    expr: 'node_load1'
    operator: gt
    threshold: 0.0001          # специально крошечный порог, чтобы сразу увидеть срабатывание
    for: 30s
    severity: info
    summary: "Load average на {{ $labels.instance }} = {{ $values.B.Value }}"
    labels:
      team: platform
```
`make plan` → `Plan: 0 to add, 1 to change, 0 to destroy` (обновляется группа `host-resources`). `make apply`, `make smoke` → две строки про `HostHighLoadAverage`, `Итог: 26/26`.

Срабатывание (проверено): состояния `inactive → pending → firing` — около 70 секунд (интервал группы 1 мин + `for: 30s`), в ящик `aaaa…` пришло `[FIRING:1] HostHighLoadAverage Alerts (node-exporter:9100 node-exporter info platform)`. Именно в `aaaa…`, потому что у маршрута `severity=info` контактная точка — `team-webhook`.

Уборка: верните порог `threshold: 4` либо удалите правило и сделайте `make apply`.

> Обратите внимание: `description` и `runbook_url` — необязательные поля, у этого правила их нет, и это нормально.

---

## Решение 3. Сломать и починить

Три поломки и что говорит `make plan` (реальный вывод, самое важное — **последние строки**):

**1. `severity: urgent`**
```
Error: Resource precondition failed
  on ../../modules/alert-rules/main.tf line 87, in resource "terraform_data" "validate":
...
Файл demo-controlled.yaml: поле severity должно быть одним из: critical,
warning, info. Проверьте правила: DemoControlledTestAlert.
```
Причина: в модуле допустимы только три значения severity — по ним идёт маршрутизация. Исправление: `severity: warning`.

**2. `threshold: "50%"`**
```
Файл demo-controlled.yaml: threshold должен быть числом (например, 85), без
кавычек и знака %. Проверьте правила: DemoControlledTestAlert.
```
Причина: порог сравнивается с числом из запроса, `%` туда не относится. Исправление: `threshold: 50`.

**3. `for: 20 sec`**
```
Файл demo-controlled.yaml: поля `for` и `interval` задаются как число с единицей: 30s, 5m, 1h. Например: for: 5m.
```
Исправление: `for: 20s`.

**Почему поймал именно Terraform:** в модуле `alert-rules` есть ресурс `terraform_data.validate` с блоками `precondition` — проверки до обращения к Grafana. Для этих же случаев есть юнит-тесты (`terraform/modules/alert-rules/tests/repo-alerts.tftest.hcl`, фикстуры в `tests/fixtures/`): каждая «плохая» папка должна отклоняться. `make test-unit` → `Success! 7 passed, 0 failed.` (Плюс `yamllint` ловит ошибки отступов ещё раньше, в CI.)

Итог: `git checkout alerts/demo-controlled.yaml`, `make plan` → `No changes`.

---

## Решение 4. Drift

```bash
make drift-dashboard      # дашборд: 200 переименован
make drift-datasource     # датасорс: 200 Datasource updated
make drift-rule           # правило: 200 for изменён на 42m
make plan
```
План:
```
  # module.alert_rules.grafana_rule_group.this["host-resources.yaml"] will be updated in-place
      ~ rule {
          ~ for                             = "42m0s" -> "5m"
  # module.dashboards.grafana_dashboard.this["Infrastructure/host-overview.json"] will be updated in-place
              ~ title         = "Host Overview (node-exporter) (EDITED BY HAND)" -> "Host Overview (node-exporter)"
  # module.prometheus.grafana_data_source.prometheus will be updated in-place
      ~ url                 = "http://prometheus:9999" -> "http://prometheus:9090"
Plan: 0 to add, 3 to change, 0 to destroy.
```
Читайте `было -> стало`: слева реальное значение в Grafana, справа — в Git.

Код возврата: `terraform -chdir=terraform/envs/test plan -detailed-exitcode; echo $?` → `2` (drift). После `make apply` (`Resources: 0 added, 3 changed, 0 destroyed`) → `0`.

**Бонус (почему `Error`):** пока в датасорсе неверный URL, Grafana не может выполнить запрос `A` к Prometheus, правило не может вычислиться и (при `exec_err_state: Error`) переходит в состояние `Error`. В логе: `failed to execute query [A]: Post "http://prometheus:9999/api/v1/query": ... connection refused`.

---

## Решение 5. Mute timing `weekends`

В `terraform/envs/test/main.tf`, в модуле `notifications`:

```hcl
  routes = [
    { severity = "critical", contact_point = "critical-webhook" },
    { severity = "info", contact_point = "team-webhook", mute_timings = ["nightly-maintenance", "weekends"] },
  ]

  mute_timings = {
    "nightly-maintenance" = { start_time = "01:00", end_time = "03:00", location = "UTC" }
    "weekends"            = { weekdays = ["saturday", "sunday"] }
  }
```
(После правки выполните `make fmt` — выровняет `=`.)

`make plan`:
```
  # module.notifications.grafana_mute_timing.this["weekends"] will be created
  # module.notifications.grafana_notification_policy.this will be updated in-place
Plan: 1 to add, 1 to change, 0 to destroy.
```
После `apply` в API: у маршрута `severity=info` `mute_time_intervals: ["nightly-maintenance","weekends"]` (проверено).

**Ответ на вопрос.** Если привязать `weekends` к маршруту `warning`, то в субботу/воскресенье предупреждения будут подавляться, и `make e2e` не дождётся уведомления для `DemoControlledTestAlert` (severity=warning). Алерт при этом честно станет Firing, но уведомление не уйдёт: это и есть «окно тишины». Для тестовых прогонов ориентируйтесь на дни недели.

**Почему не меняли `nightly-maintenance`:** окно `01:00–03:00 UTC` не пересекается с рабочими проверками; важно, что при добавлении второго окна первое **не пропало**: список `mute_timings` у маршрута перечисляет **все** окна.

---

## Решение 6. Новый маршрут для critical

В `terraform/envs/test/main.tf`:

```hcl
  contact_points = {
    "team-webhook"     = { url = "${var.webhook_base_url}/${var.webhook_default_id}" }
    "critical-webhook" = { url = "${var.webhook_base_url}/${var.webhook_critical_id}" }
    "oncall-webhook"   = { url = "${var.webhook_base_url}/dddddddd-dddd-4ddd-8ddd-dddddddddddd" }
  }

  routes = [
    { severity = "critical", contact_point = "oncall-webhook" },
    ...
```
`make plan` → `Plan: 1 to add, 1 to change, 0 to destroy`. После `make apply` и `make alert-fire-critical`:

* в ящике `dddd…` (http://localhost:8081/s/dddddddd-dddd-4ddd-8ddd-dddddddddddd) появилось `[FIRING:1] DemoControlledCriticalAlert Alerts (critical demo)` — проверено;
* `e2e`-скрипт в конце выдал `❌ За 240с в приёмнике не появилось уведомление DemoControlledCriticalAlert=firing` — ожидаемо: он проверяет штатный ящик `cccc…`, а мы его намеренно обошли.

**Откат — обязательно в два шага** (проверено):

1. Верните маршрут на прежний (`contact_point = "critical-webhook"`), **оставив** `oncall-webhook` в `contact_points` → PR/merge/`apply`: `Resources: 0 added, 1 changed`.
2. Удалите `oncall-webhook` из `contact_points` → `apply`: `Resources: 0 added, 0 changed, 1 destroyed`.

Если сделать оба изменения сразу, получите:
```
Error: [DELETE /v1/provisioning/contact-points/{UID}][409] deleteContactpointsConflict
{"message":"Contact point is currently referenced by a notification policy.", ...}
```
Причина: Terraform считает, что политика зависит от **всех** контактных точек сразу, поэтому сначала удаляет лишнюю точку, а политику (где она ещё указана) обновляет потом. Grafana не позволяет удалить точку, на которую ссылается политика. Выход — два шага.

В итоге: `git diff` пуст, `make plan` → `No changes`.

---

## Решение 7. Дашборд из UI

Пошагово — [05-tutorial-add-dashboard.md](05-tutorial-add-dashboard.md). Проверено так: дашборд создан (через API, как это делает UI), экспортирован тем же JSON, положен в `dashboards/Demo/my-test.json` с `"uid": "my-test"`:

* `make validate` → `✅ Дашборды в порядке` (если оставить `id`, `version` как в экспорте — тоже ок);
* `make plan` → `Plan: 1 to add`; `apply` → `1 added`; повторный `plan` → `No changes`;
* удаление файла и `apply` → `1 destroyed`.

Сломанный экспорт (`__inputs`, имя датасорса строкой, `${DS_PROMETHEUS}`, чужой uid) `make validate` отклоняет с понятными сообщениями — они приведены в [05](05-tutorial-add-dashboard.md).

Типичная ошибка: оставили тот же `uid`, что у существующего дашборда (например, `host-overview`). Validate: `"uid" "host-overview" уже используется в …` — выберите уникальный.

---

## Решение 8. Уронить сервис

```bash
docker compose stop node-exporter
```
Что вы увидите (реальная хронология — ниже, в «Результатах прогона»):

* Prometheus перестаёт получать метрики с node-exporter; метрика `up{job="node-exporter"}` становится `0`;
* правило `TargetDown` на очередной проверке (раз в минуту) видит `up < 1` → алерт для `job=node-exporter` уходит в `Pending`;
* через `for: 2m` → `Firing`, и в ящик critical (`cccc…`) приходит уведомление `[FIRING:1] TargetDown …` — severity `critical` идёт в `critical-webhook`;
* `docker compose start node-exporter` → `up` снова 1 → алерт `Normal` → в ящик приходит `resolved`.

**Почему не сразу:** `interval: 1m` (проверка раз в минуту) + `for: 2m` (условие должно продержаться две минуты) + до 15 с на скрейп. Итого 2–4 минуты.

**Почему не сработали `HostHigh…`:** метрик `node_*` больше нет, запрос возвращает пустой результат → `NoData`. Для наших правил `no_data_state: OK` (значение по умолчанию модуля) — «нет данных» считается нормой, алерта нет. Это осознанный выбор для стенда; отсутствие данных у хоста ловит как раз алерт `TargetDown`. Если вам нужно оповещение именно о пустом результате — в YAML правила пропишите `no_data_state: NoData` (Grafana тогда создаст служебный алерт `DatasourceNoData`).

### Результаты прогона (реальная хронология)

Время от остановки `node-exporter`:

| Время | Событие |
|---|---|
| 0 с | `docker compose stop node-exporter`; `TargetDown`: `inactive` (Normal) |
| 20 с | `TargetDown` → `Pending` (для `job=node-exporter`) |
| 141 с | `TargetDown` → `Firing`; в ящик critical (`cccc…`) сразу пришло уведомление `firing` |
| 151 с | `docker compose start node-exporter` |
| 201 с | `TargetDown` → `Normal`; в ящик пришло уведомление `resolved` |

Итого срабатывание заняло **≈ 2,5 минуты** (проверка раз в минуту + `for: 2m`; точная цифра зависит от того, в какой момент минуты вы остановили сервис), восстановление — около минуты. Остальные три цели (`grafana`, `prometheus`, `test-generator`) всё это время оставались `Normal`: алерт создаётся **по одному на цель** (по метке `job`/`instance`).
