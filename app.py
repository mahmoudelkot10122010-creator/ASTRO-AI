import asyncio
import threading

import flet as ft
import g4f
from duckduckgo_search import DDGS

APP_NAME = "ASTRO"

BAD_WORDS = [
    "هكر", "اختراق", "hack", "سكس", "اباحي", "شتم", "تهكير"
]

SYSTEM_PROMPT = """
You are ASTRO, a helpful AI assistant with a friendly Egyptian Arabic style.
Reply in the same language as the user. If the user writes Arabic, use natural Egyptian Arabic.
If the user writes English, use casual but clear English.
You are an AI assistant named ASTRO. Be honest about being AI.
If asked for harmful or inappropriate help, politely redirect to safe alternatives.
Keep answers clear and reasonably concise. Use supplied web results carefully.
"""

messages = [{"role": "system", "content": SYSTEM_PROMPT}]
messages_lock = threading.Lock()


def is_bad(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in BAD_WORDS)


def detect_language(text: str) -> str:
    """Detect Arabic text without requiring an external library."""
    if any("\u0600" <= char <= "\u06FF" for char in text):
        return "ar"
    return "en"


def search_net(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))

            return "\n".join(
                f"- {item.get('title', '')}: {item.get('body', '')}"
                for item in results
                if item.get("body")
            )
    except Exception:
        return ""


def get_ai_reply(question: str):
    lang = detect_language(question)

    search_data = ""

    search_terms = [
        "who", "مين", "news", "اخبار", "أخبار",
        "price", "سعر", "film", "فيلم", "امتى",
        "فين", "when", "where", "latest",
    ]

    lowered_question = question.lower()

    if any(term in lowered_question for term in search_terms):
        search_data = search_net(question)

    final_question = question

    if search_data:
        final_question = (
            f"User question: {question}\n"
            f"Web search results (may be incomplete):\n"
            f"{search_data}\n"
            f"Reply in the user's language ({lang}) as ASTRO."
        )

    with messages_lock:
        messages.append({
            "role": "user",
            "content": final_question,
        })

        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4o_mini,
                messages=messages,
            )

            answer = str(response)

            messages[-1] = {
                "role": "user",
                "content": question,
            }

            messages.append({
                "role": "assistant",
                "content": answer,
            })

            if len(messages) > 21:
                messages[:] = [messages[0]] + messages[-20:]

            return answer, bool(search_data)

        except Exception:
            if messages and messages[-1].get("role") == "user":
                messages.pop()

            raise


def main(page: ft.Page):
    bg = "#F4F5F3"
    white = "#FFFFFF"
    text = "#242824"
    muted = "#737A73"
    line = "#E1E5E0"
    accent = "#397A63"
    user_bubble = "#E1EEE7"
    assistant_bubble = "#FFFFFF"

    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bg
