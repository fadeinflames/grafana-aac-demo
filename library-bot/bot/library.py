from __future__ import annotations

import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Book:
    id: int
    archive: str
    file: str
    ext: str
    size: int
    lang: str
    authors: str
    title: str
    series: str
    serno: str
    genres: str

    @property
    def filename(self) -> str:
        base = " - ".join(x for x in (self.authors.split(",")[0] if self.authors else "", self.title) if x)
        base = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", base).strip(" ._")[:120] or self.file
        return f"{base}.{self.ext}"


_COLS = "id,archive,file,ext,size,lang,authors,title,series,serno,genres"


class Library:
    def __init__(self, library_dir: Path, db_path: Path):
        self.dir = library_dir
        self.db_path = db_path

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        return con

    @staticmethod
    def terms(text: str) -> list[str]:
        """Слова запроса как префиксные FTS-термы (у длинных слов отрезаем 2 буквы)."""
        words = re.findall(r"\w+", text.lower(), re.UNICODE)
        return [f'"{w[:-2] if len(w) >= 6 else w}"*' for w in words]

    @staticmethod
    def fts_query(text: str) -> str | None:
        """Каждое слово становится префиксным термом; все слова должны встретиться (AND).

        Стемминга в FTS5 нет, поэтому у длинных слов отрезаем 2 последние буквы:
        «стругацкие» -> «стругацк»* находит и «Стругацкий».
        """
        return " ".join(Library.terms(text)) or None

    def search(self, text: str, lang: str = "", limit: int = 8, offset: int = 0) -> tuple[list[Book], int]:
        q = self.fts_query(text)
        if not q:
            return [], 0
        return self.search_match(q, lang, limit, offset)

    def search_match(self, match: str, lang: str = "", limit: int = 8, offset: int = 0) -> tuple[list[Book], int]:
        """Поиск по готовому FTS5-выражению."""
        where, args = "books_fts MATCH ?", [match]
        if lang:
            where += " AND b.lang = ?"
            args.append(lang)
        con = self._con()
        try:
            total = con.execute(
                f"SELECT count(*) FROM books_fts JOIN books b ON b.id = books_fts.rowid WHERE {where}", args
            ).fetchone()[0]
            rows = con.execute(
                f"SELECT {', '.join('b.' + c for c in _COLS.split(','))} FROM books_fts "
                f"JOIN books b ON b.id = books_fts.rowid WHERE {where} "
                "ORDER BY bm25(books_fts, 3.0, 10.0, 1.0), b.id LIMIT ? OFFSET ?",
                [*args, limit, offset],
            ).fetchall()
        finally:
            con.close()
        return [Book(*r) for r in rows], total

    def candidates(self, text: str, plan=None) -> list[str]:
        """FTS-выражения от точного к грубому. Первое, давшее результат, и используется."""
        out: list[str] = []
        if plan is not None:
            parts = []
            for col, val in (("authors", plan.author), ("title", plan.title), ("series", plan.series)):
                t = self.terms(val)
                if t:
                    parts.append(f"{col} : ({' '.join(t)})")
            kw = self.terms(" ".join(plan.keywords))
            if kw:
                parts.append(f"({' '.join(kw)})")
            if parts:
                out.append(" ".join(parts))
            flat = self.terms(" ".join([plan.author, plan.title, plan.series, *plan.keywords]))
            if flat:
                out.append(" ".join(flat))
            variants = [q for q in (self.fts_query(v) for v in plan.variants) if q]
            if variants:
                out.append(" OR ".join(f"({v})" for v in variants))
        raw = self.fts_query(text)
        if raw:
            out.append(raw)
        return list(dict.fromkeys(out))

    def resolve(self, text: str, plan=None, lang: str = "") -> tuple[str | None, str]:
        """Выбирает выражение и язык для поиска (и для пагинации). Возвращает (match, lang)."""
        cands = self.candidates(text, plan)
        plan_lang = (plan.lang.strip().lower() if plan is not None else "")
        # язык пользователя главнее; язык из запроса применяем, но не ценой пустого результата
        langs = [lang] if lang else ([plan_lang, ""] if plan_lang else [""])
        for cand in cands:
            for lg in langs:
                try:
                    if self.search_match(cand, lg, 1, 0)[1]:
                        return cand, lg
                except sqlite3.OperationalError:  # кривое выражение от ИИ — пробуем следующее
                    break
        return (cands[-1] if cands else None), langs[0]

    def get(self, book_id: int) -> Book | None:
        con = self._con()
        try:
            r = con.execute(f"SELECT {_COLS} FROM books WHERE id = ?", (book_id,)).fetchone()
        finally:
            con.close()
        return Book(*r) if r else None

    def count(self) -> int:
        con = self._con()
        try:
            return con.execute("SELECT count(*) FROM books").fetchone()[0]
        finally:
            con.close()

    def read(self, book: Book) -> bytes:
        """Достаёт файл книги из zip-архива, не распаковывая остальное."""
        arch = (self.dir / book.archive).resolve()
        if self.dir.resolve() not in arch.parents:
            raise ValueError("bad archive path")
        if not arch.is_file():
            raise FileNotFoundError(book.archive)
        with zipfile.ZipFile(arch) as z:
            return z.read(f"{book.file}.{book.ext}")
