variable "dashboards_dir" {
  description = "Корневой каталог с дашбордами. Подкаталоги = папки в Grafana: <dashboards_dir>/<Папка>/<имя>.json"
  type        = string
}

variable "overwrite" {
  description = "true — перезаписывать дашборд, если с таким uid уже есть (например, созданный руками)."
  type        = bool
  default     = true
}
