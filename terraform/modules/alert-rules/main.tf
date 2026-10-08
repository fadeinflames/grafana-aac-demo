# ============================================================================
#  Модуль alert-rules: превращает YAML-файлы из каталога alerts/ в правила Grafana.
#
#  Схема работы:
#    alerts/*.yaml --yamldecode--> local.groups --for_each--> grafana_rule_group
#
#  Каждое правило в Grafana состоит из трёх шагов (так же, как в UI):
#    A — запрос в Prometheus (ваш `expr`);
#    B — Reduce: свести временной ряд к одному числу (последнее значение);
#    C — Threshold: сравнить число с порогом. C — условие срабатывания.
# ============================================================================

locals {
  # Все файлы *.yaml / *.yml в каталоге. fileset возвращает имена относительно rules_dir.
  files = fileset(var.rules_dir, "*.{yaml,yml}")

  # Разбираем каждый файл. Ключ — имя файла, значение — разобранное содержимое.
  raw = { for f in local.files : f => yamldecode(file("${var.rules_dir}/${f}")) }

  # Подставляем значения по умолчанию. try(x, default) = "x, а если его нет — default".
  groups = {
    for f, g in local.raw : f => {
      name     = try(g.group, trimsuffix(trimsuffix(f, ".yaml"), ".yml"))
      folder   = try(g.folder, var.default_folder)
      interval = try(g.interval, var.default_interval)
      rules = [
        for r in try(g.rules, []) : {
          name           = try(r.name, "")
          expr           = try(r.expr, "")
          operator       = try(r.operator, "gt")
          threshold      = try(r.threshold, null)
          for_duration   = try(r.for, "5m")
          severity       = try(r.severity, "")
          summary        = try(r.summary, "")
          description    = try(r.description, "")
          runbook_url    = try(r.runbook_url, "")
          labels         = try(r.labels, {})
          no_data_state  = try(r.no_data_state, "OK")
          exec_err_state = try(r.exec_err_state, "Error")
          paused         = try(r.paused, false)
        }
      ]
    }
  }

  # Список папок (без повторов), которые надо создать.
  folders = toset([for g in local.groups : g.folder])

  # Допустимые значения (используются в проверках ниже и в тестах).
  valid_severities = ["critical", "warning", "info"]
  valid_operators  = ["gt", "lt"]
  valid_nodata     = ["OK", "NoData", "Alerting", "KeepLast"]
  valid_exec_err   = ["OK", "Error", "Alerting", "KeepLast"]
  duration_regex   = "^[0-9]+(s|m|h|d)$"

  # Сколько секунд в единице времени (для перевода "1m" -> 60)
  unit_seconds = { s = 1, m = 60, h = 3600, d = 86400 }

  # Преобразование понятных слов в типы Grafana
  operator_to_grafana = { gt = "gt", lt = "lt" }
}

# ----------------------------------------------------------------------------
#  Проверки входных данных. Если в YAML ошибка — terraform plan остановится и
#  покажет, в каком файле и в каком правиле. Это и есть "понятные ошибки".
# ----------------------------------------------------------------------------
resource "terraform_data" "validate" {
  for_each = local.groups

  lifecycle {
    precondition {
      condition     = length(each.value.rules) > 0
      error_message = "Файл ${each.key}: нет ни одного правила. Добавьте список `rules:`."
    }

    precondition {
      condition     = length(distinct([for r in each.value.rules : r.name])) == length(each.value.rules)
      error_message = "Файл ${each.key}: имена правил должны быть уникальными, но есть повторы."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : r.name != "" && r.expr != "" && r.summary != "" && r.threshold != null])
      error_message = "Файл ${each.key}: у каждого правила должны быть поля name, expr, threshold и summary. Одно из них пропущено или пустое."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : contains(local.valid_severities, r.severity)])
      error_message = "Файл ${each.key}: поле severity должно быть одним из: ${join(", ", local.valid_severities)}. Проверьте правила: ${join(", ", [for r in each.value.rules : r.name if !contains(local.valid_severities, r.severity)])}."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : contains(local.valid_operators, r.operator)])
      error_message = "Файл ${each.key}: поле operator должно быть gt (больше) или lt (меньше). Проверьте правила: ${join(", ", [for r in each.value.rules : r.name if !contains(local.valid_operators, r.operator)])}."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : can(tonumber(r.threshold))])
      error_message = "Файл ${each.key}: threshold должен быть числом (например, 85), без кавычек и знака %. Проверьте правила: ${join(", ", [for r in each.value.rules : r.name if !can(tonumber(r.threshold))])}."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : can(regex(local.duration_regex, r.for_duration))]) && can(regex(local.duration_regex, each.value.interval))
      error_message = "Файл ${each.key}: поля `for` и `interval` задаются как число с единицей: 30s, 5m, 1h. Например: for: 5m."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : contains(local.valid_nodata, r.no_data_state) && contains(local.valid_exec_err, r.exec_err_state)])
      error_message = "Файл ${each.key}: no_data_state допускает значения ${join(", ", local.valid_nodata)}, а exec_err_state — ${join(", ", local.valid_exec_err)}."
    }

    precondition {
      condition     = alltrue([for r in each.value.rules : r.runbook_url == "" || startswith(r.runbook_url, "https://") || startswith(r.runbook_url, "http://")])
      error_message = "Файл ${each.key}: runbook_url должен быть ссылкой, начинающейся с http:// или https://."
    }
  }
}

# ----------------------------------------------------------------------------
#  Папки для алертов
# ----------------------------------------------------------------------------
resource "grafana_folder" "alerts" {
  for_each = local.folders

  title = each.value
  # Стабильный uid: если папку переименуют, ссылки на неё не сломаются.
  uid = "alerts-${lower(replace(each.value, "/[^a-zA-Z0-9]+/", "-"))}"
}

# ----------------------------------------------------------------------------
#  Сами правила: по одной группе на каждый YAML-файл
# ----------------------------------------------------------------------------
resource "grafana_rule_group" "this" {
  for_each = local.groups

  name             = each.value.name
  folder_uid       = grafana_folder.alerts[each.value.folder].uid
  interval_seconds = tonumber(regex("^[0-9]+", each.value.interval)) * local.unit_seconds[regex("[smhd]$", each.value.interval)]

  # disable_provenance = false  =>  правила нельзя править в UI (см. docs/07-drift-and-rules.md)
  disable_provenance = var.disable_provenance

  dynamic "rule" {
    for_each = each.value.rules

    content {
      name      = rule.value.name
      condition = "C"
      for       = rule.value.for_duration

      no_data_state  = rule.value.no_data_state
      exec_err_state = rule.value.exec_err_state
      is_paused      = rule.value.paused

      annotations = merge(
        { summary = rule.value.summary },
        rule.value.description != "" ? { description = rule.value.description } : {},
        rule.value.runbook_url != "" ? { runbook_url = rule.value.runbook_url } : {},
      )

      # severity берём из отдельного поля, чтобы его нельзя было забыть или написать с ошибкой
      labels = merge(rule.value.labels, { severity = rule.value.severity })

      # --- Шаг A: запрос в Prometheus -------------------------------------
      data {
        ref_id         = "A"
        datasource_uid = var.datasource_uid
        query_type     = ""

        relative_time_range {
          from = 600 # смотрим на последние 10 минут
          to   = 0
        }

        model = jsonencode({
          refId         = "A"
          datasource    = { type = "prometheus", uid = var.datasource_uid }
          expr          = rule.value.expr
          instant       = true
          range         = false
          intervalMs    = 1000
          maxDataPoints = 43200
        })
      }

      # --- Шаг B: Reduce — свести ряд к одному числу ------------------------
      data {
        ref_id         = "B"
        datasource_uid = "__expr__"
        query_type     = ""

        relative_time_range {
          from = 600
          to   = 0
        }

        model = jsonencode({
          refId      = "B"
          datasource = { type = "__expr__", uid = "__expr__" }
          type       = "reduce"
          expression = "A"
          reducer    = "last"
          settings   = { mode = "dropNN" }
        })
      }

      # --- Шаг C: Threshold — сравнить с порогом (это условие алерта) -------
      data {
        ref_id         = "C"
        datasource_uid = "__expr__"
        query_type     = ""

        relative_time_range {
          from = 600
          to   = 0
        }

        model = jsonencode({
          refId      = "C"
          datasource = { type = "__expr__", uid = "__expr__" }
          type       = "threshold"
          expression = "B"
          conditions = [{
            evaluator = {
              type   = local.operator_to_grafana[rule.value.operator]
              params = [tonumber(rule.value.threshold)]
            }
          }]
        })
      }
    }
  }

  # Группа создаётся только после успешных проверок выше
  depends_on = [terraform_data.validate]
}
