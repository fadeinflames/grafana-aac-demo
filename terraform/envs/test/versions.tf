# ============================================================================
#  Версии и хранилище state. Точка входа тестового окружения.
#  Запускать terraform нужно из ЭТОГО каталога (terraform/envs/test).
# ============================================================================
terraform {
  # Версия самого Terraform: >= 1.11 нужен для блокировок state без DynamoDB
  # (use_lockfile). Точную версию CI берёт из файла .terraform-version.
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    grafana = {
      source = "grafana/grafana"
      # Точная версия, без "~>". Обновление провайдера = осознанный PR
      # с `terraform init -upgrade` и новым .terraform.lock.hcl.
      version = "4.49.0"
    }
  }

  # --------------------------------------------------------------------------
  #  Remote state в S3-совместимом хранилище (на стенде — MinIO).
  #  Адрес хранилища и ключи НЕ пишем в код — они приходят из переменных окружения:
  #    AWS_ENDPOINT_URL_S3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  #  (make берёт их из .secrets/terraform.env, CI — из GitHub Secrets).
  #  В бою замените блок на свой backend (S3, GCS, GitLab, Terraform Cloud...).
  # --------------------------------------------------------------------------
  backend "s3" {
    bucket = "tfstate"
    key    = "envs/test/terraform.tfstate"
    region = "us-east-1" # для MinIO значение формальное

    # Блокировка state файлом в самом бакете: пока идёт apply, второй apply
    # получит ошибку "state locked" вместо того, чтобы испортить state.
    use_lockfile = true

    # Настройки для не-AWS S3 (MinIO): не ходить в AWS за проверками.
    use_path_style              = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
  }
}
