# Датасорс Prometheus. На стенде — единственный датасорс (только метрики, без логов и трейсов).
resource "grafana_data_source" "prometheus" {
  type       = "prometheus"
  name       = var.name
  uid        = var.uid
  url        = var.url
  is_default = true

  # "proxy" — запросы к Prometheus идут от сервера Grafana, а не из браузера.
  access_mode = "proxy"

  json_data_encoded = jsonencode({
    httpMethod   = "POST"
    timeInterval = var.scrape_interval
  })
}
