# Загружает переменные из .secrets/terraform.env в текущую сессию PowerShell.
# Использование (ТОЧКА и пробел в начале обязательны не нужны, достаточно запустить):
#     . .\scripts\load-env.ps1
# После этого можно запускать terraform из terraform\envs\test.
$envFile = Join-Path $PSScriptRoot "..\.secrets\terraform.env"
if (-not (Test-Path $envFile)) {
    Write-Error "Нет файла $envFile. Сначала запустите стенд: docker compose up -d --wait"
    return
}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
}
Write-Host "Переменные окружения для Terraform загружены."
