# 02. Запуск стенда

Цель: поднять Grafana, Prometheus, MinIO и остальное **одной командой** и убедиться, что всё работает.

Все команды выполняются в корне репозитория (где лежит `docker-compose.yml`). Если у вас есть `make` — используйте его (Git Bash). Если нет — смотрите блок «Без make» под каждым шагом.

## Шаг 1. Настройки (один раз)

```bash
cp .env.example .env
```
В PowerShell: `Copy-Item .env.example .env`.

Файл `.env` содержит логины, пароли и порты стенда. Значения по умолчанию подходят — ничего менять не нужно. Файл `.env` **не попадает в Git** (он в `.gitignore`).

## Шаг 2. Запуск

```bash
make up
```

**Без make:**
```powershell
docker compose up -d --wait
docker compose run --rm bootstrap
docker compose run --rm tools python set_test_metric.py 0
```

Первый запуск скачивает образы (несколько сотен МБ) — это 2–5 минут, зависит от интернета. Последующие запуски занимают около минуты.

**Ожидаемый вывод в конце:**
```
✅ MinIO: бакет 'tfstate' создан
✅ MinIO: версионирование бакета включено (можно откатить state)
✅ Grafana: создан service account 'terraform' (id=2)
✅ Grafana: выпущен новый токен (старые удалены)
✅ Записан /out/terraform.env (на вашем компьютере: .secrets/terraform.env)
✅ demo_test_value = 0 (Prometheus заберёт значение в течение 15 секунд)

Стенд готов:
  Grafana        http://localhost:3000   (логин/пароль — из .env, по умолчанию admin / admin12345)
  ...
Дальше:  make init && make apply
```

Что произошло «под капотом»:

1. `docker compose up -d --wait` запустил 6 сервисов и дождался, пока у каждого `healthcheck` станет «healthy».
2. `bootstrap` — одноразовый контейнер: создал в MinIO бакет `tfstate` для Terraform state и в Grafana — service account `terraform` с токеном. Токен записан в файл `.secrets/terraform.env` (каталог `.secrets/` в `.gitignore`).
3. `set_test_metric.py 0` положил в Pushgateway тестовую метрику `demo_test_value = 0` («всё хорошо»).

**Что делать, если вывод другой:**

| Симптом | Что делать |
|---|---|
| `port is already allocated` / `Bind for 127.0.0.1:3000 failed` | Порт занят другой программой. Откройте `.env`, поменяйте `GRAFANA_PORT=3000` на, скажем, `3001` (то же для других портов), повторите `make up`. Адреса в этой документации меняйте соответственно. |
| `error during connect ... docker daemon` | Docker Desktop не запущен. Запустите и повторите. |
| `pull access denied` / `Forbidden` на образе MinIO (`quay.io`) | У вас закрыт `quay.io`. В `.env` укажите другой образ в `MINIO_IMAGE=` (например, из внутреннего реестра). |
| Контейнер `minio` или `grafana` в статусе `unhealthy` | `docker compose logs minio` (или `grafana`) — последние строки объяснят причину. Часто не хватает памяти: выдайте Docker Desktop ≥ 4 ГБ. |
| `bootstrap` пишет `❌ Grafana API вернул 401` | В `.env` изменили пароль админа уже после первого запуска (Grafana запомнила старый). Сделайте `make reset` и `make up`. |

## Шаг 3. Проверка, что всё в порядке

```bash
make ps
```
**Без make:** `docker compose ps -a`

Ожидаемый вывод:
```
SERVICE         STATUS
bootstrap       Exited (0) 12 minutes ago
grafana         Up 11 minutes (healthy)
minio           Up 11 minutes (healthy)
node-exporter   Up 11 minutes (healthy)
prometheus      Up 11 minutes (healthy)
pushgateway     Up 11 minutes (healthy)
webhook         Up 11 minutes (healthy)
```
`bootstrap` в статусе `Exited (0)` — это **нормально**: он выполнил работу и завершился успешно. У остальных должно быть `(healthy)`.

## Шаг 4. Открыть сервисы в браузере

| Что | Адрес | Логин / пароль | Что вы должны увидеть |
|---|---|---|---|
| **Grafana** | http://localhost:3000 | `admin` / `admin12345` | Окно входа, затем главная страница. Меню **Dashboards** пустое, **Connections → Data sources** пусто — это правильно: Grafana ничего не создаёт сама. |
| **Prometheus** | http://localhost:9090 | — | Меню **Status → Target health**: 4 цели в состоянии `UP` (prometheus, grafana, node-exporter, test-generator). |
| **Приёмник вебхуков** | http://localhost:8081/s/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa | — | Пустой «ящик». Сюда будут приходить уведомления Grafana. Второй ящик — для critical: `.../s/cccccccc-cccc-4ccc-8ccc-cccccccccccc` |
| **MinIO** | http://localhost:9001 | `minioadmin` / `minioadmin123` | В разделе **Buckets** есть `tfstate`. После `make apply` в нём появится файл state. |
| **Pushgateway** | http://localhost:9091 | — | Метрика `demo_test_value` (группа `demo-generator`). |

> Первый вход в Grafana может предложить сменить пароль — для стенда нажмите **Skip**.

Быстрая проверка из командной строки (должен вернуться JSON с `"database": "ok"`):
```bash
curl http://localhost:3000/api/health
```
В PowerShell используйте `curl.exe`, а не `curl` (в PowerShell `curl` — это алиас на другую команду).

## Остановка и сброс

| Что нужно | Команда | Что произойдёт |
|---|---|---|
| Пауза (выключить на ночь) | `make down` (без make: `docker compose down`) | Контейнеры остановлены и удалены, **данные сохранены** (тома). При следующем `make up` всё будет на месте. |
| Начать с чистого листа | `make reset` (без make: `docker compose down -v` и удалить `.secrets/terraform.env`) | Удаляется **всё**: Grafana, метрики, state Terraform, токен. После `make up` Grafana снова пустая — и `make apply` создаст всё заново. |

> После `make reset` Terraform state в MinIO тоже новый и пустой. Повторять `make init` не обязательно (backend тот же), но и вреда нет.

Логи: `make logs` (без make: `docker compose logs -f --tail=50`), выход — `Ctrl+C`.

## Тестовая метрика и первое знакомство с алертом

Прежде чем создавать что-то в Grafana, можно убедиться, что метрики текут:

1. Откройте Prometheus http://localhost:9090/graph, введите `demo_test_value` и нажмите **Execute**. Должно вернуться значение `0`.
2. Введите `100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)` — это загрузка CPU стенда в процентах.

Следующий шаг: [03-first-apply.md](03-first-apply.md) — создаём всё в Grafana из кода.
