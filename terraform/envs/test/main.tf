# ============================================================================
#  Тестовое окружение: подключаем модули и передаём им данные.
#  Здесь нет "логики" — только склейка. Логика живёт в terraform/modules/*.
# ============================================================================

# 1. Датасорс Prometheus ------------------------------------------------------
module "prometheus" {
  source = "../../modules/datasource-prometheus"

  url = var.prometheus_url
  # name/uid берём по умолчанию: "Prometheus" / "prometheus-main"
}

# 2. Папки и дашборды (из каталога dashboards/ в корне репозитория) ------------
module "dashboards" {
  source = "../../modules/dashboards"

  # path.module = каталог этого файла; поднимаемся на три уровня до корня репозитория
  dashboards_dir = "${path.module}/../../../dashboards"

  # Дашборды ссылаются на датасорс по uid — значит, он должен существовать раньше
  depends_on = [module.prometheus]
}

# 3. Алерты (из каталога alerts/ в корне репозитория) --------------------------
module "alert_rules" {
  source = "../../modules/alert-rules"

  rules_dir      = "${path.module}/../../../alerts"
  datasource_uid = module.prometheus.uid
}

# 4. Контактные точки, маршрутизация, окна тишины, шаблоны ---------------------
module "notifications" {
  source = "../../modules/notifications"

  contact_points = {
    "team-webhook"     = { url = "${var.webhook_base_url}/${var.webhook_default_id}" }
    "critical-webhook" = { url = "${var.webhook_base_url}/${var.webhook_critical_id}" }
  }
  default_contact_point = "team-webhook"

  # Маршрут по severity: critical уходит в отдельную контактную точку.
  # info не должен будить людей ночью — к нему привязано окно тишины.
  routes = [
    { severity = "critical", contact_point = "critical-webhook" },
    { severity = "info", contact_point = "team-webhook", mute_timings = ["nightly-maintenance"] },
  ]

  mute_timings = {
    "nightly-maintenance" = { start_time = "01:00", end_time = "03:00", location = "UTC" }
  }

  group_wait      = var.notify_group_wait
  group_interval  = var.notify_group_interval
  repeat_interval = var.notify_repeat_interval
}

# 5. Права: Terraform-ресурсы нельзя править руками -----------------------------
module "access" {
  source = "../../modules/access"

  folder_uids = merge(
    module.dashboards.folder_uids,
    module.alert_rules.folder_uids,
  )
}
