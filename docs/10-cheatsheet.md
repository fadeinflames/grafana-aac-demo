# 10. Шпаргалка

## Команды: `make` и «то же без make»

Все команды — из корня репозитория. «Окружение» = переменные из `.secrets/terraform.env` (адреса и токены).
Как их загрузить без make:

* Git Bash / Linux / macOS: `set -a; . .secrets/terraform.env; set +a`
* PowerShell: `. .\scripts\load-env.ps1` (если «running scripts is disabled» — один раз в этом окне: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)

| Что сделать | С make | Без make |
|---|---|---|
| Поднять стенд | `make up` | `docker compose up -d --wait` затем `docker compose run --rm bootstrap` затем `docker compose run --rm tools python set_test_metric.py 0` |
| Статус сервисов | `make ps` | `docker compose ps -a` |
| Логи | `make logs` | `docker compose logs -f --tail=50` |
| Остановить (данные остаются) | `make down` | `docker compose down` |
| Сбросить всё | `make reset` | `docker compose down -v --remove-orphans` и удалить `.secrets/terraform.env` |
| Перевыпустить токен | `make bootstrap` | `docker compose run --rm bootstrap` |
| terraform init | `make init` | *(окружение)* `terraform -chdir=terraform/envs/test init` |
| Форматирование `.tf` | `make fmt` | `terraform fmt -recursive terraform` |
| Проверки без Grafana | `make validate` | 1) `terraform fmt -check -recursive terraform`. 2) **С отдельным `TF_DATA_DIR`** (иначе `init -backend=false` сломает ваш backend!): Git Bash — `export TF_DATA_DIR=$PWD/.tf-validate`, PowerShell — `$env:TF_DATA_DIR="$PWD\.tf-validate"`; затем `terraform -chdir=terraform/envs/test init -backend=false` и `… validate`; затем `unset TF_DATA_DIR` / `Remove-Item Env:TF_DATA_DIR`. 3) `docker compose run --rm tools python validate_dashboards.py`. 4) юнит-тесты — строкой ниже |
| Юнит-тесты алертов | `make test-unit` | `terraform -chdir=terraform/modules/alert-rules init -backend=false` затем `terraform -chdir=terraform/modules/alert-rules test` |
| План изменений | `make plan` | *(окружение)* `terraform -chdir=terraform/envs/test plan` |
| Применить | `make apply` (`AUTO=1 make apply` — без вопроса) | *(окружение)* `terraform -chdir=terraform/envs/test apply` |
| Проверить, что всё есть в Grafana | `make smoke` | `docker compose run --rm tools python smoke.py` |
| Вызвать алерт | `make alert-fire` | `docker compose run --rm tools python alert_e2e.py fire` |
| …и critical | `make alert-fire-critical` | `docker compose run --rm tools python alert_e2e.py fire-critical` |
| Снять алерт | `make alert-resolve` | `docker compose run --rm tools python alert_e2e.py resolve` |
| Полный e2e (~1,5 минуты) | `make e2e` | `docker compose run --rm tools python alert_e2e.py cycle` |
| Всё сразу | `make test` | три предыдущих блока подряд |
| Задать метрику вручную | — | `docker compose run --rm tools python set_test_metric.py 100` |
| Учебная «порча» | `make drift-dashboard` / `drift-datasource` / `drift-rule` / `drift-rule-ui` | `docker compose run --rm tools python drift.py dashboard` (и т.д.) |
| Пересчитать lock-файл | `make lock` | `terraform -chdir=terraform/envs/test providers lock -platform=linux_amd64 -platform=linux_arm64 -platform=windows_amd64 -platform=darwin_amd64 -platform=darwin_arm64` |

> В PowerShell `curl` — алиас другой команды; пишите `curl.exe`.

## Адреса

| Что | Адрес |
|---|---|
| Grafana | http://localhost:3000 (admin / admin12345) |
| Prometheus | http://localhost:9090 |
| Webhook-ящик (обычный) | http://localhost:8081/s/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa |
| Webhook-ящик (critical) | http://localhost:8081/s/cccccccc-cccc-4ccc-8ccc-cccccccccccc |
| MinIO консоль | http://localhost:9001 (minioadmin / minioadmin123) |
| Pushgateway | http://localhost:9091 |

## Git-цикл изменения

```bash
git switch main && git pull
git switch -c my-change            # ветка под изменение
# ... правим alerts/*.yaml, dashboards/..., terraform/...
make validate && make plan         # локальные проверки
git add -A && git commit -m "Что и зачем"
git push -u origin my-change       # затем Pull Request
```

## Чек-лист «перед Pull Request»

- [ ] `make plan` **до** изменений показывал `No changes` (иначе в Grafana уже есть drift — разберитесь сначала с ним).
- [ ] Я менял **только файлы в Git**, а не Grafana руками.
- [ ] `make validate` — зелёный (fmt, validate, дашборды, юнит-тесты алертов).
- [ ] `make plan` показывает **ровно те изменения, которые я хотел** (прочитал `+`, `~`, `-` до конца; ни одного неожиданного `destroy`).
- [ ] У нового алерта: понятные `summary`/`description`, правильный `severity`, ссылка `runbook_url`.
- [ ] У нового дашборда: `uid`, датасорс `{"type":"prometheus","uid":"prometheus-main"}`, экспорт **без** галочки «для внешнего использования».
- [ ] В коммите нет секретов (токенов, паролей, `.env`, `.secrets/`, `*.tfstate`).
- [ ] Если удаляю contact point — маршрут на него убран **в предыдущем** PR (иначе 409).
- [ ] В описании PR — что меняется и зачем; я готов к вопросам ревьюера.
- [ ] После merge я нажал Approve в `apply` (или попросил коллегу) и убедился, что `smoke` зелёный.

## Как читать `plan`

| Значок | Значит |
|---|---|
| `+` | будет создано |
| `~` | будет изменено на месте (`было -> стало`) |
| `-` | будет **удалено** — проверяйте особенно внимательно |
| `-/+` | пересоздание (удалить и создать заново) |
| `(known after apply)` | значение станет известно только после создания |
| `Plan: A to add, B to change, C to destroy.` | итог |
| `No changes.` | код и Grafana совпадают |

## Что где лежит

| Хочу … | Файл |
|---|---|
| добавить/изменить алерт | `alerts/*.yaml` |
| добавить/изменить дашборд | `dashboards/<Папка>/<имя>.json` |
| изменить маршрутизацию / contact point / окно тишины | `terraform/envs/test/main.tf` (модуль `notifications`) |
| изменить текст уведомления | `terraform/modules/notifications/templates/aac.tmpl` |
| поменять версию провайдера | `versions.tf` в `envs/test` и модулях, затем `make lock` |
| поменять версии образов стенда | `docker-compose.yml` (и `.env.example` для MinIO), таблица в `README.md` |

## Полезные ссылки

* Провайдер Grafana для Terraform: <https://registry.terraform.io/providers/grafana/grafana/latest/docs>
* Алертинг Grafana: <https://grafana.com/docs/grafana/latest/alerting/>
* Провижининг алертов через Terraform: <https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/terraform-provisioning/>
* PromQL: <https://prometheus.io/docs/prometheus/latest/querying/basics/>
* Основы Terraform: <https://developer.hashicorp.com/terraform/intro>
* Шаблоны уведомлений: <https://grafana.com/docs/grafana/latest/alerting/configure-notifications/template-notifications/>
