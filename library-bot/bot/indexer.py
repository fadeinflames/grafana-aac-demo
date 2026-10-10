"""Индексатор .inpx (формат индекса MyHomeLib / Flibusta) в SQLite FTS5.

INPX — это zip, внутри которого лежат файлы *.inp (по одному на zip-архив с книгами)
и служебные collection.info / version.info / structure.info (необязательно).
Каждая строка .inp — одна книга, поля разделены символом 0x04.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Iterator

SEP = "\x04"
DEFAULT_STRUCTURE = "AUTHOR;GENRE;TITLE;SERIES;SERNO;FILE;SIZE;LIBID;DEL;EXT;DATE;LANG;LIBRATE;KEYWORDS"

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    archive TEXT NOT NULL,     -- имя zip-архива в LIBRARY_DIR
    file TEXT NOT NULL,        -- имя файла внутри архива без расширения
    ext TEXT NOT NULL,
    size INTEGER,
    lang TEXT,
    authors TEXT,
    title TEXT,
    series TEXT,
    serno TEXT,
    genres TEXT
);
CREATE VIRTUAL TABLE books_fts USING fts5(
    authors, title, series, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def format_authors(raw: str) -> str:
    """'Стругацкий,Аркадий,Натанович:Стругацкий,Борис,Натанович:' -> 'Аркадий Стругацкий, Борис Стругацкий'."""
    out = []
    for a in raw.split(":"):
        parts = [p.strip() for p in a.split(",")]
        if not parts or not parts[0]:
            continue
        last, first = parts[0], parts[1] if len(parts) > 1 else ""
        out.append(f"{first} {last}".strip())
    return ", ".join(out)


def parse_inp(lines: Iterator[str], structure: list[str], archive: str) -> Iterator[tuple]:
    idx = {name: i for i, name in enumerate(structure)}

    def get(fields: list[str], name: str) -> str:
        i = idx.get(name)
        return fields[i].strip() if i is not None and i < len(fields) else ""

    for line in lines:
        line = line.rstrip("\r\n")
        if not line:
            continue
        f = line.split(SEP)
        file, ext = get(f, "FILE"), get(f, "EXT").lower().lstrip(".")
        if not file or not ext or get(f, "DEL") == "1":
            continue
        try:
            size = int(get(f, "SIZE") or 0)
        except ValueError:
            size = 0
        yield (
            archive, file, ext, size, get(f, "LANG").lower(),
            format_authors(get(f, "AUTHOR")), get(f, "TITLE"), get(f, "SERIES"),
            get(f, "SERNO"), get(f, "GENRE").replace(":", ", ").strip(", "),
        )


def build_index(inpx_path: Path, db_path: Path) -> int:
    """Строит индекс во временный файл и атомарно подменяет им db_path. Возвращает число книг."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(db_path.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    total = 0
    with zipfile.ZipFile(inpx_path) as z:
        structure = DEFAULT_STRUCTURE
        if "structure.info" in z.namelist():
            structure = z.read("structure.info").decode("utf-8", "replace").strip() or structure
        fields = [s.strip().upper() for s in structure.split(";") if s.strip()]
        for name in sorted(n for n in z.namelist() if n.lower().endswith(".inp")):
            archive = Path(name).stem + ".zip"
            with z.open(name) as raw:
                text = (ln.decode("utf-8", "replace") for ln in raw)
                rows = list(parse_inp(text, fields, archive))
            for row in rows:
                cur = con.execute(
                    "INSERT INTO books(archive,file,ext,size,lang,authors,title,series,serno,genres)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)", row)
                con.execute(
                    "INSERT INTO books_fts(rowid,authors,title,series) VALUES (?,?,?,?)",
                    (cur.lastrowid, row[5], row[6], row[7]))
            total += len(rows)
    con.execute("INSERT INTO meta VALUES ('inpx_mtime', ?)", (str(inpx_path.stat().st_mtime),))
    con.execute("INSERT INTO meta VALUES ('count', ?)", (str(total),))
    con.commit()
    con.execute("INSERT INTO books_fts(books_fts) VALUES ('optimize')")
    con.commit()
    con.close()
    os.replace(tmp, db_path)
    return total


def find_inpx(library_dir: Path, name: str | None) -> Path:
    if name:
        p = library_dir / name
        if not p.is_file():
            raise FileNotFoundError(p)
        return p
    found = sorted(library_dir.glob("*.inpx"))
    if len(found) != 1:
        raise FileNotFoundError(
            f"В {library_dir} должен быть ровно один .inpx (найдено: {len(found)}); укажите INPX_FILE")
    return found[0]


def is_stale(inpx_path: Path, db_path: Path) -> bool:
    if not db_path.exists():
        return True
    try:
        con = sqlite3.connect(db_path)
        row = con.execute("SELECT value FROM meta WHERE key='inpx_mtime'").fetchone()
        con.close()
    except sqlite3.Error:
        return True
    return not row or row[0] != str(inpx_path.stat().st_mtime)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m bot.indexer LIBRARY.inpx index.db")
    print("indexed:", build_index(Path(sys.argv[1]), Path(sys.argv[2])))
