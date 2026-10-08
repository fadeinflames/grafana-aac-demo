output "datasource_uid" {
  value = module.prometheus.uid
}

output "dashboard_urls" {
  value = module.dashboards.dashboard_urls
}

output "alert_rule_groups" {
  value = module.alert_rules.rule_groups
}

output "alert_rule_count" {
  value = module.alert_rules.rule_count
}

output "contact_points" {
  value = module.notifications.contact_points
}
