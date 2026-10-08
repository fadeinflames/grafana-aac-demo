# ============================================================================
#  Makefile — короткие команды для всего стенда. Справка:  make help
#
#  Windows: запускайте make из Git Bash (не из cmd). Если make не установлен,
#  нужные команды написаны в docs/10-cheatsheet.md — их можно выполнить вручную.
# ============================================================================
SHELL := /bin/sh

TF_DIR  := terraform/envs/test
# На Windows (Git Bash) обычно "python", на Linux/macOS "python3"
PY      := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
TOOLS   := docker compose run --rm -T tools python
# AUTO=1 make apply  — применить без вопроса "yes" (используйте осознанно)
APPLY_FLAGS := $(if $(AUTO),-auto-approve,)

# Адреса и токены для Terraform создаёт bootstrap и кладёт в .secrets/terraform.env.
# Строки вида КЛЮЧ=ЗНАЧЕНИЕ становятся переменными make и экспортируются в terraform.
-include .secrets/terraform.env
export

.DEFAULT_GOAL := help
.PHONY: help up bootstrap down reset ps logs init fmt validate test-unit plan apply smoke alert-fire alert-fire-critical alert-resolve test e2e drift-dashboard drift-datasource drift-rule drift-rule-ui lock

help: ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------- стенд ----
up: ## Поднять стенд (Grafana, Prometheus, MinIO ...) и выдать токен для Terraform
	@test -f .env || cp .env.example .env
	@mkdir -p .secrets
	docker compose up -d --wait
	docker compose run --rm bootstrap
	@docker compose run --rm -T tools python set_test_metric.py 0
	@echo ""
	@echo "Стенд готов:"
	@echo "  Grafana        http://localhost:3000   (логин/пароль — из .env, по умолчанию admin / admin12345)"
	@echo "  Prometheus     http://localhost:9090"
	@echo "  Webhook-ящики  http://localhost:8081/s/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
	@echo "  MinIO console  http://localhost:9001   (minioadmin / minioadmin123)"
	@echo "Дальше:  make init && make apply"

bootstrap: ## Перевыпустить токен для Terraform и перепроверить бакет MinIO (старый токен перестанет работать)
	docker compose run --rm bootstrap

down: ## Остановить стенд (данные сохраняются)
	docker compose down

reset: ## Удалить стенд ВМЕСТЕ с данными (Grafana, state, токен) — чистый лист
	docker compose down -v --remove-orphans
	rm -f .secrets/terraform.env

ps: ## Статус сервисов
	docker compose ps -a

logs: ## Логи всех сервисов (Ctrl+C — выйти)
	docker compose logs -f --tail=50

# ------------------------------------------------------------- terraform ----
init: ## terraform init (скачать провайдер, подключить state в MinIO)
	terraform -chdir=$(TF_DIR) init -input=false

fmt: ## Автоформатирование всех .tf-файлов
	terraform fmt -recursive terraform

validate: ## Все проверки без доступа к Grafana: fmt, validate, дашборды, юнит-тесты модулей
	terraform fmt -check -recursive -diff terraform
	TF_DATA_DIR=$(CURDIR)/.tf-validate terraform -chdir=$(TF_DIR) init -backend=false -input=false
	TF_DATA_DIR=$(CURDIR)/.tf-validate terraform -chdir=$(TF_DIR) validate
	$(PY) scripts/validate_dashboards.py
	$(MAKE) test-unit

test-unit: ## Юнит-тесты модуля alert-rules (проверка YAML-алертов, Grafana не нужна)
	TF_DATA_DIR=$(CURDIR)/.tf-validate-alert-rules terraform -chdir=terraform/modules/alert-rules init -backend=false -input=false
	TF_DATA_DIR=$(CURDIR)/.tf-validate-alert-rules terraform -chdir=terraform/modules/alert-rules test

plan: ## terraform plan — показать, что изменится в Grafana (ничего не меняет)
	terraform -chdir=$(TF_DIR) plan -input=false

apply: ## terraform apply — применить изменения (спросит yes; AUTO=1 — без вопроса)
	terraform -chdir=$(TF_DIR) apply -input=false $(APPLY_FLAGS)

lock: ## Пересчитать .terraform.lock.hcl для всех платформ (после смены версии провайдера)
	terraform -chdir=$(TF_DIR) providers lock -platform=linux_amd64 -platform=linux_arm64 -platform=windows_amd64 -platform=darwin_amd64 -platform=darwin_arm64

# --------------------------------------------------------------- проверки ---
smoke: ## Проверить, что все ресурсы из Git реально есть в Grafana
	$(TOOLS) smoke.py

alert-fire: ## Вызвать срабатывание тестового алерта и дождаться уведомления в вебхуке
	$(TOOLS) alert_e2e.py fire

alert-fire-critical: ## То же, но ещё и critical-алерт (проверка маршрутизации по severity)
	$(TOOLS) alert_e2e.py fire-critical

alert-resolve: ## Снять тестовый алерт и дождаться уведомления "resolved"
	$(TOOLS) alert_e2e.py resolve

e2e: ## Полный цикл: fire -> уведомления -> resolve (~2-3 минуты)
	$(TOOLS) alert_e2e.py cycle

test: validate smoke e2e ## Всё сразу: проверки кода, smoke, e2e

# ------------------------------------------------------- учебный "вред" -----
drift-dashboard: ## Переименовать дашборд "руками" -> потом make plan покажет drift
	$(TOOLS) drift.py dashboard

drift-datasource: ## Испортить URL датасорса "руками"
	$(TOOLS) drift.py datasource

drift-rule: ## Поменять правило в обход блокировки (через API)
	$(TOOLS) drift.py rule

drift-rule-ui: ## Показать, что UI не даёт править правила, созданные Terraform
	$(TOOLS) drift.py rule-ui
