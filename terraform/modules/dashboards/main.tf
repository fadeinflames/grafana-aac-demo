# ============================================================================
#  Модуль dashboards: каждый JSON из dashboards/<Папка>/<имя>.json -> дашборд в Grafana.
#  Подкаталог = папка в Grafana (создаётся автоматически).
# ============================================================================
locals {
  # Пути вида "Infrastructure/host-overview.json" (относительно dashboards_dir)
  files = fileset(var.dashboards_dir, "*/*.json")

  # Названия папок = имена подкаталогов
  folders = toset([for f in local.files : dirname(f)])
}

resource "grafana_folder" "this" {
  for_each = local.folders

  title = each.value
  uid   = "dash-${lower(replace(each.value, "/[^a-zA-Z0-9]+/", "-"))}"
}

resource "grafana_dashboard" "this" {
  for_each = local.files

  folder      = grafana_folder.this[dirname(each.value)].uid
  config_json = file("${var.dashboards_dir}/${each.value}")
  overwrite   = var.overwrite
  message     = "Applied by Terraform from ${each.value}"

  # В JSON обязательно должен быть "uid" — иначе Grafana придумает его сама и
  # ссылки на дашборд будут меняться при каждом пересоздании.
  lifecycle {
    precondition {
      condition     = can(jsondecode(file("${var.dashboards_dir}/${each.value}"))["uid"])
      error_message = "В ${each.value} нет поля \"uid\". Добавьте его на верхний уровень JSON (например, \"uid\": \"my-dashboard\")."
    }
    precondition {
      condition     = !strcontains(file("${var.dashboards_dir}/${each.value}"), "__inputs")
      error_message = "В ${each.value} остался блок \"__inputs\" — это дашборд, экспортированный с опцией «Export for sharing externally». Экспортируйте заново БЕЗ этой галочки (см. docs/05-tutorial-add-dashboard.md)."
    }
  }
}
