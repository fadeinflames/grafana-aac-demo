# ============================================================================
#  Модуль notifications: КУДА и КОГДА отправлять уведомления.
#
#    алерт --(labels)--> notification policy --(маршрут)--> contact point --> webhook
#                                  |
#                                  +-- mute timing (окна тишины)
#
#  ВНИМАНИЕ: notification policy в Grafana — ОДНА НА ОРГАНИЗАЦИЮ ("дерево
#  маршрутов"). Ресурс grafana_notification_policy перезаписывает его целиком.
#  Поэтому он должен быть описан ровно в одном месте — здесь.
# ============================================================================

# Шаблон текста сообщения (файл templates/aac.tmpl)
resource "grafana_message_template" "aac" {
  name     = "aac"
  template = file("${path.module}/templates/aac.tmpl")
}

# Контактные точки (webhook)
resource "grafana_contact_point" "webhook" {
  for_each = var.contact_points

  name = each.key

  webhook {
    url         = each.value.url
    http_method = "POST"
    # Текст берём из шаблона выше. Явная зависимость нужна, чтобы шаблон
    # существовал к моменту создания контактной точки.
    message = "{{ template \"aac.message\" . }}"
  }

  depends_on = [grafana_message_template.aac]
}

# Окна тишины
resource "grafana_mute_timing" "this" {
  for_each = var.mute_timings

  name = each.key

  intervals {
    weekdays = length(each.value.weekdays) > 0 ? each.value.weekdays : null
    location = each.value.location

    dynamic "times" {
      for_each = each.value.start_time != null && each.value.end_time != null ? [1] : []
      content {
        start = each.value.start_time
        end   = each.value.end_time
      }
    }
  }
}

# Дерево маршрутизации
resource "grafana_notification_policy" "this" {
  # Корень: сюда попадает всё, что не подошло под маршруты ниже
  contact_point   = grafana_contact_point.webhook[var.default_contact_point].name
  group_by        = ["alertname", "grafana_folder"]
  group_wait      = var.group_wait
  group_interval  = var.group_interval
  repeat_interval = var.repeat_interval

  # По одному дочернему маршруту на каждый элемент var.routes
  dynamic "policy" {
    for_each = var.routes

    content {
      matcher {
        label = "severity"
        match = "="
        value = policy.value.severity
      }
      contact_point = grafana_contact_point.webhook[policy.value.contact_point].name
      mute_timings  = [for m in policy.value.mute_timings : grafana_mute_timing.this[m].name]
    }
  }
}
