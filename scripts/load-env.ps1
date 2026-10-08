# Loads variables from .secrets/terraform.env into the current PowerShell session.
# (Comments and messages are in ASCII on purpose: Windows PowerShell 5.1 reads
#  UTF-8 files without BOM in the ANSI code page and breaks on non-Latin text.)
#
# Usage:   . .\scripts\load-env.ps1
# If PowerShell says "running scripts is disabled", allow scripts for THIS window only:
#          Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$envFile = Join-Path $PSScriptRoot "..\.secrets\terraform.env"
if (-not (Test-Path $envFile)) {
    Write-Error "File $envFile not found. Start the stand first: make up (or docker compose up -d --wait; docker compose run --rm bootstrap)"
    return
}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
}
Write-Host "Terraform environment variables loaded."
