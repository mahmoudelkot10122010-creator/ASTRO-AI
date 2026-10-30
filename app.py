import asyncio
import json
import threading
import urllib.request
import urllib.error

import flet as ft
from duckduckgo_search import DDGS

APP_NAME = "ASTRO"

# =========================
# ASTRO THEME
# =========================

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

messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
            results = list(ddgs.text(query, max_results=3))

        lines = []
        for item in results:
            title = item.get("title", "")
            body = item.get("body", "")
            url = item.get("href", "")
            if body:
                lines.append(f"- {title}\n  {body}\n  {url}")

        return "\n".join(lines)
    except Exception:
        return ""


# =========================
# FREE THE AI BACKEND
# =========================

def get_ai_reply(question: str, api_key: str):
    api_key = (api_key or "").strip()
    if not api_key:
        raise RuntimeError("اكتب مفتاح FreeTheAI في خانة مفتاح API أولًا.")

    search_terms = [
        "who", "مين", "news", "اخبار", "أخبار", "price", "سعر",
        "film", "فيلم", "امتى", "فين", "when", "where", "latest",
        "آخر", "اخر", "دلوقتي", "حاليا",
    ]

    search_data = ""
    if any(term in question.lower() for term in search_terms):
        search_data = search_net(question)

    final_question = question
    if search_data:
        final_question = (
            f"User question: {question}\n\n"
            f"Internet search results:\n{search_data}\n\n"
            f"Answer in {detect_language(question)}."
        )

    with messages_lock:
        request_messages = messages + [
            {"role": "user", "content": final_question}
        ]

        payload = json.dumps({
            "model": "fta/zai/glm-5.3",
            "messages": request_messages,
        }).encode("utf-8")

        request = urllib.request.Request(
            "https://api.freetheai.org/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))

            answer = data["choices"][0]["message"]["content"]
            if not answer:
                raise RuntimeError("المزوّد أرسل ردًا فارغًا.")

            answer = str(answer).strip()

            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": answer})

            if len(messages) > 21:
                messages[:] = [messages[0]] + messages[-20:]

            return answer, bool(search_data)

        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"FreeTheAI HTTP {error.code}: {details}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                f"تعذّر الاتصال بالإنترنت: {error.reason}"
            ) from error
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "استجابة غير متوقعة من FreeTheAI."
            ) from error


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

    status = ft.Text("● جاهز", size=11, color=CYAN)

    # The key is held only in this screen's memory, not saved in GitHub.
    api_key_box = ft.TextField(
        label="مفتاح FreeTheAI API",
        hint_text="الصق المفتاح الذي يبدأ بـ ftai_ هنا",
        password=True,
        can_reveal_password=True,
        dense=True,
        text_size=13,
        color=WHITE,
        cursor_color=ACCENT_LIGHT,
        border_color=BORDER,
        focused_border_color=ACCENT,
        bgcolor=SURFACE,
        content_padding=12,
    )

    # -------------------------
    # CHAT BUBBLES
    # -------------------------

    def add_bubble(sender: str, content: str, is_user: bool = False):
        avatar = ft.Container(
            content=ft.Icon(
                ft.Icons.PERSON_ROUNDED if is_user else ft.Icons.AUTO_AWESOME,
                size=18,
                color=WHITE,
            ),
            width=34,
            height=34,
            border_radius=12,
            bgcolor=USER_BUBBLE if is_user else ACCENT,
            alignment=ft.Alignment.CENTER,
        )

        bubble = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        sender,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=CYAN if is_user else ACCENT_LIGHT,
                    ),
                    ft.Text(content, size=15, color=WHITE, selectable=True),
                ],
                spacing=7,
                tight=True,
            ),
            bgcolor=USER_BUBBLE if is_user else AI_BUBBLE,
            border=ft.Border.all(1, BORDER),
            border_radius=18,
            padding=14,
            width=min((page.width or 420) * 0.78, 520),
        )

        row = ft.Row(
            [bubble, avatar] if is_user else [avatar, bubble],
            alignment=(
                ft.MainAxisAlignment.END if is_user
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
            messages[:] = [{"role": "system", "content": SYSTEM_PROMPT}]

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

        api_key = (api_key_box.value or "").strip()
        if not api_key:
            status.value = "● أدخل مفتاح FreeTheAI أولًا"
            page.update()
            add_bubble(
                "ASTRO AI",
                "اكتب مفتاح FreeTheAI في خانة «مفتاح FreeTheAI API» قبل إرسال سؤالك.",
            )
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
                            ft.Text("جاري التفكير...", color=MUTED, size=14),
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
                api_key,
            )

            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)

            add_bubble("ASTRO AI", answer)
            status.value = "● تم البحث على الإنترنت" if searched else "● جاهز"

        except Exception as error:
            if waiting_row in chat.controls:
                chat.controls.remove(waiting_row)

            error_details = f"{type(error).__name__}: {error}"
            add_bubble(
                "ASTRO AI",
                "حصل خطأ أثناء الاتصال بمزوّد الذكاء الاصطناعي.\n\n"
                f"تفاصيل الخطأ:\n{error_details}\n\n"
                "تأكد من الإنترنت ومن صلاحية المفتاح، "
                "وتأكد من تنفيذ Daily check-in في موقع FreeTheAI.",
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
        content_padding=ft.Padding(left=12, top=12, right=12, bottom=12),
        on_submit=lambda e: page.run_task(send_message, e),
    )

    send_button = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD_ROUNDED,
        icon_color=WHITE,
        bgcolor=ACCENT,
        tooltip="إرسال الرسالة",
        on_click=lambda e: page.run_task(send_message, e),
    )

    # -------------------------
    # HEADER
    # -------------------------

    logo = ft.Container(
        content=ft.Icon(ft.Icons.AUTO_AWESOME, size=27, color=WHITE),
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
                        ft.Text("ASTRO", size=22, weight=ft.FontWeight.BOLD, color=WHITE),
                        ft.Text("YOUR AI COMPANION", size=10, color=ACCENT_LIGHT),
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
        padding=ft.Padding(left=16, top=13, right=16, bottom=13),
        bgcolor=SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
    )

    # -------------------------
    # STATUS BAR
    # -------------------------

    status_bar = ft.Container(
        content=status,
        padding=ft.Padding(left=16, top=7, right=16, bottom=7),
        bgcolor=BG,
    )

    # -------------------------
    # MESSAGE COMPOSER
    # -------------------------

    composer = ft.Container(
        content=ft.Row(
            [
                ft.Container(content=input_box, expand=True),
                send_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.END,
            spacing=8,
        ),
        padding=10,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=22,
        margin=ft.Margin(left=12, top=4, right=12, bottom=10),
    )

    # -------------------------
    # PAGE LAYOUT
    # -------------------------

    page.add(
        ft.Column(
            [
                header,
                ft.Container(content=chat, expand=True, bgcolor=BG),
                status_bar,
                ft.Container(
                    content=ft.Column(
                        [
                            api_key_box,
                            composer,
                            ft.Text(
                                "مفتاح API لا يُحفظ في GitHub، لكنه مطلوب مجددًا عند إعادة فتح التطبيق.",
                                size=10,
                                color=MUTED,
                            ),
                        ],
                        spacing=4,
                    ),
                    padding=ft.Padding(left=12, right=12, top=4, bottom=4),
                ),
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


# =========================
# APP ENTRY POINT
# =========================

if __name__ == "__main__":
    ft.run(main)
