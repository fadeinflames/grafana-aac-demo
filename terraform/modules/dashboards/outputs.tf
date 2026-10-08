output "folder_uids" {
  description = "Папки с дашбордами: название => uid."
  value       = { for k, f in grafana_folder.this : k => f.uid }
}

output "dashboard_urls" {
  description = "Файл => URL дашборда в Grafana."
  value       = { for k, d in grafana_dashboard.this : k => d.url }
}
