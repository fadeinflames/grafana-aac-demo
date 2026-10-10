# library-bot — Telegram-бот для коллекции MyHomeLib

Ищет книги в локальной коллекции MyHomeLib (индекс `.inpx` + zip-архивы `fb2-*.zip`)
и присылает их в Telegram. Торренты не нужны: коллекция лежит на сервере или шаре,
бот достаёт нужный файл прямо из zip.

Сам MyHomeLib (программа) боту не нужен — только файлы коллекции.

## Как это работает
1. При старте бот читает `.inpx` и строит поисковый индекс SQLite FTS5 (`DB_PATH`).
   Для коллекции в сотни тысяч книг это десятки секунд. Индекс перестраивается сам,
   если `.inpx` изменился.
2. Вы пишете боту «автор название» → список кнопок → карточка → ⬇ FB2 / ⬇ EPUB.
3. EPUB делается на лету через calibre (`ebook-convert`), если он установлен.

## Установка (Linux)
```bash
sudo useradd -r -s /usr/sbin/nologin librarybot
sudo mkdir -p /opt/library-bot /var/lib/library-bot
sudo cp -r bot requirements.txt .env.example /opt/library-bot/
cd /opt/library-bot
sudo python3 -m venv venv && sudo venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env      # BOT_TOKEN, LIBRARY_DIR, ALLOWED_USERS
sudo chown -R librarybot /opt/library-bot /var/lib/library-bot
sudo cp deploy/library-bot.service /etc/systemd/system/   # из репозитория
sudo systemctl enable --now library-bot
journalctl -u library-bot -f
```
- Токен: создайте бота у @BotFather.
- `ALLOWED_USERS`: сначала запустите с пустым значением, напишите боту `/id`, впишите свой id и перезапустите.
  Пока список пуст, бот никого не пускает.
- `LIBRARY_DIR`: папка, где лежат `.inpx` и zip-архивы. Для шары смонтируйте её (NFS/SMB) на чтение.
  Пользователю `librarybot` нужен доступ на чтение.
- EPUB: `sudo apt install calibre` (необязательно).

## Ограничения
- Telegram Bot API принимает файлы до 50 МБ. Для книг этого хватает.
- Поиск по автору, названию и серии, по всем словам (AND), с префиксами и грубым учётом окончаний.
- Если в `.inpx` есть удалённые книги (`DEL=1`), они пропускаются.

## Тесты
```bash
pip install -r requirements-dev.txt && python -m pytest
```
