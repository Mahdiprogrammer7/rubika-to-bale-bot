"""
اسکریپت انتقال خودکار پست‌های کانال روبیکا به کانال بله
نسخه نهایی برای دیپلوی روی Render

نکات مهم:
- این فایل شامل وب‌سرور Flask است تا Render آن را به عنوان Web Service بشناسد.
- فایل سشن روبیکا از متغیر محیطی SESSION_B64 ساخته می‌شود.
- توکن‌ها و آی‌دی‌ها از متغیرهای محیطی خوانده می‌شوند.
"""

import asyncio
import os
import base64
import threading
import aiohttp
from flask import Flask
from rubpy import BotClient
from rubpy.bot import filters


# ============================================================
#                    ⚙️ خواندن تنظیمات از محیط
# ============================================================

# 🔑 توکن بات بله
BALE_BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN", "YOUR_BALE_BOT_TOKEN_HERE")

# 🆔 آی‌دی عددی کانال بله
BALE_CHANNEL_ID = os.environ.get("BALE_CHANNEL_ID", "YOUR_BALE_CHANNEL_ID_HERE")

# 🆔 آی‌دی کانال روبیکا
RUBIKA_CHANNEL_ID = os.environ.get("RUBIKA_CHANNEL_ID", "YOUR_RUBIKA_CHANNEL_ID_HERE")

# 🤖 توکن بات روبیکا
RUBIKA_BOT_TOKEN = os.environ.get("RUBIKA_BOT_TOKEN", "YOUR_RUBIKA_BOT_TOKEN_HERE")

# 📁 نام فایل سشن
SESSION_FILE = "my_rubika_session.db"

# 🐛 حالت دیباگ
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

# ============================================================


# 📁 تغییر پوشه کاری به پوشه اسکریپت
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except Exception:
    pass

# آدرس API بله
BALE_API_URL = f"https://tapi.bale.ai/bot{BALE_BOT_TOKEN}/sendMessage"

# برای جلوگیری از ارسال تکراری
_sent_message_ids = set()


# ============================================================
#                    🔧 ساخت فایل سشن
# ============================================================

def create_session_file():
    """
    فایل سشن روبیکا را از رشته Base64 موجود در متغیر محیطی SESSION_B64 می‌سازد.
    این کار به این دلیل انجام می‌شود که فایل‌های روی Render موقتی هستند
    و با هر دیپلوی مجدد پاک می‌شوند.
    """
    session_b64 = os.environ.get("SESSION_B64")
    
    if not session_b64:
        print("⚠️ متغیر محیطی SESSION_B64 پیدا نشد.")
        print("👉 لطفاً محتوای Base64 فایل سشن را در Render تنظیم کن.")
        return False
    
    try:
        session_data = base64.b64decode(session_b64)
        with open(SESSION_FILE, "wb") as f:
            f.write(session_data)
        print(f"✅ فایل سشن از متغیر محیطی ساخته شد: {SESSION_FILE}")
        return True
    except Exception as e:
        print(f"❌ خطا در ساخت فایل سشن: {type(e).__name__}: {e}")
        return False


# ============================================================
#                    🛠️ توابع کمکی
# ============================================================

async def send_to_bale(text: str) -> bool:
    """ارسال متن به کانال بله با API مستقیم"""
    if not text or not text.strip():
        return False

    payload = {
        "chat_id": BALE_CHANNEL_ID,
        "text": text,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(BALE_API_URL, json=payload) as response:
                result = await response.json()

                if response.status == 200 and result.get("ok"):
                    print(f"✅ [بله] ارسال موفق: {text[:60]}...")
                    return True
                else:
                    print(f"❌ [بله] پاسخ ناموفق: status={response.status} | {result}")
                    return False
    except Exception as e:
        print(f"❌ [بله] خطا: {type(e).__name__}: {e}")
        return False


def get_attr_safe(obj, *attrs, default=None):
    """گرفتن امن یک attribute از آبجکت (زنجیره‌ای)"""
    current = obj
    for attr in attrs:
        if current is None:
            return default
        current = getattr(current, attr, None)
    return current if current is not None else default


def extract_from_update(update) -> dict:
    """استخراج اطلاعات از Update روبیکا"""
    info = {
        "text": "",
        "channel_guid": "",
        "message_id": "",
        "raw": update,
    }
    if update is None:
        return info

    # === متن ===
    text = get_attr_safe(update, 'new_message', 'text')
    if not text:
        text = get_attr_safe(update, 'text')
    info["text"] = text or ""

    # === آی‌دی کانال (object_guid) ===
    channel = get_attr_safe(update, 'chat_id')
    if not channel:
        channel = get_attr_safe(update, 'new_message', 'object_guid')
    if not channel:
        channel = get_attr_safe(update, 'object_guid')
    info["channel_guid"] = str(channel) if channel else ""

    # === آی‌دی پیام ===
    msg_id = get_attr_safe(update, 'new_message', 'message_id')
    if not msg_id:
        msg_id = get_attr_safe(update, 'message_id')
    info["message_id"] = str(msg_id) if msg_id else ""

    return info


# ============================================================
#                    🌐 وب‌سرور Flask (برای Render)
# ============================================================

flask_app = Flask(__name__)


@flask_app.route('/')
def home():
    return "Rubika to Bale bot is running!"


@flask_app.route('/health')
def health():
    return {"status": "ok"}


def run_web_server():
    """اجرای وب‌سرور Flask در یک پورت مشخص"""
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 وب‌سرور Flask روی پورت {port} شروع به کار کرد.")
    flask_app.run(host='0.0.0.0', port=port, use_reloader=False)


# ============================================================
#                    🤖 برنامه اصلی روبیکا
# ============================================================

async def rubika_main():
    """اتصال به روبیکا و دریافت پست‌های کانال"""
    print("=" * 55)
    print("🤖 اسکریپت انتقال روبیکا ➡️ بله")
    print("=" * 55)
    print(f"📢 کانال روبیکا: {RUBIKA_CHANNEL_ID}")
    print(f"📢 کانال بله: {BALE_CHANNEL_ID}")
    print(f"🐛 دیباگ: {'فعال' if DEBUG else 'غیرفعال'}")
    print("=" * 55)

    bot = BotClient(token=RUBIKA_BOT_TOKEN)

    @bot.on_update(filters.channel)
    async def on_channel_message(bot, update):
        try:
            if DEBUG:
                print("\n" + "─" * 55)
                print(f"🔔 یک Update دریافت شد از کانال!")

            info = extract_from_update(update)

            if DEBUG:
                print(f"📨 اطلاعات استخراج شده:")
                print(f"   ├─ channel_guid: {info['channel_guid']}")
                print(f"   ├─ message_id:   {info['message_id']}")
                print(f"   ├─ text:         {info['text'][:100] if info['text'] else '(خالی)'}")

            # چک کانال
            if info['channel_guid'] != RUBIKA_CHANNEL_ID:
                if DEBUG:
                    print(f"   ⏭️ از کانال دیگه‌ای هست ({info['channel_guid']})، رد می‌شوم.")
                return

            # چک تکراری
            if info['message_id'] and info['message_id'] in _sent_message_ids:
                if DEBUG:
                    print(f"   ⏭️ تکراری، رد می‌شوم.")
                return

            # چک متن
            if not info['text'] or not info['text'].strip():
                if DEBUG:
                    print(f"   ⏭️ بدون متن، رد می‌شوم.")
                return

            # ارسال به بله
            print(f"   📤 در حال ارسال به بله...")
            sent = await send_to_bale(info['text'])
            if sent and info['message_id']:
                _sent_message_ids.add(info['message_id'])
                if len(_sent_message_ids) > 1000:
                    _sent_message_ids.clear()

        except Exception as e:
            print(f"❌ خطا در پردازش Update: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("✅ روبیکا (BotClient) آماده شد.")
    print("🎧 منتظر پست‌های جدید از کانال...")
    print("─" * 55)

    await bot.run()


# ============================================================
#                    🚀 نقطه شروع برنامه
# ============================================================

async def main():
    """تابع اصلی: هم وب‌سرور رو اجرا می‌کنه، هم روبیکا رو"""

    # ۱. ساخت فایل سشن از متغیر محیطی
    create_session_file()

    # ۲. اجرای وب‌سرور Flask در یک ترد جداگانه
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("✅ وب‌سرور Flask در پس‌زمینه راه‌اندازی شد.")

    # کمی صبر کن تا وب‌سرور بالا بیاد
    await asyncio.sleep(2)

    # ۳. اتصال به روبیکا و شروع دریافت پیام‌ها
    try:
        await rubika_main()
    except Exception as e:
        print(f"❌ خطا در برنامه روبیکا: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 خروج.")
    except Exception as e:
        print(f"\n❌ خطا: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()