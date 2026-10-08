# 06. Настройка CI (GitHub Actions)

> ⚠️ Раздел написан без доступа к GitHub: workflow-файлы проверены `actionlint` и по шагам вручную (см. [00-overview](00-overview.md#что-проверено-на-самом-деле-и-что-нет)), но **на GitHub не запускались**. Первый запуск у вас — это часть проверки; в случае проблем смотрите раздел «Что смотреть в упавшем workflow».

## Три workflow'а

| Файл | Когда запускается | Что делает |
|---|---|---|
| `.github/workflows/pr-checks.yml` | Pull Request в `main` | `static-checks` (GitHub-hosted раннер, без доступа к Grafana): fmt, validate, tflint, yamllint, валидатор дашбордов, `terraform test`. Затем `plan` (раннер с доступом к стенду): `terraform plan` и **комментарий в PR**. |
| `.github/workflows/apply.yml` | push в `main` (после merge) или вручную | `Plan` → ручное подтверждение (Environment `test-stand`) → `terraform apply` → `scripts/smoke.py`. |
| `.github/workflows/drift.yml` | раз в 6 часов и вручную | `terraform plan -detailed-exitcode`; при расхождении job красный. |

Общие правила для всех: минимальные `permissions` (по умолчанию `contents: read`, право писать в PR — только у job `plan`), concurrency-группа `terraform-test-stand` (plan/apply/drift идут **по одному**, новые не отменяют текущий apply), версии экшенов закреплены по SHA коммита.

## Как CI достучится до стенда

Проблема: Grafana живёт на `localhost` вашего компьютера, а **GitHub-hosted раннеры работают в облаке GitHub и до вашего localhost не дотянутся**. Три способа решить:

### Вариант 1. Self-hosted runner в docker-сети стенда (реализован, рекомендуется)

Раннер — контейнер `github-runner` в том же `docker-compose.yml` (профиль `ci`). Он находится в одной сети с Grafana и MinIO и обращается к ним по именам `http://grafana:3000`, `http://minio:9000`. Наружу ничего не открывается — раннер сам ходит **исходящими** запросами на GitHub.

| Плюсы | Минусы |
|---|---|
| Ничего не надо открывать в интернет | Компьютер с раннером должен быть включён, иначе job'ы висят в очереди |
| Работает с любым стендом, включая внутреннюю сеть компании | Раннер выполняет код из PR — **опасно для публичных репозиториев** (форки) |
| Бесплатно, нет лимитов минут | Нужно обновлять образ раннера (старые версии GitHub перестаёт принимать) |
| Максимально похоже на «боевую» схему (раннер внутри периметра) | Одна точка отказа; раннер надо настраивать и мониторить |

### Вариант 2. GitHub-hosted раннер + туннель к стенду (не реализован)

Стенд публикуется наружу через туннель (Cloudflare Tunnel, ngrok, Tailscale), и hosted-раннеры ходят в Grafana и MinIO по публичным адресам (например, `https://grafana-xxxx.trycloudflare.com`). Задаётся переменной репозитория `GRAFANA_URL` и `AWS_ENDPOINT_URL_S3`, а `STAND_RUNNER_LABELS` = `["ubuntu-24.04"]`.

| Плюсы | Минусы |
|---|---|
| Не нужен свой раннер | Вы **открываете свой стенд (и MinIO со state!) в интернет**; токены Terraform проходят через чужую инфраструктуру |
| Подходит публичным репозиториям (код из форков не исполняется у вас) | Нужны два туннеля (Grafana и MinIO) или другой remote backend; адреса бесплатных туннелей меняются при перезапуске |
| Быстрая проверка идеи | Компьютер и туннель всё равно должны быть включены; нестабильно |

Tailscale-вариант (раннер подключается к вашей приватной сети через `tailscale/github-action`) безопаснее обычного туннеля, но требует настройки ACL и ключей.

### Вариант 3. Grafana Cloud Free как целевой стенд (не реализован)

Вместо локальной Grafana Terraform применяется к бесплатному стеку Grafana Cloud (<https://grafana.com/products/cloud/>). Hosted-раннеры достают его без туннелей.

| Плюсы | Минусы |
|---|---|
| Доступ из любого раннера, ничего не надо открывать | Это **другая** Grafana (Cloud, а не OSS): отличаются токены, часть настроек и ограничения; результаты не всегда переносятся 1:1 |
| Ближе всего к реальной среде, если в проде тоже Cloud | Свой Prometheus с localhost Cloud не увидит: нужны данные в самом Cloud (remote_write) либо публичный Prometheus |
| Не нужно ничего держать включённым | Вебхуки уходят в интернет: приёмнику нужен публичный адрес (внешний сервис — данные алертов уходят наружу) |
| | Нужен другой remote state (S3/GCS/Terraform Cloud): MinIO с localhost недоступен |
| | Лимиты бесплатного плана (метрики, хранение, количество SA) |

Реализуется заменой `GRAFANA_URL` на адрес стека, токена — на токен SA Cloud-стека, датасорса и backend — на подходящие. Эти изменения в репозитории **не сделаны и не проверены**.

**Рекомендация для ручной проверки: вариант 1.** Остальные имеет смысл рассматривать, если нельзя держать раннер.

## Шаг 1. Репозиторий на GitHub

1. Создайте **приватный** репозиторий на GitHub и отправьте туда код:
   ```bash
   git remote add origin https://github.com/OWNER/REPO.git
   git push -u origin main
   ```
2. В **Settings → Actions → General**: *Allow all actions and reusable workflows* (или разрешите конкретные), **Workflow permissions** → *Read repository contents permissions*.

## Шаг 2. Self-hosted runner

1. GitHub → репозиторий → **Settings → Actions → Runners → New self-hosted runner**. Выберите *Linux / x64*. На странице в блоке *Configure* найдите команду вида:
   ```
   ./config.sh --url https://github.com/OWNER/REPO --token A1B2C3...
   ```
   Это значение после `--token` — **регистрационный токен раннера**. Он действует около **1 часа** и нужен только для регистрации.
2. Впишите в `.env`:
   ```
   RUNNER_REPO_URL=https://github.com/OWNER/REPO
   RUNNER_TOKEN=A1B2C3...
   RUNNER_LABELS=grafana-aac-stand
   ```
3. Запустите раннер (стенд при этом должен быть поднят):
   ```bash
   docker compose --profile ci up -d
   docker compose logs -f github-runner
   ```
   Ожидаемо в логах: `Connected to GitHub` … `Listening for Jobs`. В GitHub в **Settings → Actions → Runners** раннер станет **Idle** (зелёная точка) с метками `self-hosted, Linux, X64, grafana-aac-stand`.
4. Метки (`grafana-aac-stand`) должны совпадать с тем, что в workflow: `runs-on: [self-hosted, grafana-aac-stand]`. Если нужно, поменяйте `RUNNER_LABELS` либо задайте переменную репозитория `STAND_RUNNER_LABELS` (см. ниже).

Заметки:
* Токен регистрации одноразовый и короткоживущий. После регистрации его можно стереть из `.env`. Если контейнер пересоздан (`docker compose down` + `up`), раннер надо регистрировать заново **новым** токеном; старую запись удалите в *Settings → Actions → Runners → … → Remove*, иначе GitHub скажет, что раннер с таким именем уже существует.
* Для постоянной автоматической регистрации образ `myoung34/github-runner` поддерживает персональный токен (`ACCESS_TOKEN`), но это выдача широкого токена контейнеру — для стенда не используем.
* Раннер обновляется сам. Образ закреплён на `2.337.0-ubuntu-noble`; раз в несколько месяцев поднимайте тег.

## Шаг 3. Секреты и переменные

**Settings → Secrets and variables → Actions.**

**Secrets** (вкладка *Secrets* → *New repository secret*) — то, что нельзя показывать:

| Имя | Значение | Откуда взять |
|---|---|---|
| `GRAFANA_AUTH` | токен service account `terraform` | в файле `.secrets/terraform.env`, строка `GRAFANA_AUTH=…` (значение после `=`) |
| `AWS_ACCESS_KEY_ID` | ключ доступа к MinIO | `.secrets/terraform.env` (на стенде `minioadmin`) |
| `AWS_SECRET_ACCESS_KEY` | секретный ключ MinIO | `.secrets/terraform.env` |

**Variables** (вкладка *Variables*) — не секреты, это адреса:

| Имя | Значение для варианта 1 | Для чего |
|---|---|---|
| `GRAFANA_URL` | `http://grafana:3000` | Адрес Grafana **с точки зрения раннера** (внутри docker-сети), а не localhost! |
| `AWS_ENDPOINT_URL_S3` | `http://minio:9000` | Адрес MinIO с точки зрения раннера |
| `STAND_RUNNER_LABELS` | *(не задавать)* | Необязательно. JSON-список меток раннера, например `["ubuntu-24.04"]` для hosted-раннера (вариант 2/3) |

Ту же настройку можно сделать из командной строки (если установлен `gh`):
```bash
gh secret set GRAFANA_AUTH --body "$(grep '^GRAFANA_AUTH=' .secrets/terraform.env | cut -d= -f2-)"
gh secret set AWS_ACCESS_KEY_ID --body "$(grep '^AWS_ACCESS_KEY_ID=' .secrets/terraform.env | cut -d= -f2-)"
gh secret set AWS_SECRET_ACCESS_KEY --body "$(grep '^AWS_SECRET_ACCESS_KEY=' .secrets/terraform.env | cut -d= -f2-)"
gh variable set GRAFANA_URL --body "http://grafana:3000"
gh variable set AWS_ENDPOINT_URL_S3 --body "http://minio:9000"
```

> ⚠️ **Токен меняется.** Каждый `make up` / `make bootstrap` выпускает **новый** токен и удаляет старый. После этого секрет `GRAFANA_AUTH` в GitHub надо обновить, иначе CI получит `401 Unauthorized`. То же после `make reset`.
>
> Секреты в workflow подставляются только через `${{ secrets.… }}` и в логах маскируются (`***`). Не печатайте их через `echo`.

## Шаг 4. Environment с ручным подтверждением (approve)

Job `apply` в `apply.yml` объявлен с `environment: test-stand`. Если у этого environment включены *Required reviewers*, job не стартует, пока ревьюер не подтвердит.

1. **Settings → Environments → New environment** → имя ровно `test-stand` → *Configure environment*.
2. **Required reviewers** → поставьте галочку и добавьте себя и/или команду (до 6 человек). Для личного репозитория достаточно вас самих; чтобы подтверждать мог только другой человек, включите *Prevent self-review*.
3. **Deployment branches and tags** → *Selected branches and tags* → добавьте `main`. Тогда apply невозможен из других веток.
4. Сохраните (**Save protection rules**).

Как выглядит подтверждение: после merge открывается запуск `Apply` во вкладке **Actions**; job `Apply + smoke test` показывает жёлтую плашку *Waiting for review* → кнопка **Review deployments** → отметьте `test-stand` → **Approve and deploy**.

> Требуемые ревьюеры в приватных репозиториях на бесплатном плане GitHub доступны не всегда (зависит от тарифа). Если опция недоступна — используйте публичный репозиторий **без** self-hosted раннера, либо платный план.

## Шаг 5. Защита ветки `main` (branch protection)

**Settings → Branches → Add branch ruleset / Add classic branch protection rule**, ветка `main`:

* ✅ Require a pull request before merging (минимум 1 approval; *Dismiss stale approvals* — по желанию);
* ✅ Require status checks to pass before merging → добавьте проверки (имена видны после первого запуска PR):
  * `Static checks (fmt / validate / lint / tests)`
  * `terraform plan (stand)`
* ✅ Require branches to be up to date before merging;
* ✅ Block force pushes; ✅ запретить удаление ветки.

Без этого любой может залить изменения в `main` мимо проверок — а `main` сразу применяется в Grafana.

## Шаг 6. Первый запуск

1. Создайте ветку, внесите небольшое изменение (например, `threshold` в `alerts/demo-controlled.yaml`), откройте PR.
2. Во вкладке **Checks**: `Static checks` и `terraform plan (stand)` должны стать зелёными, в PR появится комментарий «Terraform plan (тестовый стенд)».
3. Merge → вкладка **Actions** → workflow `Apply` → approve → зелёный `Apply + smoke test`.
4. `Actions → Drift detection → Run workflow` — ручной запуск; без расхождений job зелёный.

## Что смотреть в упавшем workflow

Откройте упавший job и раскройте красный шаг — ошибка почти всегда в последних 20 строках лога.

| Красный шаг | Типичная причина | Что делать |
|---|---|---|
| `terraform fmt -check` | Файл `.tf` не отформатирован. В логе — diff. | Локально `make fmt`, закоммитить |
| `terraform validate` | Опечатка/неверная ссылка в `.tf` | Читать сообщение: оно содержит файл и строку |
| `tflint` | Устаревший синтаксис и т.п. | Читать сообщение |
| `yamllint (alerts/)` | Отступы/пробелы/синтаксис YAML | Номер строки в логе; чаще всего — таб или лишний пробел |
| `Validate dashboards` | Дашборд с `__inputs`/неверным датасорсом | Список проблем в логе; см. [05](05-tutorial-add-dashboard.md) |
| `terraform test (alert-rules)` | В `alerts/*.yaml` смысловая ошибка | Читать сообщение (в нём файл и имя правила) |
| `terraform init` (в plan/apply) | Раннер не видит MinIO (`connection refused`/`no such host`), нет интернета для скачивания провайдера | Проверьте переменную `AWS_ENDPOINT_URL_S3` и что раннер в сети стенда (`docker compose ps`) |
| `terraform plan`/`apply` — `401` / `Invalid API key` | Устарел `GRAFANA_AUTH` | Обновить секрет (токен менялся — см. выше) |
| `terraform plan`/`apply` — `Error acquiring the state lock` | Параллельный запуск или оборванный прошлый | Подождать; если lock «завис» — `terraform force-unlock <ID>` (ID в сообщении) |
| `Smoke test` красный, а `apply` зелёный | Ресурса нет в Grafana или он не защищён provenance | Лог перечисляет, какой именно ✅/❌; зайдите в Grafana, сверьте с кодом |
| Job висит «Waiting for a runner to pick up this job» | Раннер выключен или метки не совпали | `docker compose ps github-runner`, статус *Idle* в Settings → Runners, метки |
| Job висит «Waiting for review» | Ждёт ручного approve | Нажмите *Review deployments* |
| `Drift detection` красный | Grafana отличается от кода | Откройте Summary запуска — там план; см. [07](07-drift-and-rules.md) |

## Обновление версий экшенов

В workflow'ах экшены закреплены по SHA коммита с комментарием версии (`@<sha> # v7.0.1`) — это защита от подмены тега. Добавлен `.github/dependabot.yml`: Dependabot раз в неделю открывает PR на обновление таких SHA. Проверяйте и принимайте их как обычные PR.

## Что улучшить для настоящего продакшена

* Раздельные токены: read-only для `plan` на PR, write — только в environment `apply`.
* `terraform plan -out=tfplan` в одном job и `terraform apply tfplan` именно этого плана в другом (с артефактом плана); сейчас `apply` строит план заново.
* Environment-секреты вместо репозиторных; отдельное окружение `prod` с более строгими ревьюерами.
* Эфемерные раннеры (`EPHEMERAL=true`): каждый job — новый чистый контейнер.
* Уведомления о красном drift-job (Slack/почта) — по умолчанию GitHub пишет только владельцу workflow.
