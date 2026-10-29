import asyncio
import threading

import flet as ft
import g4f
from duckduckgo_search import DDGS


APP_NAME = "ASTRO"

# ASTRO Dark Theme
BG = "#0B0D14"
SURFACE = "#121622"
SURFACE_LIGHT = "#1A2030"
ACCENT = "#8B5CF6"
ACCENT_LIGHT = "#A78BFA"
CYAN = "#38BDF8"
WHITE = "#F8FAFC"
MUTED = "#929BB0"
BORDER = "#272D40"
USER_BUBBLE = "#252044"
AI_BUBBLE = "#151B29"

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

    # منطقة المحادثة
    chat = ft.ListView(
        expand=True,
        spacing=16,
        padding=16,
        auto_scroll=True,
    )

    status = ft.Text(
        "● متصل وجاهز",
        size=11,
        color=CYAN,
    )

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
            bgcolor=USER_BUBBLE if is_user else ACCENT,
            alignment=ft.alignment.center,
        )

        bubble = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        sender,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ACCENT_LIGHT if not is_user else CYAN,
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
            bgcolor=USER_BUBBLE if is_user else AI_BUBBLE,
            border=ft.border.all(1, BORDER),
            border_radius=18,
            padding=14,
            width=min((page.width or 420) * 0.78, 520),
        )

        row = ft.Row(
            [avatar, bubble] if not is_user else [bubble, avatar],
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

    def clear_chat(_):
        with messages_lock:
            messages[:] = [
                {"role": "system", "content": SYSTEM_PROMPT}
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

    async def send_message(_=None):
        question = (input_box.value or "").strip()

        if not question:
            return

        input_box.value = ""
        add_bubble("أنت", question, True)

        if is_bad(question):
            add_bubble(
                "ASTRO AI",
                "خلّينا في حاجة مفيدة وآمنة، وأنا أساعدك فيها.",
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
                    border=ft.border.all(1, BORDER),
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

        except Exception:
            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)

            add_bubble(
                "ASTRO AI",
                "مش قادر أوصل لمزوّد الذكاء الاصطناعي دلوقتي.\n"
                "اتأكد من اتصال الإنترنت وحاول تاني بعد شوية.",
            )

            status.value = "● تعذّر الاتصال"

        finally:
            send_button.disabled = False
            input_box.disabled = False
            page.update()

    # مربع الكتابة
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
        content_padding=ft.padding.symmetric(
            horizontal=12,
            vertical=12,
        ),
        on_submit=lambda e: page.run_task(send_message),
    )

    send_button = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD_ROUNDED,
        icon_color=WHITE,
        bgcolor=ACCENT,
        tooltip="إرسال الرسالة",
        on_click=lambda e: page.run_task(send_message),
    )

    # رأس التطبيق
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
        alignment=ft.alignment.center,
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
        padding=ft.padding.symmetric(
            horizontal=16,
            vertical=13,
        ),
        bgcolor=SURFACE,
        border=ft.border.only(
            bottom=ft.BorderSide(1, BORDER),
        ),
    )

    # حالة التطبيق
    status_bar = ft.Container(
        content=status,
        padding=ft.padding.only(
            left=16,
            right=16,
            top=7,
            bottom=7,
        ),
        bgcolor=BG,
    )

    # شريط الكتابة
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
        padding=ft.padding.all(10),
        bgcolor=SURFACE,
        border=ft.border.all(1, BORDER),
        border_radius=22,
        margin=ft.margin.only(
            left=12,
            right=12,
            top=4,
            bottom=10,
        ),
    )

    # التخطيط النهائي
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
    ft.app(target=main)
