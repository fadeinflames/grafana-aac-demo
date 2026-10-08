# Настройки tflint. Запуск: `tflint --recursive` (в CI — job static-checks).
# Встроенный набор правил "terraform" уже входит в tflint, отдельные плагины качать не нужно.
config {
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
