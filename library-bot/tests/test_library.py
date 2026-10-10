import zipfile
from pathlib import Path

from bot.indexer import build_index, is_stale
from bot.library import Library

SEP = "\x04"


def make_collection(d: Path):
    def row(author, genre, title, series, serno, file, size, libid, dele, ext, date, lang):
        return SEP.join([author, genre, title, series, serno, file, str(size), libid, dele, ext, date, lang, "0", ""]) + SEP + "\r\n"

    inp = (
        row("Стругацкий,Аркадий,Натанович:Стругацкий,Борис,Натанович:", "sf:", "Пикник на обочине", "", "0", "100", 10, "1", "0", "fb2", "2020-01-01", "ru")
        + row("Лем,Станислав,:", "sf:", "Солярис", "", "0", "101", 10, "2", "0", "fb2", "2020-01-01", "ru")
        + row("Удалённый,Автор,:", "sf:", "Удалённая книга", "", "0", "102", 10, "3", "1", "fb2", "2020-01-01", "ru")
        + row("Lem,Stanislaw,:", "sf:", "Solaris", "", "0", "103", 10, "4", "0", "fb2", "2020-01-01", "en")
    )
    with zipfile.ZipFile(d / "lib.inpx", "w") as z:
        z.writestr("collection.info", "test")
        z.writestr("fb2-000100-000103.inp", inp.encode())
    with zipfile.ZipFile(d / "fb2-000100-000103.zip", "w") as z:
        z.writestr("100.fb2", b"<fb2>picnic</fb2>")


def test_index_search_read(tmp_path):
    make_collection(tmp_path)
    db = tmp_path / "idx.db"
    assert is_stale(tmp_path / "lib.inpx", db)
    assert build_index(tmp_path / "lib.inpx", db) == 3  # DEL=1 пропущена
    assert not is_stale(tmp_path / "lib.inpx", db)

    lib = Library(tmp_path, db)
    books, total = lib.search("стругацкие пикник")
    assert total == 1 and books[0].title == "Пикник на обочине"
    assert books[0].authors == "Аркадий Стругацкий, Борис Стругацкий"
    assert lib.search("СОЛЯР")[1] == 1               # регистр + префикс
    assert lib.search("lem")[1] == 1 and lib.search("lem", lang="ru")[1] == 0  # фильтр языка
    assert lib.search("удалённая")[1] == 0
    assert lib.search("!!!")[1] == 0                 # мусорный запрос не падает
    assert lib.search('" OR ""')[1] == 0             # спецсимволы FTS экранированы

    assert lib.read(books[0]) == b"<fb2>picnic</fb2>"
    assert books[0].filename == "Аркадий Стругацкий - Пикник на обочине.fb2"
