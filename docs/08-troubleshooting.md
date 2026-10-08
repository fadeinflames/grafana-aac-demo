# 08. Если что-то сломалось: симптом → причина → что делать

Колонка «Видел» отмечает, встречалась ли проблема **реально** при подготовке стенда (✅) или она **предвидится** по опыту/документации (—).

Как пользоваться: найдите свой текст ошибки в колонке «Симптом» (Ctrl+F). Если не нашли — `make ps`, `make logs`, а затем читайте последние строки лога сломавшегося сервиса: `docker compose logs <сервис> --tail=50`.

## Стенд (Docker)

| № | Симптом | Причина | Что делать | Видел |
|---|---|---|---|---|
| 1 | `Bind for 127.0.0.1:3000 failed: port is already allocated` | Порт занят другой программой (часто — другая Grafana) | В `.env` поменяйте `GRAFANA_PORT` (и аналогично другие порты), повторите `make up`. Узнать, кто занял: `netstat -ano \| findstr :3000` (Windows) | — |
| 2 | `error during connect: ... docker daemon is not running` / `Cannot connect to the Docker daemon` | Docker Desktop не запущен | Запустите Docker Desktop, дождитесь «Engine running» | — |
| 3 | `/bin/sh^M: bad interpreter` или `python: can't open file ... ^M` / скрипт «не найден» | У файла окончания строк **CRLF** (Windows) вместо LF | Репозиторий принудительно держит LF (`.gitattributes`). Если файлы уже испорчены: `git add --renormalize .` и `git checkout -- .`, либо в VS Code смена CRLF → LF внизу справа. Для будущих клонов: `git config --global core.autocrlf false` | — |
| 4 | `make: command not found` / `make: *** No rule to make target` | На Windows нет `make`; либо запустили из cmd, либо не в корне репозитория | Ставьте make (см. [01](01-prerequisites.md)) и запускайте из **Git Bash** в корне проекта; либо используйте команды из [10-cheatsheet.md](10-cheatsheet.md) без make | — |
| 5 | `docker compose up --wait` печатает `container grafana-aac-bootstrap-1 exited (0)` и завершается с ошибкой | Одноразовый контейнер завершился, пока compose ждал «запущенные» | **Исправлено** в этом репозитории: `bootstrap` вынесен в профиль `init` и запускается отдельным шагом внутри `make up`. Если вы запускаете руками — используйте `docker compose up -d --wait` и затем `docker compose run --rm bootstrap` | ✅ |
| 6 | `pull access denied` / `Forbidden` при скачивании MinIO с `quay.io` | `quay.io` недоступен из вашей сети; либо образ удалён | В `.env` задайте `MINIO_IMAGE=` с другим доступным образом MinIO (внутренний реестр). Подробнее об истории образа — в [00](00-overview.md#известные-ограничения) | ✅ (в песочнице агента `quay.io` был закрыт) |
| 7 | Сервис `unhealthy` (чаще `grafana`, `minio`, `prometheus`) | Нехватка памяти, повреждённый том, конфликт портов внутри | `docker compose logs <сервис> --tail=50`. Нехватка памяти — выдайте Docker/WSL2 ≥ 4–6 ГБ. Остальное — `make reset` и `make up` | — |
| 8 | `permission denied` при записи `.secrets/terraform.env` (Linux/macOS) | Каталог `.secrets/` создан Docker'ом от root | `sudo chown -R $USER .secrets`, затем `make bootstrap`. На Windows/Docker Desktop обычно не встречается | — |
| 9 | `bootstrap` печатает `❌ Grafana API вернул 401` | Поменяли пароль админа в `.env` **после** первого запуска: Grafana помнит старый (он в томе) | Верните прежний пароль в `.env` либо `make reset` (удалит все данные стенда) | — |

## Terraform: init / подключение

| № | Симптом | Причина | Что делать | Видел |
|---|---|---|---|---|
| 10 | `Failed to query available provider packages ... registry.terraform.io ... 403/timeout` | Нет доступа к реестру Terraform (корпоративный прокси, блокировка, офлайн) | Проверьте интернет/прокси (`HTTPS_PROXY`). Если реестр закрыт политикой — используйте зеркало провайдеров (`provider_installation { network_mirror/filesystem_mirror }` в CLI-конфиге). Реестр, закрытый политикой, обходить не надо | ✅ (в песочнице агента реестр был закрыт; использовано зеркало из официальных архивов) |
| 11 | `dial tcp 127.0.0.1:9000: connect: connection refused` при `init`/`plan` (S3 backend) | MinIO не запущен | `make ps`, `make up` | — |
| 12 | `no such host: grafana` / `dial tcp: lookup grafana` при запуске terraform **с вашего компьютера** | Переменные окружения взяты из CI (`GRAFANA_URL=http://grafana:3000`) — это имя работает только внутри docker-сети | На хосте нужны `http://localhost:3000` и `http://localhost:9000`: загрузите `.secrets/terraform.env` заново (`make …` делает это сам; в PowerShell — `. .\scripts\load-env.ps1`) | — |
| 13 | `Backend initialization required, please run "terraform init"` | Сменили backend/модули или каталог `.terraform` удалён/поменян | `make init`. (Мы заранее исключили частую причину: `make validate` использует отдельный `TF_DATA_DIR` и не трогает backend.) | — |
| 14 | `Unsupported Terraform Core version` | Установлен Terraform старше 1.11 | Обновите Terraform ([01](01-prerequisites.md)) | — |
| 15 | `The cached package for registry.terraform.io/grafana/grafana ... does not match any of the checksums recorded in the dependency lock file` | В `.terraform.lock.hcl` нет хешей для вашей ОС/архитектуры либо файл повреждён | `make lock`, затем закоммитьте изменённый lock-файл | — |

## Terraform: plan / apply

| № | Симптом | Причина | Что делать | Видел |
|---|---|---|---|---|
| 16 | `Error acquiring the state lock ... PreconditionFailed ... Lock Info: ID: …` | Другой `apply`/`plan` идёт сейчас (вы в соседнем окне, или CI), либо прошлый запуск оборвался | Подождите и повторите. Если уверены, что других запусков нет: `terraform -chdir=terraform/envs/test force-unlock <ID>` | ✅ |
| 17 | `401 Unauthorized` / `Invalid API key` / `unauthorized` от Grafana | Токен устарел: `make up`/`make bootstrap`/`make reset` выпускают **новый** токен и удаляют старый; либо устарел секрет `GRAFANA_AUTH` в GitHub | Локально: `make …` сам читает свежий `.secrets/terraform.env`. В CI: обновите секрет `GRAFANA_AUTH` ([06](06-ci-setup.md)) | — |
| 18 | `403 Forbidden` / `Permission denied` / `You'll need additional permissions` | У service account не та роль (нужен `Admin` на стенде) | Grafana → Administration → Service accounts → `terraform` → роль Admin; либо `make bootstrap` | — |
| 19 | `connection refused` к `localhost:3000` при plan/apply | Grafana не запущена | `make ps`, `make up` | — |
| 20 | `Error: Resource precondition failed ... Файл X.yaml: …` | Ошибка в YAML-алерте (наши проверки). Текст в конце сообщения — по-русски | Прочитайте **последние строки** ошибки, исправьте файл. Примеры: `severity` вне `critical/warning/info`; `threshold: "85%"` (нужно число `85`); `for: 5 minutes` (нужно `5m`); повторяющиеся `name`; нет `summary` | ✅ |
| 21 | `Error: Resource precondition failed ... нет поля "uid"` / `остался блок "__inputs"` (дашборд) | Дашборд экспортирован неправильно | См. [05](05-tutorial-add-dashboard.md): экспорт без галочки «для внешнего использования», добавить `uid` | — |
| 22 | `409 ... a folder with the same name already exists` / `folder already exists` | В Grafana уже есть папка с таким названием (создана руками), а Terraform пытается создать такую же | Переименуйте ручную папку либо подкаталог в `dashboards/`; либо усыновите папку: `terraform import 'module.dashboards.grafana_folder.this["Имя"]' <uid>` | — |
| 23 | `[DELETE /v1/provisioning/contact-points/{UID}][409] ... Contact point is currently referenced by a notification policy` | Вы убрали contact point из кода **и** маршрут на него в одном изменении: Terraform сначала удаляет точку, а политику (где она ещё указана) обновляет после | Делайте в **два шага**: 1) PR, в котором маршрут перенаправлен на другую точку, но сама точка ещё есть → merge → apply; 2) PR, удаляющий точку. Проверено | ✅ |
| 24 | `plan` каждый раз показывает изменения, хотя код не менялся | Кто-то регулярно правит объект руками (drift); либо в JSON дашборда поле, которое Grafana переписывает | Посмотрите, что именно отличается (`~` строки). Для дашборда — приведите JSON к виду, который отдаёт Grafana | — |
| 25 | `plan` пишет `Changes to Outputs` и `exit 2`, хотя ресурсы не менялись | Раньше так вёл себя вывод `url` дашборда (в нём slug от заголовка) | **Исправлено**: теперь выводится `uid`. Если добавляете свои outputs — не выводите изменчивые значения | ✅ |
| 26 | Все алерты в состоянии `Error`, в логе Grafana `connection refused ... prometheus:9999` | Датасорс сломан (чаще всего: правили URL руками → drift) | `make plan` покажет `~ url = … -> "http://prometheus:9090"`; `make apply` вернёт. Проверьте, что `prometheus` healthy | ✅ |
| 27 | Алерты приходят с `DatasourceNoData`/`DatasourceError` | Запрос вернул пустоту или ошибку: опечатка в метрике, Prometheus ещё не собрал данные | Проверьте выражение на http://localhost:9090/graph. На стенде `no_data_state` по умолчанию `OK`; поле можно переопределить в YAML | — |

## Дашборды и алерты

| № | Симптом | Причина | Что делать | Видел |
|---|---|---|---|---|
| 28 | В панели `Datasource prometheus-main was not found` / `${DS_PROMETHEUS}` | В JSON ссылка на датасорс по имени/другому uid или переменная экспорта | `make validate` покажет файл и путь. Замените на `{"type":"prometheus","uid":"prometheus-main"}` | ✅ (валидатор проверен на заведомо сломанном файле) |
| 29 | `❌ ... JSON лежит не в подкаталоге dashboards/<Папка>/` | JSON положили прямо в `dashboards/` | Переложите в подкаталог: подкаталог = папка в Grafana | — |
| 30 | Алерт `Firing`, а в приёмнике вебхуков пусто | Не истёк `group_wait` (5 с); маршрут в mute timing; неверный URL contact point | Подождите. Alerting → Notification policies: активен ли mute timing (`nightly-maintenance` 01:00–03:00 UTC на `severity=info`). Alerting → Contact points → ⋯ → *Test* | — |
| 31 | `make alert-fire` завершается `ТАЙМАУТ`/`❌ За 240с в приёмнике не появилось уведомление …` | Изменили маршрут/адрес contact point: e2e-скрипт ждёт уведомления в ящиках `aaaa…`/`cccc…` | Это ожидаемо, если вы осознанно перенаправили маршрут (в упражнении 4 так и есть). Иначе — `make smoke` и проверьте policy | ✅ |
| 32 | Алерт долго `Pending` | Время срабатывания ≈ `interval` группы + `for` + до 15 с на скрейп | Уменьшите `for`/`interval` для проверки (на стенде минимум `interval` — 10s) | ✅ |
| 33 | `Failed to evaluate rule ... failed to execute query [A]` в логах Grafana | Prometheus недоступен или неверный PromQL | Проверьте `expr` в Prometheus; `docker compose ps prometheus` | ✅ |

## CI

| № | Симптом | Причина | Что делать | Видел |
|---|---|---|---|---|
| 34 | Job висит `Waiting for a runner to pick up this job` | Self-hosted раннер выключен или метки не совпали | `docker compose --profile ci ps`, статус *Idle* в Settings → Actions → Runners; метки `self-hosted, grafana-aac-stand` | — |
| 35 | Раннер при старте: `A runner exists with the same name` / `Http response code: NotFound ... registration` | Токен регистрации истёк (живёт ~1 час) или раннер уже зарегистрирован | Возьмите новый токен; старый раннер удалите в Settings → Actions → Runners | — |
| 36 | `plan` в CI: `no such host: minio` / `connection refused` | Задачу взял раннер **вне** docker-сети (например, hosted) либо `AWS_ENDPOINT_URL_S3` указывает на localhost | Переменные `GRAFANA_URL`, `AWS_ENDPOINT_URL_S3` — адреса с точки зрения раннера (`http://grafana:3000`, `http://minio:9000`), раннер — в сети стенда ([06](06-ci-setup.md)) | — |
| 37 | `plan` в CI: `Error: Failed to get existing workspaces` / `AccessDenied` / `InvalidAccessKeyId` | Неверные/устаревшие `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` в Secrets | Обновите секреты из `.secrets/terraform.env` | — |
| 38 | Комментарий с планом не появился в PR | PR из форка (job `plan` не запускается намеренно) или у job нет `pull-requests: write` | Работайте из веток этого репозитория; права заданы в workflow | — |
| 39 | `Drift detection` красный, хотя «никто ничего не менял» | Возможно, обновился провайдер/Grafana и объект «нормализуется» по-другому либо стенд перезапускали | Откройте Summary запуска: что именно в плане. Если это шум — исправьте код; если реальная правка — см. [07](07-drift-and-rules.md) | — |
| 40 | PR от Dependabot: нет проверки `terraform plan` / «Expected — Waiting» | Job `plan` для Dependabot и форков намеренно пропускается (у них нет секретов) | Так и задумано; проверки `Static checks` отрабатывают. Для обновлений Actions запустите plan вручную после merge (workflow Drift) | — |
| 41 | `. .\scripts\load-env.ps1` → `running scripts is disabled` (PowerShell) | Политика выполнения скриптов Windows | В этом окне: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` | — |

## Когда ничего не помогло

1. `make ps` — все ли сервисы `healthy`?
2. `make logs` — нет ли красных ошибок?
3. `make reset && make up && make init && make apply` — чистый запуск с нуля занимает ~3 минуты и лечит большинство проблем стенда (**удаляет все данные стенда!**).
4. Скопируйте полный текст ошибки (последние ~30 строк) и покажите коллеге/в чат вместе с командой, которую вы запускали.
