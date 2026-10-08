variable "contact_points" {
  description = <<-EOT
    Контактные точки типа webhook: имя => { url }.
    Пример: { "team-webhook" = { url = "http://webhook:8080/abc" } }
    Другие типы (email, slack, telegram...) добавляются в main.tf по образцу — см. docs/00-overview.md.
  EOT
  type        = map(object({ url = string }))

  validation {
    condition     = length(var.contact_points) > 0
    error_message = "Нужна хотя бы одна контактная точка."
  }
}

variable "default_contact_point" {
  description = "Куда идут все алерты, не подошедшие ни под один маршрут."
  type        = string

  validation {
    condition     = contains(keys(var.contact_points), var.default_contact_point)
    error_message = "default_contact_point должен быть одним из имён в contact_points."
  }
}

variable "routes" {
  description = <<-EOT
    Маршруты по severity (проверяются сверху вниз, первое совпадение побеждает):
    [{ severity = "critical", contact_point = "critical-webhook", mute_timings = [] }, ...]
  EOT
  type = list(object({
    severity      = string
    contact_point = string
    mute_timings  = optional(list(string), [])
  }))
  default = []

  validation {
    condition     = alltrue([for r in var.routes : contains(["critical", "warning", "info"], r.severity)])
    error_message = "В routes поле severity должно быть critical, warning или info."
  }

  validation {
    condition     = alltrue([for r in var.routes : contains(keys(var.contact_points), r.contact_point)])
    error_message = "В routes указана contact_point, которой нет в contact_points."
  }

  validation {
    condition     = alltrue(flatten([for r in var.routes : [for m in r.mute_timings : contains(keys(var.mute_timings), m)]]))
    error_message = "В routes указан mute timing, которого нет в mute_timings."
  }
}

variable "mute_timings" {
  description = <<-EOT
    Окна, когда уведомления НЕ отправляются: имя => расписание.
    weekdays — например ["saturday", "sunday"] или ["monday:friday"];
    start_time/end_time — "HH:MM" (end не включается); location — часовой пояс IANA.
  EOT
  type = map(object({
    weekdays   = optional(list(string), [])
    start_time = optional(string)
    end_time   = optional(string)
    location   = optional(string, "UTC")
  }))
  default = {}
}

variable "group_wait" {
  description = "Сколько ждать перед ПЕРВЫМ уведомлением о группе алертов (в бою обычно 30s)."
  type        = string
  default     = "30s"
}

variable "group_interval" {
  description = "Минимальная пауза между уведомлениями об ИЗМЕНЕНИЯХ в группе, в том числе о восстановлении (в бою обычно 5m)."
  type        = string
  default     = "5m"
}

variable "repeat_interval" {
  description = "Как часто повторять уведомление о всё ещё горящем алерте (в бою обычно 4h)."
  type        = string
  default     = "4h"
}
