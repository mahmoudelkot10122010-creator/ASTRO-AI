import asyncio
import threading

import flet as ft
import g4f
from duckduckgo_search import DDGS
from langdetect import detect

APP_NAME = "ASTRO"
BAD_WORDS = ["هكر", "اختراق", "hack", "سكس", "اباحي", "شتم", "تهكير"]

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
    try:
        lang = detect(question)
    except Exception:
        lang = "ar"

    search_data = ""
    search_terms = [
        "who", "مين", "news", "اخبار", "أخبار", "price", "سعر",
        "film", "فيلم", "امتى", "فين", "when", "where", "latest",
    ]
    if any(term in question.lower() for term in search_terms):
        search_data = search_net(question)

    final_question = question
    if search_data:
        final_question = (
            f"User question: {question}\n"
            f"Web search results (may be incomplete):\n{search_data}\n"
            f"Reply in the user's language ({lang}) as ASTRO."
        )

    with messages_lock:
        messages.append({"role": "user", "content": final_question})
        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4o_mini,
                messages=messages,
            )
            answer = str(response)
            messages[-1] = {"role": "user", "content": question}
            messages.append({"role": "assistant", "content": answer})
            if len(messages) > 21:
                messages[:] = [messages[0]] + messages[-20:]
            return answer, bool(search_data)
        except Exception:
            if messages and messages[-1].get("role") == "user":
                messages.pop()
            raise


def main(page: ft.Page):
    # A restrained, familiar mobile-app palette: off-white, white, charcoal, muted green.
    bg = "#F4F5F3"
    white = "#FFFFFF"
    text = "#242824"
    muted = "#737A73"
    line = "#E1E5E0"
    accent = "#397A63"
    user_bubble = "#E1EEE7"
    assistant_bubble = "#FFFFFF"

    page.title = "ASTRO"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = bg
    page.padding = 0
    page.spacing = 0

    chat = ft.ListView(expand=True, spacing=12, padding=16, auto_scroll=True)
    status = ft.Text("جاهز", size=12, color=muted)

    def add_bubble(sender: str, content: str, is_user: bool = False):
        bubble = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        sender,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=accent if not is_user else "#315A49",
                    ),
                    ft.Text(content, size=15, color=text, selectable=True),
                ],
                spacing=5,
                tight=True,
            ),
            bgcolor=user_bubble if is_user else assistant_bubble,
            border=ft.border.all(1, line),
            border_radius=12,
            padding=12,
            width=min((page.width or 420) * 0.86, 520),
        )
        chat.controls.append(
            ft.Row(
                [bubble],
                alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            )
        )
        page.update()

    def clear_chat(_):
        with messages_lock:
            messages[:] = [{"role": "system", "content": SYSTEM_PROMPT}]
        chat.controls.clear()
        add_bubble("ASTRO", "أهلًا! أنا ASTRO. تحب تسأل عن إيه؟")
        status.value = "محادثة جديدة"
        page.update()

    async def send_message(_=None):
        question = (input_box.value or "").strip()
        if not question:
            return

        input_box.value = ""
        add_bubble("أنت", question, True)

        if is_bad(question):
            add_bubble("ASTRO", "خلّينا في حاجة مفيدة وآمنة، وأنا أساعدك فيها.")
            status.value = "جاهز"
            page.update()
            return

        send_button.disabled = True
        input_box.disabled = True
        status.value = "ASTRO بيجهّز الرد..."
        waiting_row = ft.Row(
            [
                ft.Container(
                    content=ft.Text("جاري التفكير...", color=muted, size=14),
                    bgcolor=assistant_bubble,
                    border=ft.border.all(1, line),
                    border_radius=12,
                    padding=12,
                )
            ],
            alignment=ft.MainAxisAlignment.START,
        )
        chat.controls.append(waiting_row)
        page.update()

        try:
            answer, searched = await asyncio.to_thread(get_ai_reply, question)
            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)
            add_bubble("ASTRO", answer)
            status.value = "تم البحث على الإنترنت" if searched else "جاهز"
        except Exception:
            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)
            add_bubble(
                "ASTRO",
                "مش قادر أوصل لمزوّد الذكاء الاصطناعي دلوقتي. جرّب تاني بعد شوية.",
            )
            status.value = "تعذّر الاتصال"
        finally:
            send_button.disabled = False
            input_box.disabled = False
            input_box.focus()
            page.update()

    input_box = ft.TextField(
        hint_text="اكتب رسالتك...",
        multiline=True,
        min_lines=1,
        max_lines=4,
        expand=True,
        border=ft.InputBorder.NONE,
        text_size=15,
        color=text,
        hint_style=ft.TextStyle(color=muted),
        content_padding=ft.padding.symmetric(horizontal=12, vertical=12),
        on_submit=lambda e: page.run_task(send_message),
    )

    send_button = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD,
        icon_color=white,
        bgcolor=accent,
        tooltip="إرسال",
        on_click=lambda e: page.run_task(send_message),
    )

    header = ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Text("A", size=22, weight=ft.FontWeight.BOLD, color=white),
                    width=42,
                    height=42,
                    bgcolor=accent,
                    border_radius=10,
                    alignment=ft.alignment.center,
                ),
                ft.Column(
                    [
                        ft.Text("ASTRO", size=20, weight=ft.FontWeight.BOLD, color=text),
                        ft.Text("مساعدك الذكي", size=12, color=muted),
                    ],
                    spacing=1,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    icon_color=text,
                    tooltip="محادثة جديدة",
                    on_click=clear_chat,
                ),
            ],
            spacing=11,
        ),
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        bgcolor=white,
        border=ft.border.only(bottom=ft.BorderSide(1, line)),
    )

    composer = ft.Container(
        content=ft.Row(
            [input_box, send_button],
            vertical_alignment=ft.CrossAxisAlignment.END,
            spacing=6,
        ),
        padding=ft.padding.all(10),
        bgcolor=white,
        border=ft.border.only(top=ft.BorderSide(1, line)),
    )

    page.add(
        ft.Column(
            [
                header,
                ft.Container(content=chat, expand=True, bgcolor=bg),
                ft.Container(
                    content=status,
                    padding=ft.padding.only(left=16, top=5, bottom=5),
                    bgcolor=bg,
                ),
                composer,
            ],
            expand=True,
            spacing=0,
        )
    )
    add_bubble("ASTRO", "أهلًا! أنا ASTRO. اسألني اللي تحب تعرفه.")
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
