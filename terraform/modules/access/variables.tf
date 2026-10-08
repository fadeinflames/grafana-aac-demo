variable "folder_uids" {
  description = "Папки, к которым применяются права: название => uid."
  type        = map(string)
}

variable "team_name" {
  description = "Команда, которой выдаётся право ПРОСМОТРА папок."
  type        = string
  default     = "platform"
}
