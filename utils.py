import aiohttp
import asyncio
import base64
import random
import re
import urllib.parse
import os
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
AGNES_API_KEY = os.getenv("AGNES_API_KEY")
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"

groq_client = Groq(api_key=GROQ_API_KEY)

# ====== Agnes AI Helpers ======
async def agnes_chat(prompt: str, system: str = None) -> str:
    url = f"{AGNES_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": "agnes-2.0-flash",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                return None
    except Exception:
        return None

async def generate_image(prompt: str) -> str:
    url = f"{AGNES_BASE_URL}/images/generations"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "agnes-image-2.1-flash",
        "prompt": prompt,
        "size": "1024x1024",
        "num_images": 1
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=60) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["data"][0]["url"]
                return None
    except Exception:
        return None

async def generate_video(prompt: str, duration: int = 5) -> str:
    url = f"{AGNES_BASE_URL}/videos/generations"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "duration": duration,
        "size": "1152x768"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=120) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    task_id = result.get("task_id")
                    if not task_id:
                        return None
                    
                    status_url = f"{url}/{task_id}"
                    for _ in range(30):
                        await asyncio.sleep(2)
                        async with session.get(status_url, headers=headers) as status_resp:
                            if status_resp.status == 200:
                                status_data = await status_resp.json()
                                if status_data.get("status") == "completed":
                                    return status_data.get("result", {}).get("url")
                                elif status_data.get("status") == "failed":
                                    return None
                    return None
                return None
    except Exception:
        return None

async def detect_mood(text: str) -> str:
    try:
        response = await agnes_chat(
            text,
            system="احساسات کاربر را تشخیص بده. فقط یکی از این کلمات را برگردان: شاد, غمگین, عصبانی, خسته, نگران, خنثی"
        )
        if response and response in ["شاد", "غمگین", "عصبانی", "خسته", "نگران", "خنثی"]:
            return response
        return "خنثی"
    except Exception:
        return "خنثی"

async def search_web(query: str) -> str:
    try:
        from googlesearch import search
        results = []
        for url in search(query, num_results=3, lang="fa", user_agent="Mozilla/5.0"):
            results.append(url)
        if results:
            return "\n".join(results)
        return "نتیجه‌ای پیدا نشد."
    except Exception:
        try:
            response = await agnes_chat(
                f"لطفاً اطلاعات مفید درباره '{query}' را از دانش خودت بگو.",
                system="به عنوان یک دستیار جستجو، اطلاعات مفید و مختصر درباره سوال کاربر بده."
            )
            return response if response else "خطا در جستجو."
        except Exception:
            return "خطا در جستجو."

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
    except Exception as e:
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
        except Exception as e2:
            return f"خطا در تحلیل تصویر: {str(e2)}"

# ====== Enhanced reaction emoji based on text content ======
def get_reaction_emoji(text: str, mood: str = None) -> str:
    # First check for specific keywords
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
    if "!" in text or "!" in text:
        return "😮"
    # Fallback to mood-based emoji
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
        "غمگین": "ناراحت نباش داداش، همه چی درست میشه. من کنارت هستم 🤗",
        "عصبانی": "آروم باش داداش، نفس عمیق بکش. بیا با هم حلش کنیم 💪",
        "خسته": "برو یه استراحت کوتاه بکن، یه چای بخور. بعدش با انرژی بیشتری برمیگردی ☕",
        "نگران": "نگران نباش داداش، همه چی خوب میشه. بهت قول میدم 🤝"
    }
    return messages.get(mood, "همیشه بهت افتخار میکنم داداش. تو عالی‌ای ❤️")

def get_thinking_emoji(personality: str) -> str:
    if "شوخ" in personality or "دلقک" in personality:
        return "🤡"
    elif "سیگما" in personality or "troller" in personality:
        return "😎"
    elif "مهربان" in personality or "شرمگین" in personality:
        return "😊"
    elif "هوش مصنوعی" in personality or "دستیار" in personality:
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
    complex_keywords = ["چرا", "چگونه", "چه زمانی", "چه کسی", "تحلیل", "بررسی", "مقایسه", "تاریخچه", "آمار", "داده", "اطلاعات", "علت", "دلیل"]
    return any(kw in text for kw in complex_keywords) and len(text.split()) > 5
