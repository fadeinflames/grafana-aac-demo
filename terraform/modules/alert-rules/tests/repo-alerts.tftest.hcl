# Тесты модуля alert-rules. Запуск:  cd terraform/modules/alert-rules && terraform init -backend=false && terraform test
# Тесты идут с "подделанным" провайдером (mock_provider) — Grafana для них НЕ нужна,
# поэтому они работают на GitHub-hosted раннере и на вашем ноутбуке без стенда.

mock_provider "grafana" {}

variables {
  datasource_uid = "prometheus-main"
}

# --- Позитивный тест: реальные алерты из репозитория проходят все проверки -----
run "real_alerts_from_repo_are_valid" {
  command = plan

  variables {
    rules_dir = "../../../alerts"
  }

  assert {
    condition     = output.rule_count >= 3
    error_message = "В репозитории должно быть минимум 3 алерта в alerts/*.yaml"
  }
}

# --- Негативные тесты: ошибки в YAML должны ловиться понятными проверками -------
run "rejects_unknown_severity" {
  command = plan
  variables {
    rules_dir = "./tests/fixtures/bad-severity"
  }
  expect_failures = [terraform_data.validate]
}

run "rejects_threshold_that_is_not_a_number" {
  command = plan
  variables {
    rules_dir = "./tests/fixtures/bad-threshold"
  }
  expect_failures = [terraform_data.validate]
}

run "rejects_bad_duration_format" {
  command = plan
  variables {
    rules_dir = "./tests/fixtures/bad-duration"
  }
  expect_failures = [terraform_data.validate]
}

run "rejects_duplicate_rule_names" {
  command = plan
  variables {
    rules_dir = "./tests/fixtures/duplicate-names"
  }
  expect_failures = [terraform_data.validate]
}

run "rejects_missing_required_fields" {
  command = plan
  variables {
    rules_dir = "./tests/fixtures/missing-field"
  }
  expect_failures = [terraform_data.validate]
}

run "rejects_group_without_rules" {
  command = plan
  variables {
    rules_dir = "./tests/fixtures/no-rules"
  }
  expect_failures = [terraform_data.validate]
}
