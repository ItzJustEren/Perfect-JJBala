import aiohttp
import asyncio
import base64
import random
import re
import urllib.parse
import os
from groq import Groq
from duckduckgo_search import DDGS

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# ====== Image Generation with Pollinations.ai ======
async def generate_image(prompt: str) -> str:
    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&model=flux"
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=10) as resp:
                if resp.status == 200:
                    return url
        return None
    except Exception:
        return None

# ====== Video Generation with Pollinations.ai ======
async def generate_video(prompt: str, duration: int = 5) -> str:
    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://video.pollinations.ai/prompt/{encoded}?width=1152&height=768&duration={duration}&nologo=true"
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=10) as resp:
                if resp.status == 200:
                    return url
        return None
    except Exception:
        return None

# ====== Search with DuckDuckGo + Google Fallback ======
async def search_web(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=3):
                results.append(f"• {r['title']}\n{r['body'][:200]}...\n{r['href']}")
            if results:
                return "\n\n".join(results)
        return await google_search_fallback(query)
    except Exception:
        return await google_search_fallback(query)

async def google_search_fallback(query: str) -> str:
    try:
        from googlesearch import search
        results = []
        for url in search(query, num_results=3, lang="fa", user_agent="Mozilla/5.0"):
            results.append(url)
        if results:
            return "\n".join(results)
        return "نتیجه‌ای پیدا نشد."
    except Exception:
        return "خطا در جستجو."

# ====== Mood Detection using Groq (fast) ======
async def detect_mood(text: str) -> str:
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "احساسات کاربر را تشخیص بده. فقط یکی از این کلمات را برگردان: شاد, غمگین, عصبانی, خسته, نگران, خنثی"},
                {"role": "user", "content": text[:100]}
            ],
            temperature=0.1,
            max_tokens=10
        )
        mood = response.choices[0].message.content.strip()
        if mood in ["شاد", "غمگین", "عصبانی", "خسته", "نگران", "خنثی"]:
            return mood
        return "خنثی"
    except Exception:
        return "خنثی"

# ====== Image Analysis ======
async def analyze_image(image_data: bytes, question: str) -> str:
    try:
        encoded = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{encoded}"
        
        response = groq_client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url", "image_url": {"url": data_url}}
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"خطا در تحلیل تصویر: {str(e)}"

# ====== Reaction Functions ======
def get_reaction_emoji(text: str, mood: str = None) -> str:
    if "سلام" in text or "درود" in text:
        return "👋"
    if "خداحافظ" in text or "بدرود" in text or "می‌رم" in text:
        return "👋"
    if "خنده" in text or "جوک" in text or "😂" in text:
        return "😂"
    if "❤️" in text or "عشق" in text or "دوست" in text:
        return "❤️"
    if "?" in text or "؟" in text:
        return "🤔"
    if "!" in text:
        return "😮"
    if "خوب" in text or "عالی" in text:
        return "😊"
    if "بد" in text or "خراب" in text or "ناراحت" in text:
        return "😟"
    if mood:
        return get_mood_emoji(mood)
    return "😐"

def get_mood_emoji(mood: str) -> str:
    emojis = {
        "شاد": "😊",
        "غمگین": "😢",
        "عصبانی": "😡",
        "خسته": "😴",
        "نگران": "😰",
        "خنثی": "😐"
    }
    return emojis.get(mood, "😐")

def get_comfort_message(mood: str) -> str:
    messages = {
        "غمگین": "داداش ناراحت نباش، همه چی درست میشه. من کنارتم 🤗",
        "عصبانی": "آروم باش داداش. نفس عمیق بکش، همه چی حل میشه 💪",
        "خسته": "برو یه استراحت بکن، یه چای بخور. بعدش انرژی میگیری ☕",
        "نگران": "نگران نباش داداش، من اینجام تا کمکت کنم 🤝"
    }
    return messages.get(mood, "همیشه بهت افتخار میکنم داداش ❤️")

def get_thinking_emoji(personality: str = None) -> str:
    if not personality:
        return "🧠"
    if "شوخ" in personality or "جوک" in personality:
        return "🤡"
    elif "سیگما" in personality or "خونسرد" in personality:
        return "😎"
    elif "مهربان" in personality or "خجالتی" in personality:
        return "😊"
    elif "دستیار" in personality or "حرفه‌ای" in personality:
        return "🤖"
    else:
        return "🧠"

def get_random_idea() -> str:
    ideas = [
        "قهرمان امروز @کاربر هست همیشه با جوکاش میادو همرو میخندونه",
        "امتحان کنید: جوجوبلا هرکدوم ما توی فیلم دزدی چه نقشی داشتیم؟",
        "به نظرتون بهترین فیلم تاریخ چیه؟ من که عاشق سه‌گانه بازگشت به آینده هستم",
        "اگه یه روز میتونستید به گذشته سفر کنید، کدوم دوره رو انتخاب میکردید؟",
        "جوجوبلا میگه امروز یه روز عالی برای یادگیری چیزای جدید هست، نظر شما چیه؟"
    ]
    return random.choice(ideas)

def is_complex_question(text: str) -> bool:
    keywords = ["چرا", "چگونه", "چه زمانی", "چه کسی", "تحلیل", "بررسی", "مقایسه", "تاریخچه", "آمار", "داده", "اطلاعات", "علت", "دلیل"]
    return any(k in text for k in keywords) and len(text.split()) > 5
