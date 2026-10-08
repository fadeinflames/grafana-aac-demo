# 01. Что установить (Windows 11)

> ⚠️ Эта инструкция написана для Windows 11, но **на Windows не запускалась** (проверка стенда выполнялась на Linux). Версии и выводы команд ниже взяты с Linux; на Windows они могут слегка отличаться. Если вывод не совпал — смотрите «Что делать, если вывод другой».

Нужно пять вещей: **Docker Desktop**, **Git**, **Terraform**, **make** (необязательно) и **редактор кода**. Команды ниже выполняйте в **PowerShell** (если не сказано иное).

## 1. Docker Desktop (с WSL2)

Docker запускает все сервисы стенда в контейнерах.

1. Включите виртуализацию в BIOS/UEFI (обычно включена; если Docker потом пожалуется — проверьте).
2. Установите WSL2 (в PowerShell **от имени администратора**):
   ```powershell
   wsl --install
   ```
   Перезагрузите компьютер.
3. Скачайте и установите Docker Desktop: <https://docs.docker.com/desktop/setup/install/windows-install/> — при установке оставьте галочку **Use WSL 2 instead of Hyper-V**.
4. Запустите Docker Desktop и дождитесь значка «Engine running» (зелёный).
5. Рекомендуется выделить WSL2 минимум 4 ГБ памяти (файл `%UserProfile%\.wslconfig`):
   ```ini
   [wsl2]
   memory=6GB
   ```
   затем `wsl --shutdown` и перезапуск Docker Desktop.

**Проверка:**
```powershell
docker version
docker compose version
```
Ожидаемо: есть блоки `Client` и `Server`; Docker Compose версии v2.x (у нас проверено: Docker 29.8, Compose v5.6). Если блока `Server` нет — Docker Desktop не запущен.

## 2. Git

1. Установите Git for Windows: <https://git-scm.com/download/win>. При установке оставьте **Git Bash** и выберите «Checkout as-is, commit as-is» либо «Checkout Windows-style» — для этого репозитория разницы нет: файл `.gitattributes` принудительно оставляет у `.sh`, `.py`, `.tf`, `.yml` окончания строк LF.
2. Один раз представьтесь:
   ```powershell
   git config --global user.name "Ваше Имя"
   git config --global user.email "you@example.com"
   ```

**Проверка:** `git --version` → `git version 2.xx.x.windows.x`.

> **Про CRLF/LF.** Windows заканчивает строки символами `CRLF`, Linux — `LF`. Скрипт с `CRLF` внутри Linux-контейнера падает с ошибкой вида `/bin/sh^M: bad interpreter`. Поэтому в репозитории есть `.gitattributes`. Если вы всё же столкнулись — см. [08-troubleshooting.md](08-troubleshooting.md).

## 3. Terraform

Нужна версия **1.11 или новее** (в проекте проверено на 1.16.5).

Вариант А (проще всего):
```powershell
winget install --id Hashicorp.Terraform --exact
```
Вариант Б: скачать zip для Windows (amd64) с <https://developer.hashicorp.com/terraform/install>, распаковать `terraform.exe` в, например, `C:\tools\terraform` и добавить эту папку в `PATH` (Параметры → Система → О системе → Дополнительные параметры → Переменные среды).

Откройте **новое** окно PowerShell (чтобы подхватился `PATH`).

**Проверка:**
```powershell
terraform version
```
Ожидаемо:
```
Terraform v1.16.5
on windows_amd64
```
Если версия ниже 1.11 — обновите: в проекте используется блокировка state файлом в бакете (`use_lockfile`), её нет в старых версиях.

## 4. make (необязательно, но удобно)

`make` — это программа, запускающая короткие команды вида `make up` из `Makefile`. На Windows её нет «из коробки».

Вариант А — через winget:
```powershell
winget install --id ezwinports.make --exact
```
Вариант Б — Chocolatey: `choco install make`.

Запускайте `make` **из Git Bash** (в Пуске: «Git Bash»), а не из cmd: Makefile написан для POSIX-оболочки `sh`.

**Проверка (в Git Bash):**
```bash
make --version
```
Ожидаемо: `GNU Make 4.x`.

**Python на Windows ставить не нужно:** все скрипты стенда (включая проверку дашбордов в `make validate`) запускаются внутри контейнера.

**Не хотите ставить make?** Каждой команде `make ...` соответствует обычная команда — таблица в [10-cheatsheet.md](10-cheatsheet.md). Работать можно полностью без make.

## 5. Редактор

Подойдёт любой. Рекомендуем **Visual Studio Code** (<https://code.visualstudio.com/>) с расширениями:

* **HashiCorp Terraform** — подсветка и автодополнение `.tf`;
* **YAML** (Red Hat) — подсказки по отступам;
* **EditorConfig for VS Code** — подхватит настройки из `.editorconfig` (LF, отступы).

В настройках VS Code в правом нижнем углу убедитесь, что для файлов проекта выбрано **LF**, а не CRLF.

## 6. Забрать репозиторий

```powershell
git clone <адрес-вашего-репозитория> grafana-aac-demo
cd grafana-aac-demo
```

Положите проект в простой путь без кириллицы и пробелов, например `C:\work\grafana-aac-demo` — это избавит от множества мелких проблем с путями.

## Итоговая проверка

Выполните одной группой:

```powershell
docker version --format "{{.Server.Version}}"
docker compose version --short
git --version
terraform version
```

| Команда | Ожидаемый вывод | Что делать, если иначе |
|---|---|---|
| `docker version --format "{{.Server.Version}}"` | номер версии, например `29.8.2` | Ошибка «cannot connect to the Docker daemon» — запустите Docker Desktop и подождите минуту |
| `docker compose version --short` | `v2.x`/`v5.x` | Команды `docker-compose` (с дефисом) — это устаревшая версия; обновите Docker Desktop |
| `git --version` | `git version 2.x` | Перезапустите PowerShell после установки |
| `terraform version` | `Terraform v1.11` или выше | Не найдено — проверьте `PATH`; старая версия — обновите |

Дальше: [02-start-stand.md](02-start-stand.md).
