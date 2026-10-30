import asyncio
import os
import tempfile
import threading
from pathlib import Path

import flet as ft
import g4f
import g4f.config
from g4f.client import Client
from duckduckgo_search import DDGS


# =========================
# ASTRO CONFIGURATION
# =========================

APP_NAME = "ASTRO"

BG = "#0B0D14"
SURFACE = "#121622"
ACCENT = "#8B5CF6"
ACCENT_LIGHT = "#A78BFA"
CYAN = "#38BDF8"
WHITE = "#F8FAFC"
MUTED = "#929BB0"
BORDER = "#272D40"
USER_BUBBLE = "#252044"
AI_BUBBLE = "#151B29"


# =========================
# G4F CONFIGURATION
# =========================

ASTRO_DATA = Path(tempfile.gettempdir()) / "astro_g4f"
ASTRO_DATA.mkdir(parents=True, exist_ok=True)

G4F_COOKIES = ASTRO_DATA / "cookies"
G4F_COOKIES.mkdir(parents=True, exist_ok=True)

# Configure g4f before creating its client.
g4f.config.CONFIG_DIR = ASTRO_DATA
g4f.config.COOKIES_DIR = G4F_COOKIES

# Also configure the cookie directory through its API.
try:
    from g4f.cookies import set_cookies_dir
    set_cookies_dir(str(G4F_COOKIES))
except (ImportError, AttributeError):
    pass


# =========================
# CHAT CONFIGURATION
# =========================

BAD_WORDS = [
    "هكر",
    "اختراق",
    "hack",
    "سكس",
    "اباحي",
    "إباحي",
    "تهكير",
]

SYSTEM_PROMPT = """
You are ASTRO, a helpful AI assistant.

Reply in the same language as the user.
When the user writes Arabic, use natural Egyptian Arabic.
When the user writes English, use clear, friendly English.
Be honest that you are an AI assistant.
Give useful, accurate, reasonably concise answers.
If web search results are supplied, use them carefully.
If a request is unsafe, redirect toward a safe alternative.
"""

messages = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

messages_lock = threading.Lock()


# =========================
# LANGUAGE AND SAFETY
# =========================

def is_bad(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in BAD_WORDS)


def detect_language(text: str) -> str:
    if any("\u0600" <= char <= "\u06FF" for char in text):
        return "Arabic"
    return "English"


# =========================
# INTERNET SEARCH
# =========================

def search_net(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(
                ddgs.text(query, max_results=3)
            )

        lines = []

        for item in results:
            title = item.get("title", "")
            body = item.get("body", "")
            url = item.get("href", "")

            if body:
                lines.append(
                    f"- {title}\n"
                    f"  {body}\n"
                    f"  {url}"
                )

        return "\n".join(lines)

    except Exception:
        return ""


# =========================
# AI BACKEND
# =========================

def get_ai_reply(question: str):
    search_terms = [
        "who",
        "مين",
        "news",
        "اخبار",
        "أخبار",
        "price",
        "سعر",
        "film",
        "فيلم",
        "امتى",
        "فين",
        "when",
        "where",
        "latest",
        "آخر",
        "اخر",
        "دلوقتي",
        "حاليا",
    ]

    search_data = ""

    if any(
        term in question.lower()
        for term in search_terms
    ):
        search_data = search_net(question)

    final_question = question

    if search_data:
        final_question = (
            f"User question: {question}\n\n"
            f"Internet search results:\n"
            f"{search_data}\n\n"
            f"Answer in {detect_language(question)}."
        )

    with messages_lock:
        messages.append({
            "role": "user",
            "content": final_question,
        })

        try:
            client = Client()

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )

            answer = response.choices[0].message.content

            if not answer:
                raise RuntimeError(
                    "The AI provider returned an empty response."
                )

            answer = str(answer).strip()

            messages[-1] = {
                "role": "user",
                "content": question,
            }

            messages.append({
                "role": "assistant",
                "content": answer,
            })

            if len(messages) > 21:
                messages[:] = (
                    [messages[0]] + messages[-20:]
                )

            return answer, bool(search_data)

        except Exception:
            if (
                messages
                and messages[-1].get("role") == "user"
            ):
                messages.pop()

            raise


# =========================
# USER INTERFACE
# =========================

def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.spacing = 0

    try:
        page.theme = ft.Theme(
            color_scheme_seed=ACCENT,
            use_material3=True,
        )
    except Exception:
        pass

    chat = ft.ListView(
        expand=True,
        spacing=16,
        padding=16,
        auto_scroll=True,
    )

    status = ft.Text(
        "● جاهز",
        size=11,
        color=CYAN,
    )

    # -------------------------
    # CHAT BUBBLES
    # -------------------------

    def add_bubble(
        sender: str,
        content: str,
        is_user: bool = False,
    ):
        avatar = ft.Container(
            content=ft.Icon(
                ft.Icons.PERSON_ROUNDED
                if is_user
                else ft.Icons.AUTO_AWESOME,
                size=18,
                color=WHITE,
            ),
            width=34,
            height=34,
            border_radius=12,
            bgcolor=(
                USER_BUBBLE if is_user else ACCENT
            ),
            alignment=ft.Alignment.CENTER,
        )

        bubble = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        sender,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=(
                            CYAN
                            if is_user
                            else ACCENT_LIGHT
                        ),
                    ),
                    ft.Text(
                        content,
                        size=15,
                        color=WHITE,
                        selectable=True,
                    ),
                ],
                spacing=7,
                tight=True,
            ),
            bgcolor=(
                USER_BUBBLE
                if is_user
                else AI_BUBBLE
            ),
            border=ft.Border.all(1, BORDER),
            border_radius=18,
            padding=14,
            width=min(
                (page.width or 420) * 0.78,
                520,
            ),
        )

        row = ft.Row(
            (
                [bubble, avatar]
                if is_user
                else [avatar, bubble]
            ),
            alignment=(
                ft.MainAxisAlignment.END
                if is_user
                else ft.MainAxisAlignment.START
            ),
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=8,
        )

        chat.controls.append(row)
        page.update()

    # -------------------------
    # NEW CHAT
    # -------------------------

    def clear_chat(_):
        with messages_lock:
            messages[:] = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                }
            ]

        chat.controls.clear()

        add_bubble(
            "ASTRO AI",
            "أهلًا بيك في ASTRO! ✨\n\n"
            "أنا مساعدك الذكي. اسألني عن أي حاجة، "
            "وهحاول أساعدك بأفضل شكل ممكن.",
        )

        status.value = "● محادثة جديدة"
        page.update()

    # -------------------------
    # SEND MESSAGE
    # -------------------------

    async def send_message(_=None):
        question = (input_box.value or "").strip()

        if not question:
            return

        input_box.value = ""
        add_bubble("أنت", question, True)

        if is_bad(question):
            add_bubble(
                "ASTRO AI",
                "خلّينا في حاجة مفيدة وآمنة، "
                "وأنا أساعدك فيها.",
            )

            status.value = "● جاهز"
            page.update()
            return

        send_button.disabled = True
        input_box.disabled = True
        status.value = "● ASTRO بيفكر..."

        waiting_row = ft.Row(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.AUTO_AWESOME,
                                color=ACCENT_LIGHT,
                                size=18,
                            ),
                            ft.Text(
                                "جاري التفكير...",
                                color=MUTED,
                                size=14,
                            ),
                        ],
                        spacing=9,
                    ),
                    bgcolor=AI_BUBBLE,
                    border=ft.Border.all(1, BORDER),
                    border_radius=16,
                    padding=14,
                )
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        chat.controls.append(waiting_row)
        page.update()

        try:
            answer, searched = await asyncio.to_thread(
                get_ai_reply,
                question,
            )

            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)

            add_bubble("ASTRO AI", answer)

            status.value = (
                "● تم البحث على الإنترنت"
                if searched
                else "● جاهز"
            )

        except Exception as error:
            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)

            error_details = (
                f"{type(error).__name__}: {error}"
            )

            add_bubble(
                "ASTRO AI",
                "حصل خطأ أثناء الاتصال بمزوّد الذكاء الاصطناعي.\n\n"
                f"تفاصيل الخطأ:\n{error_details}\n\n"
                "اتأكد من الإنترنت وحاول تاني.",
            )

            status.value = "● تعذّر الاتصال"

        finally:
            send_button.disabled = False
            input_box.disabled = False
            page.update()

    # -------------------------
    # MESSAGE INPUT
    # -------------------------

    input_box = ft.TextField(
        hint_text="اكتب رسالتك هنا...",
        multiline=True,
        min_lines=1,
        max_lines=4,
        expand=True,
        border=ft.InputBorder.NONE,
        text_size=15,
        color=WHITE,
        cursor_color=ACCENT_LIGHT,
        hint_style=ft.TextStyle(color=MUTED),
        content_padding=ft.Padding(
            left=12,
            top=12,
            right=12,
            bottom=12,
        ),
        on_submit=lambda e: page.run_task(
            send_message,
            e,
        ),
    )

    send_button = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD_ROUNDED,
        icon_color=WHITE,
        bgcolor=ACCENT,
        tooltip="إرسال الرسالة",
        on_click=lambda e: page.run_task(
            send_message,
            e,
        ),
    )

    # -------------------------
    # HEADER
    # -------------------------

    logo = ft.Container(
        content=ft.Icon(
            ft.Icons.AUTO_AWESOME,
            size=27,
            color=WHITE,
        ),
        width=48,
        height=48,
        bgcolor=ACCENT,
        border_radius=16,
        alignment=ft.Alignment.CENTER,
    )

    header = ft.Container(
        content=ft.Row(
            [
                logo,
                ft.Column(
                    [
                        ft.Text(
                            "ASTRO",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=WHITE,
                        ),
                        ft.Text(
                            "YOUR AI COMPANION",
                            size=10,
                            color=ACCENT_LIGHT,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                    icon_color=ACCENT_LIGHT,
                    icon_size=26,
                    tooltip="محادثة جديدة",
                    on_click=clear_chat,
                ),
            ],
            spacing=12,
        ),
        padding=ft.Padding(
            left=16,
            top=13,
            right=16,
            bottom=13,
        ),
        bgcolor=SURFACE,
        border=ft.Border.only(
            bottom=ft.BorderSide(1, BORDER),
        ),
    )

    # -------------------------
    # STATUS BAR
    # -------------------------

    status_bar = ft.Container(
        content=status,
        padding=ft.Padding(
            left=16,
            top=7,
            right=16,
            bottom=7,
        ),
        bgcolor=BG,
    )

    # -------------------------
    # MESSAGE COMPOSER
    # -------------------------

    composer = ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=input_box,
                    expand=True,
                ),
                send_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.END,
            spacing=8,
        ),
        padding=10,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=22,
        margin=ft.Margin(
            left=12,
            top=4,
            right=12,
            bottom=10,
        ),
    )

    # -------------------------
    # PAGE LAYOUT
    # -------------------------

    page.add(
        ft.Column(
            [
                header,
                ft.Container(
                    content=chat,
                    expand=True,
                    bgcolor=BG,
                ),
                status_bar,
                composer,
            ],
            expand=True,
            spacing=0,
        )
    )

    add_bubble(
        "ASTRO AI",
        "أهلًا بيك في ASTRO! ✨\n\n"
        "أنا مساعدك الذكي. اسألني عن أي حاجة، "
        "وهحاول أساعدك بأفضل شكل ممكن.",
    )

    page.update()


if __name__ == "__main__":
    ft.run(main)
