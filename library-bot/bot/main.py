from __future__ import annotations

import asyncio
import html
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from . import convert
from .ai_search import AiPlanner
from .config import Config
from .indexer import build_index, find_inpx, is_stale
from .library import Book, Library

log = logging.getLogger("library-bot")
PAGE = 8


def esc(s: str) -> str:
    return html.escape(s or "")


def short(b: Book) -> str:
    a = b.authors.split(",")[0] if b.authors else "?"
    return f"{a} — {b.title}"[:60]


def build_router(cfg: Config, lib: Library, planner: AiPlanner | None = None) -> Router:
    r = Router()
    # выбранное FTS-выражение и язык для пагинации (callback_data ограничен 64 байтами)
    last_query: dict[int, tuple[str | None, str]] = {}
    langs: dict[int, str] = {}
    can_convert = convert.available(cfg.ebook_convert)

    def allowed(uid: int | None) -> bool:
        return uid is not None and uid in cfg.allowed_users

    @r.message(Command("id"))
    async def cmd_id(m: Message):
        await m.answer(f"Ваш id: <code>{m.from_user.id}</code>", parse_mode="HTML")

    @r.message(CommandStart())
    async def cmd_start(m: Message):
        if not allowed(m.from_user.id):
            return await m.answer("Нет доступа. Ваш id: /id")
        await m.answer(
            "Пришлите автора, название или серию — найду книгу.\n"
            "Например: <i>стругацкие пикник</i>\n\n"
            "/lang ru — искать только на языке (/lang — любой)\n"
            f"Книг в библиотеке: {lib.count():,}".replace(",", " "),
            parse_mode="HTML")

    @r.message(Command("lang"))
    async def cmd_lang(m: Message):
        if not allowed(m.from_user.id):
            return
        arg = (m.text or "").split(maxsplit=1)
        langs[m.from_user.id] = arg[1].strip().lower() if len(arg) > 1 else ""
        await m.answer(f"Язык поиска: {langs[m.from_user.id] or 'любой'}")

    def user_lang(uid: int) -> str:
        return langs.get(uid, cfg.default_lang)

    def render(uid: int, page: int):
        match, lang = last_query[uid]
        books, total = lib.search_match(match, lang, PAGE, page * PAGE) if match else ([], 0)
        if not books:
            return "Ничего не найдено.", None
        rows = [[InlineKeyboardButton(text=short(b), callback_data=f"b:{b.id}")] for b in books]
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀", callback_data=f"p:{page - 1}"))
        if (page + 1) * PAGE < total:
            nav.append(InlineKeyboardButton(text="▶", callback_data=f"p:{page + 1}"))
        if nav:
            rows.append(nav)
        pages = (total + PAGE - 1) // PAGE
        return f"Найдено: {total} (стр. {page + 1}/{pages})", InlineKeyboardMarkup(inline_keyboard=rows)

    @r.message(F.text & ~F.text.startswith("/"))
    async def on_text(m: Message):
        if not allowed(m.from_user.id):
            return await m.answer("Нет доступа. Ваш id: /id")
        uid = m.from_user.id
        status = await m.answer("🔎 Ищу…")
        plan, fail = await planner.plan(m.text) if planner else (None, None)
        last_query[uid] = await asyncio.to_thread(lib.resolve, m.text, plan, user_lang(uid))
        text, kb = await asyncio.to_thread(render, uid, 0)
        if fail:
            text += f"\n(ИИ недоступен: {fail} — искал по тексту как есть)"
        await status.edit_text(text, reply_markup=kb)

    @r.callback_query(F.data.startswith("p:"))
    async def on_page(c: CallbackQuery):
        if not allowed(c.from_user.id) or c.from_user.id not in last_query:
            return await c.answer("Повторите поиск", show_alert=True)
        text, kb = await asyncio.to_thread(render, c.from_user.id, int(c.data[2:]))
        await c.message.edit_text(text, reply_markup=kb)
        await c.answer()

    @r.callback_query(F.data.startswith("b:"))
    async def on_book(c: CallbackQuery):
        if not allowed(c.from_user.id):
            return await c.answer("Нет доступа", show_alert=True)
        b = lib.get(int(c.data[2:]))
        if not b:
            return await c.answer("Книга не найдена", show_alert=True)
        lines = [f"<b>{esc(b.title)}</b>", esc(b.authors)]
        if b.series:
            lines.append(f"Серия: {esc(b.series)}" + (f" #{esc(b.serno)}" if b.serno and b.serno != "0" else ""))
        if b.genres:
            lines.append(f"Жанр: {esc(b.genres)}")
        lines.append(f"{b.ext.upper()}, {b.size / 1024 / 1024:.1f} МБ, язык: {esc(b.lang) or '?'}")
        btns = [InlineKeyboardButton(text=f"⬇ {b.ext.upper()}", callback_data=f"dl:{b.id}:{b.ext}")]
        if can_convert and b.ext == "fb2":
            btns.append(InlineKeyboardButton(text="⬇ EPUB", callback_data=f"dl:{b.id}:epub"))
        await c.message.answer("\n".join(lines), parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[btns]))
        await c.answer()

    @r.callback_query(F.data.startswith("dl:"))
    async def on_download(c: CallbackQuery):
        if not allowed(c.from_user.id):
            return await c.answer("Нет доступа", show_alert=True)
        _, bid, fmt = c.data.split(":")
        b = lib.get(int(bid))
        if not b:
            return await c.answer("Книга не найдена", show_alert=True)
        await c.answer("Готовлю файл…")
        try:
            # зависшая шара не должна вешать бота: ждём не дольше api_timeout
            data = await asyncio.wait_for(asyncio.to_thread(lib.read, b), cfg.api_timeout)
            name = b.filename
            if fmt != b.ext:
                data = await convert.convert(data, b.ext, fmt, cfg.ebook_convert)
                name = name.rsplit(".", 1)[0] + f".{fmt}"
        except FileNotFoundError:
            return await c.message.answer(f"Архив {b.archive} не найден в библиотеке.")
        except asyncio.TimeoutError:
            return await c.message.answer(f"Хранилище не ответило за {cfg.api_timeout:g} с. Попробуйте позже.")
        except Exception as e:  # noqa: BLE001 — показываем причину пользователю
            log.exception("download failed")
            return await c.message.answer(f"Не удалось получить книгу: {esc(str(e))}")
        if len(data) > cfg.max_send_bytes:
            return await c.message.answer("Файл больше 50 МБ — Telegram Bot API его не примет.")
        await c.message.answer_document(BufferedInputFile(data, filename=name))

    return r


async def amain() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config.from_env()
    if not cfg.allowed_users:
        log.warning("ALLOWED_USERS пуст — бот никого не пустит. Узнайте id командой /id")
    inpx = find_inpx(cfg.library_dir, cfg.inpx_file)
    if is_stale(inpx, cfg.db_path):
        log.info("Строю индекс из %s ...", inpx)
        n = await asyncio.to_thread(build_index, inpx, cfg.db_path)
        log.info("Проиндексировано книг: %d", n)
    lib = Library(cfg.library_dir, cfg.db_path)
    bot = Bot(cfg.token)
    dp = Dispatcher()
    planner = AiPlanner(cfg.ai_model, cfg.api_timeout) if cfg.ai_search else None
    log.info("ИИ-поиск: %s", f"{cfg.ai_model}, таймаут {cfg.api_timeout:g} с" if planner else "выключен (нет ANTHROPIC_API_KEY)")
    dp.include_router(build_router(cfg, lib, planner))
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
