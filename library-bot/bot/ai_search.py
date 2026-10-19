"""Разбор поискового запроса через Claude: свободный текст -> структура для FTS.

Любая ошибка (таймаут, сеть, отказ, невалидный ответ) -> plan() возвращает None,
и бот ищет по исходному тексту без ИИ.
"""
from __future__ import annotations

import asyncio
import logging

import anthropic
from pydantic import BaseModel

log = logging.getLogger("library-bot.ai")

SYSTEM = """\
Ты разбираешь поисковые запросы к личной библиотеке книг (в основном русскоязычной, есть иностранные книги).
Пользователь пишет по-человечески: с опечатками, падежами, латиницей, не помня точного названия.
Верни структуру для полнотекстового поиска по полям автор / название / серия.

Правила:
- author: фамилия (и имя, если дано) автора в именительном падеже, как её пишут в каталоге.
  Латиницу переводи в привычное русское написание («Strugatsky» -> «Стругацкий»), если автор издавался по-русски.
  Для иностранных авторов в англоязычных книгах оставь латиницу.
- title: название книги, если оно названо или угадывается. Исправь опечатки. Не придумывай то, чего пользователь не называл.
- series: только если пользователь явно назвал серию или цикл.
- lang: код языка книги (ru, en, ...) ТОЛЬКО если пользователь прямо просит книгу на конкретном языке, иначе пустая строка.
- keywords: значимые слова, которые не вошли в author/title/series (тема, герой). Без служебных слов.
- variants: до 3 альтернативных коротких запросов (другое написание имени/названия, оригинальное название,
  транслитерация), по которым книга могла бы найтись, если основной разбор промахнётся.
Неизвестные поля оставляй пустой строкой или пустым списком. Не добавляй ничего от себя."""


class QueryPlan(BaseModel):
    author: str
    title: str
    series: str
    lang: str
    keywords: list[str]
    variants: list[str]


class AiPlanner:
    def __init__(self, model: str, timeout: float, client: anthropic.AsyncAnthropic | None = None):
        self.model = model
        self.timeout = timeout
        # max_retries=0: SDK повторяет таймауты, и реальное ожидание стало бы timeout*(retries+1)
        self.client = client or anthropic.AsyncAnthropic(timeout=timeout, max_retries=0)

    async def plan(self, text: str) -> tuple[QueryPlan | None, str | None]:
        """Возвращает (план, None) либо (None, причина_сбоя)."""
        try:
            resp = await asyncio.wait_for(
                self.client.messages.parse(
                    model=self.model,
                    max_tokens=2000,
                    system=SYSTEM,
                    output_config={"effort": "low"},
                    messages=[{"role": "user", "content": text}],
                    output_format=QueryPlan,
                ),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, anthropic.APITimeoutError):
            return None, f"таймаут {self.timeout:g} с"
        except anthropic.APIError as e:
            log.warning("AI search failed: %s", e)
            return None, "ошибка API"
        except Exception:  # noqa: BLE001 — поиск не должен падать из-за ИИ
            log.exception("AI search failed")
            return None, "ошибка"
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            return None, "ИИ не разобрал запрос"
        return resp.parsed_output, None
