variable "rules_dir" {
  description = "Каталог с YAML-файлами алертов (один файл = одна группа правил)."
  type        = string
}

variable "datasource_uid" {
  description = "UID датасорса Prometheus, к которому обращаются алерты."
  type        = string
}

variable "default_folder" {
  description = "Папка Grafana для алертов, если в YAML-файле не указан `folder`."
  type        = string
  default     = "Alerts"
}

variable "default_interval" {
  description = "Как часто проверять правила группы, если в YAML не указан `interval`."
  type        = string
  default     = "1m"
}

variable "disable_provenance" {
  description = <<-EOT
    false (по умолчанию) = правила помечаются в Grafana как "созданные через API"
    и ЗАБЛОКИРОВАНЫ для правки в UI. Ставьте true только для отладки.
  EOT
  type        = bool
  default     = false
}
