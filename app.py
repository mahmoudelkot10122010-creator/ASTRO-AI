import asyncio
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import flet as ft
from duckduckgo_search import DDGS

APP_NAME = "ASTRO"
WORKER_CHAT_URL = "https://hidden-bush-561c.mahmoud-elkot10122010.workers.dev/chat"
PRIMARY_MODEL = "fta/zzz/deepseek-chat"
FALLBACK_MODELS = ["fta/meow/gpt-4.1-mini", "fta/meow/gpt-4.1-nano"]
DAILY_MESSAGE_LIMIT = 50
USAGE_FILE = Path.home() / ".astro_daily_usage.json"
usage_lock = threading.Lock()

BG, SURFACE, ACCENT, ACCENT_LIGHT = "#0B0D14", "#121622", "#8B5CF6", "#A78BFA"
CYAN, WHITE, MUTED, BORDER = "#38BDF8", "#F8FAFC", "#929BB0", "#272D40"
USER_BUBBLE, AI_BUBBLE = "#252044", "#151B29"

BAD_WORDS = ["هكر", "اختراق", "hack", "سكس", "اباحي", "إباحي", "تهكير"]
SYSTEM_PROMPT = """
You are ASTRO, a helpful AI assistant.
Your developers are Mahmoud Abdelhalim (محمود عبدالحليم) and Omar Sharaf El-Din (عمر شرف الدين).
If asked who created ASTRO, say it was developed by Mahmoud Abdelhalim and Omar Sharaf El-Din. Do not claim they created the underlying AI model.
Reply in the user's language. Use natural Egyptian Arabic for Arabic and clear friendly English for English.
Be honest that you are an AI assistant, useful, accurate, and reasonably concise.
Use supplied search results carefully. If a request is unsafe, redirect toward a safe alternative.
""".strip()
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
messages_lock = threading.Lock()


def is_bad(text):
    low = text.lower()
    return any(word in low for word in BAD_WORDS)


def detect_language(text):
    return "Arabic" if any("\u0600" <= c <= "\u06ff" for c in text) else "English"


def search_net(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        return "\n".join(
            f"- {x.get('title','')}\n  {x.get('body','')}\n  {x.get('href','')}"
            for x in results if x.get("body")
        )
    except Exception:
        return ""


def read_usage():
    today = date.today().isoformat()
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        if data.get("date") != today:
            return {"date": today, "count": 0}
        return {"date": today, "count": max(0, int(data.get("count", 0)))}
    except (OSError, ValueError, TypeError):
        return {"date": today, "count": 0}


def get_usage_count():
    with usage_lock:
        return read_usage()["count"]


def can_send_daily_message():
    # Check the limit without consuming a message before the server responds.
    with usage_lock:
        count = read_usage()["count"]
        return count < DAILY_MESSAGE_LIMIT, count


def record_successful_message():
    # Count only successful AI responses, not failed connection attempts.
    with usage_lock:
        data = read_usage()
        if data["count"] >= DAILY_MESSAGE_LIMIT:
            return data["count"]
        data["count"] += 1
        try:
            USAGE_FILE.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            # Keep the app usable if local usage storage is unavailable.
            return data["count"] - 1
        return data["count"]


def request_model(model, request_messages):
    body = json.dumps({"model": model, "messages": request_messages}).encode("utf-8")
    req = urllib.request.Request(
        WORKER_CHAT_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "ASTRO-AI/1.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"السيرفر رجّع HTTP {error.code}: {details[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError("تعذّر الاتصال بسيرفر ASTRO. تأكد من الإنترنت.") from error
    try:
        data = json.loads(raw)
        answer = data["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        try:
            detail = json.loads(raw).get("error", raw)
        except Exception:
            detail = raw
        raise RuntimeError(f"استجابة غير متوقعة: {str(detail)[:500]}") from error
    if not answer or not str(answer).strip():
        raise RuntimeError("المزوّد أرسل ردًا فارغًا.")
    return str(answer).strip()


def get_ai_reply(question):
    search_terms = ["who", "مين", "news", "اخبار", "أخبار", "price", "سعر",
                    "film", "فيلم", "امتى", "فين", "when", "where", "latest",
                    "آخر", "اخر", "دلوقتي", "حاليا"]
    search_data = search_net(question) if any(t in question.lower() for t in search_terms) else ""
    final_question = question
    if search_data:
        final_question = (f"User question: {question}\n\nInternet search results:\n"
                          f"{search_data}\n\nAnswer in {detect_language(question)}.")
    with messages_lock:
        request_messages = messages + [{"role": "user", "content": final_question}]
        errors = []
        for index, model in enumerate([PRIMARY_MODEL, *FALLBACK_MODELS]):
            attempts = 2 if index == 0 else 1
            for attempt in range(attempts):
                try:
                    answer = request_model(model, request_messages)
                    messages.extend([{"role": "user", "content": question},
                                     {"role": "assistant", "content": answer}])
                    if len(messages) > 21:
                        messages[:] = [messages[0]] + messages[-20:]
                    return answer, bool(search_data)
                except RuntimeError as error:
                    detail = str(error)
                    errors.append(f"{model}: {detail}")
                    if not any(code in detail for code in ("HTTP 502", "HTTP 503", "HTTP 504")):
                        raise
                    if attempt < attempts - 1:
                        time.sleep(2)
        raise RuntimeError("كل الموديلات فشلت:\n" + "\n".join(errors[-3:]))


def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.spacing = 0
    try:
        page.theme = ft.Theme(color_scheme_seed=ACCENT, use_material3=True)
    except Exception:
        pass

    chat = ft.ListView(expand=True, spacing=16, padding=16, auto_scroll=True)
    status = ft.Text("● جاهز", size=11, color=CYAN)
    quota = ft.Text("", size=11, color=MUTED)

    def update_quota():
        quota.value = f"المتبقي اليوم: {max(0, DAILY_MESSAGE_LIMIT - get_usage_count())} من {DAILY_MESSAGE_LIMIT}"
        page.update()

    def add_bubble(sender, content, is_user=False):
        avatar = ft.Container(
            content=ft.Icon(ft.Icons.PERSON_ROUNDED if is_user else ft.Icons.AUTO_AWESOME,
                            size=18, color=WHITE),
            width=34, height=34, border_radius=12,
            bgcolor=USER_BUBBLE if is_user else ACCENT, alignment=ft.Alignment.CENTER)
        bubble = ft.Container(
            content=ft.Column([
                ft.Text(sender, size=12, weight=ft.FontWeight.BOLD,
                        color=CYAN if is_user else ACCENT_LIGHT),
                ft.Text(content, size=15, color=WHITE, selectable=True),
            ], spacing=7, tight=True),
            bgcolor=USER_BUBBLE if is_user else AI_BUBBLE,
            border=ft.Border.all(1, BORDER), border_radius=18, padding=14,
            width=min((page.width or 420) * 0.78, 520))
        chat.controls.append(ft.Row(
            [bubble, avatar] if is_user else [avatar, bubble],
            alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START, spacing=8))
        page.update()

    def clear_chat(_):
        with messages_lock:
            messages[:] = [{"role": "system", "content": SYSTEM_PROMPT}]
        chat.controls.clear()
        add_bubble("ASTRO AI", "أهلًا بيك في ASTRO! ✨\n\nأنا مساعدك الذكي. اسألني عن أي حاجة.")
        status.value = "● محادثة جديدة"
        page.update()

    async def send_message(_=None):
        question = (input_box.value or "").strip()
        if not question:
            return
        input_box.value = ""
        add_bubble("أنت", question, True)
        if is_bad(question):
            add_bubble("ASTRO AI", "خلّينا في حاجة مفيدة وآمنة، وأنا أساعدك فيها.")
            status.value = "● جاهز"
            page.update()
            return

        allowed, _used = can_send_daily_message()
        update_quota()
        if not allowed:
            status.value = "● وصلت للحد اليومي"
            add_bubble("ASTRO AI", "استخدمت حد الـ50 رسالة المجانية لليوم. جرّب تاني بكرة.")
            return

        send_button.disabled = True
        input_box.disabled = True
        status.value = "● ASTRO بيفكر..."
        waiting = ft.Row([ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=ACCENT_LIGHT, size=18),
                            ft.Text("جاري التفكير...", color=MUTED, size=14)], spacing=9),
            bgcolor=AI_BUBBLE, border=ft.Border.all(1, BORDER),
            border_radius=16, padding=14)], alignment=ft.MainAxisAlignment.START)
        chat.controls.append(waiting)
        page.update()
        try:
            answer, searched = await asyncio.to_thread(get_ai_reply, question)
            record_successful_message()
            if waiting in chat.controls:
                chat.controls.remove(waiting)
            add_bubble("ASTRO AI", answer)
            status.value = "● تم البحث على الإنترنت" if searched else "● جاهز"
        except Exception as error:
            if waiting in chat.controls:
                chat.controls.remove(waiting)
            add_bubble("ASTRO AI",
                "حصل خطأ أثناء الاتصال.\n\n"
                f"التفاصيل: {str(error)[:700]}\n\n"
                "لو ظهر HTTP 403، فممكن مزوّد الذكاء الاصطناعي بيرفض الطلب المار عبر Cloudflare Worker.")
            status.value = "● تعذّر الاتصال"
        finally:
            send_button.disabled = False
            input_box.disabled = False
            update_quota()
            page.update()

    input_box = ft.TextField(
        hint_text="اكتب رسالتك هنا...", multiline=True, min_lines=1, max_lines=4,
        expand=True, border=ft.InputBorder.NONE, text_size=15, color=WHITE,
        cursor_color=ACCENT_LIGHT, hint_style=ft.TextStyle(color=MUTED),
        content_padding=ft.Padding(left=12, top=12, right=12, bottom=12),
        on_submit=lambda e: page.run_task(send_message, e))
    send_button = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD_ROUNDED, icon_color=WHITE, bgcolor=ACCENT,
        tooltip="إرسال الرسالة", on_click=lambda e: page.run_task(send_message, e))
    logo = ft.Container(content=ft.Icon(ft.Icons.AUTO_AWESOME, size=27, color=WHITE),
                        width=48, height=48, bgcolor=ACCENT, border_radius=16,
                        alignment=ft.Alignment.CENTER)
    header = ft.Container(content=ft.Row([
        logo,
        ft.Column([ft.Text("ASTRO", size=22, weight=ft.FontWeight.BOLD, color=WHITE),
                   ft.Text("YOUR AI COMPANION", size=10, color=ACCENT_LIGHT)],
                  spacing=2, expand=True),
        ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                      icon_color=ACCENT_LIGHT, icon_size=26, tooltip="محادثة جديدة",
                      on_click=clear_chat)
    ], spacing=12), padding=ft.Padding(left=16, top=13, right=16, bottom=13),
        bgcolor=SURFACE, border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)))
    status_bar = ft.Container(content=ft.Row([status, quota], spacing=12),
        padding=ft.Padding(left=16, top=7, right=16, bottom=7), bgcolor=BG)
    composer = ft.Container(content=ft.Row([
        ft.Container(content=input_box, expand=True), send_button
    ], vertical_alignment=ft.CrossAxisAlignment.END, spacing=8),
        padding=10, bgcolor=SURFACE, border=ft.Border.all(1, BORDER),
        border_radius=22, margin=ft.Margin(left=12, top=4, right=12, bottom=10))

    page.add(ft.Column([
        header,
        ft.Container(content=chat, expand=True, bgcolor=BG),
        status_bar,
        ft.Container(content=composer,
                     padding=ft.Padding(left=12, right=12, top=4, bottom=4))
    ], expand=True, spacing=0))
    add_bubble("ASTRO AI", "أهلًا بيك في ASTRO! ✨\n\nأنا مساعدك الذكي. اسألني عن أي حاجة، وهحاول أساعدك.")
    update_quota()
    page.update()


if __name__ == "__main__":
    ft.run(main)
