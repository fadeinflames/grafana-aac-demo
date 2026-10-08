# ============================================================================
#  Модуль access: кто что может делать с папками.
#
#  Идея: всё, что создано Terraform, менять можно ТОЛЬКО через Git.
#  Поэтому ролям Viewer и Editor даём лишь право просмотра (View).
#  Администраторы организации (и service account `terraform`) сохраняют полный доступ.
#
#  ВНИМАНИЕ: grafana_folder_permission задаёт список прав ЦЕЛИКОМ — всё, чего
#  здесь нет (в том числе стандартное "Editor может редактировать"), удаляется.
# ============================================================================
resource "grafana_team" "this" {
  name = var.team_name
}

resource "grafana_folder_permission" "this" {
  for_each = var.folder_uids

  folder_uid = each.value

  permissions {
    role       = "Viewer"
    permission = "View"
  }

  permissions {
    role       = "Editor"
    permission = "View"
  }

  permissions {
    team_id    = grafana_team.this.id
    permission = "View"
  }
}
