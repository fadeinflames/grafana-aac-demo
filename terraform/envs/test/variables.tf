# Все значения по умолчанию рассчитаны на учебный стенд из docker-compose.yml.
# Переопределить можно файлом terraform.tfvars (он в .gitignore) или TF_VAR_<имя>.

variable "prometheus_url" {
  description = "Адрес Prometheus так, как его видит Grafana (внутри docker-сети)."
  type        = string
  default     = "http://prometheus:9090"
}

variable "webhook_base_url" {
  description = "Адрес приёмника вебхуков так, как его видит Grafana."
  type        = string
  default     = "http://webhook:8080"
}

# "Почтовые ящики" приёмника вебхуков (webhook-tester). Любой UUID работает.
# Должны совпадать с scripts/common.py (там их читают проверки).
variable "webhook_default_id" {
  description = "UUID ящика для обычных уведомлений."
  type        = string
  default     = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
}

variable "webhook_critical_id" {
  description = "UUID ящика для critical-уведомлений."
  type        = string
  default     = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
}

# Тайминги уведомлений. На стенде короткие, чтобы не ждать; в бою оставьте 30s / 5m / 4h.
variable "notify_group_wait" {
  type    = string
  default = "5s"
}

variable "notify_group_interval" {
  type    = string
  default = "10s"
}

variable "notify_repeat_interval" {
  type    = string
  default = "1h"
}
