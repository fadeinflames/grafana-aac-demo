output "uid" {
  description = "UID датасорса (передаётся в модуль alert-rules и используется в JSON дашбордов)."
  value       = grafana_data_source.prometheus.uid
}
