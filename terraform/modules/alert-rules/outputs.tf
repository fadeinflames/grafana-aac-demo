output "folder_uids" {
  description = "Папки с алертами: название => uid (нужно модулю access)."
  value       = { for k, f in grafana_folder.alerts : k => f.uid }
}

output "rule_groups" {
  description = "Созданные группы правил: файл => имя группы."
  value       = { for f, g in grafana_rule_group.this : f => g.name }
}

output "rule_count" {
  description = "Сколько правил описано в YAML."
  value       = sum([for g in local.groups : length(g.rules)])
}
