output "folder_uids" {
  description = "Папки с дашбордами: название => uid."
  value       = { for k, f in grafana_folder.this : k => f.uid }
}

output "dashboard_uids" {
  description = "Файл => uid дашборда. Ссылка: <GRAFANA_URL>/d/<uid>. (URL целиком не выводим: в нём slug от заголовка, и он «плавает».)"
  value       = { for k, d in grafana_dashboard.this : k => d.uid }
}
