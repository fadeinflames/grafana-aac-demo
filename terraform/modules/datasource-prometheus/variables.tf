variable "name" {
  description = "Отображаемое имя датасорса в Grafana."
  type        = string
  default     = "Prometheus"
}

variable "uid" {
  description = <<-EOT
    Постоянный идентификатор датасорса. ВАЖНО: дашборды в dashboards/*.json и алерты
    ссылаются на датасорс именно по этому uid, а не по имени. Менять нельзя без
    правки всех дашбордов.
  EOT
  type        = string
  default     = "prometheus-main"
}

variable "url" {
  description = "Адрес Prometheus так, как его видит САМА Grafana (внутри docker-сети)."
  type        = string
  default     = "http://prometheus:9090"
}

variable "scrape_interval" {
  description = "Интервал скрейпа Prometheus (должен совпадать с prometheus.yml), нужен для корректных rate()."
  type        = string
  default     = "15s"
}
