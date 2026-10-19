import asyncio
import time
from types import SimpleNamespace

import anthropic
import httpx2 as httpx

from bot.ai_search import AiPlanner, QueryPlan
from bot.indexer import build_index
from bot.library import Library
from tests.test_library import make_collection


def plan(**kw):
    base = dict(author="", title="", series="", lang="", keywords=[], variants=[])
    return QueryPlan(**{**base, **kw})


def make_lib(tmp_path):
    make_collection(tmp_path)
    build_index(tmp_path / "lib.inpx", tmp_path / "idx.db")
    return Library(tmp_path, tmp_path / "idx.db")


def test_structured_plan_fixes_typos_and_translit(tmp_path):
    lib = make_lib(tmp_path)
    # ИИ превратил «strugatsky picnic» в русские поля — сырой текст ничего бы не нашёл
    p = plan(author="Стругацкий", title="Пикник на обочине")
    match, lang = lib.resolve("strugatsky picnic", p)
    books, total = lib.search_match(match, lang)
    assert total == 1 and books[0].title == "Пикник на обочине"
    assert lib.search("strugatsky picnic")[1] == 0


def test_falls_back_to_variants_then_raw(tmp_path):
    lib = make_lib(tmp_path)
    p = plan(author="Несуществующий", title="Ерунда", variants=["Солярис"])
    match, lang = lib.resolve("что-то", p)
    assert lib.search_match(match, lang)[0][0].title == "Солярис"
    # без плана — обычный поиск по тексту
    match, lang = lib.resolve("пикник")
    assert lib.search_match(match, lang)[1] == 1


def test_bad_fts_from_ai_does_not_crash(tmp_path):
    lib = make_lib(tmp_path)
    p = plan(author='"', title="AND OR NEAR(", keywords=["*", "("], variants=["пикник"])
    match, lang = lib.resolve("пикник", p)
    assert lib.search_match(match, lang)[1] == 1


def test_plan_lang_is_soft(tmp_path):
    lib = make_lib(tmp_path)
    # ИИ посчитал язык en, но английского «Пикника» нет — язык отбрасываем, а не возвращаем пусто
    match, lang = lib.resolve("пикник", plan(title="Пикник", lang="en"))
    assert lang == "" and lib.search_match(match, lang)[1] == 1
    # а язык пользователя — жёсткий
    match, lang = lib.resolve("lem", plan(author="Lem"), lang="ru")
    assert lang == "ru" and lib.search_match(match, lang)[1] == 0


class FakeClient:
    def __init__(self, behavior):
        self.messages = SimpleNamespace(parse=behavior)


def run(coro):
    return asyncio.run(coro)


def test_planner_ok():
    async def parse(**kw):
        assert kw["model"] and kw["output_format"] is QueryPlan
        return SimpleNamespace(stop_reason="end_turn", parsed_output=plan(author="Лем"))
    got, err = run(AiPlanner("m", 20, FakeClient(parse)).plan("лем"))
    assert err is None and got.author == "Лем"


def test_planner_timeout_returns_quickly():
    async def parse(**kw):
        await asyncio.sleep(5)
    t = time.monotonic()
    got, err = run(AiPlanner("m", 0.2, FakeClient(parse)).plan("лем"))
    assert got is None and "таймаут" in err and time.monotonic() - t < 1


def test_planner_api_error_and_refusal():
    async def boom(**kw):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))
    assert run(AiPlanner("m", 20, FakeClient(boom)).plan("x")) == (None, "ошибка API")

    async def refuse(**kw):
        return SimpleNamespace(stop_reason="refusal", parsed_output=None)
    assert run(AiPlanner("m", 20, FakeClient(refuse)).plan("x"))[0] is None
