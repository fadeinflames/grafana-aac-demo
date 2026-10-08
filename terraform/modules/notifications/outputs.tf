output "contact_points" {
  description = "Имена созданных контактных точек."
  value       = [for c in grafana_contact_point.webhook : c.name]
}

output "mute_timings" {
  description = "Имена созданных окон тишины."
  value       = [for m in grafana_mute_timing.this : m.name]
}
