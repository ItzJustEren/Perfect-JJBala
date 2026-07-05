# ============================================
# فایل 4: utils.py
# ============================================

import asyncio
import base64
import random
import re
import urllib.parse
from datetime import datetime
from googlesearch import search
from groq import Groq
import aiohttp
import os
import requests
from PIL import Image

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
AGNES_API_KEY = os.getenv("AGNES_API_KEY")
AGNES_API_URL = "https://apihub.agnes-ai.com"

groq_client = Groq(api_key=GROQ_API_KEY)

def is_complex_question(text: str) -> bool:
    complex_keywords = ["چرا", "چگونه", "چه زمانی", "چه کسی", "تحلیل", "بررسی", "مقایسه", "تاریخچه", "آمار", "داده", "اطلاعات", "علت", "دلیل"]
    return any(kw in text for kw in complex_keywords) and len(text.split()) > 5

async def google_search(query: str, num_results: int = 3) -> str:
    try:
        results = []
        for url in search(query, num_results=num_results, lang="fa"):
            results.append(url)
        if results:
            return "\n".join(results)
        return "نتیجه‌ای یافت نشد."
    except Exception:
        return "خطا در جستجوی گوگل."

async def search_web(query: str) -> str:
    return await google_search(query)

async def generate_image(prompt: str) -> str:
    url = f"{AGNES_API_URL}/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "agnes-image-2.1-flash",
        "prompt": prompt,
        "size": "1024x768"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("data", [{}])[0].get("url")
                return None
    except Exception:
        return None

async def generate_video(prompt: str, duration: int = 5) -> str:
    url = f"{AGNES_API_URL}/v1/videos/generations"
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
            async with session.post(url, json=data, headers=headers) as response:
                if response.status != 200:
                    return None
                result = await response.json()
                task_id = result.get("task_id")
                if not task_id:
                    return None

            status_url = f"{url}/{task_id}"
            for _ in range(30):
                await asyncio.sleep(1)
                async with session.get(status_url, headers=headers) as status_response:
                    if status_response.status != 200:
                        continue
                    status_data = await status_response.json()
                    status = status_data.get("status")
                    if status == "completed":
                        return status_data.get("result", {}).get("url")
                    elif status == "failed":
                        return None
            return None
    except Exception:
        return None

async def analyze_image_with_groq(image_data: bytes, question: str) -> str:
    try:
        encoded = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{encoded}"
        
        response = groq_client.chat.completions.create(
            model="llama-4-scout-17b-16e-instruct",
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
                model="qwen/qwen3.6-27b",
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

async def detect_mood(text: str) -> str:
    moods = ["شاد", "غمگین", "عصبانی", "خسته", "مشتاق", "بی‌حوصله", "نگران"]
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "احساسات کاربر را تشخیص بده. فقط یکی از این کلمات را برگردان: شاد, غمگین, عصبانی, خسته, مشتاق, بی‌حوصله, نگران"},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=10
        )
        detected = response.choices[0].message.content.strip()
        for mood in moods:
            if mood in detected:
                return mood
        return "خنثی"
    except Exception:
        return "خنثی"

def get_mood_emoji(mood: str) -> str:
    emojis = {
        "شاد": "😊",
        "غمگین": "😢",
        "عصبانی": "😡",
        "خسته": "😴",
        "مشتاق": "🤩",
        "بی‌حوصله": "😒",
        "نگران": "😰",
        "خنثی": "😐"
    }
    return emojis.get(mood, "😐")

def get_comfort_message(mood: str) -> str:
    comfort = {
        "غمگین": "داداش ناراحت نباش، همه چی درست میشه. من کنارت هستم تا کمکت کنم. برات یه آغوش مجازی میفرستم 🤗",
        "عصبانی": "هی آروم باش داداش. نفس عمیق بکش، همه چیز حل میشه. بیا با هم یه راه حل پیدا کنیم.",
        "خسته": "چقدر خسته‌ای داداش؟ برو یه استراحت کوتاه بکن، یه چای بخور. بعدش با انرژی بیشتری برمیگردی.",
        "نگران": "نگران نباش داداش، همه چیز خوب میشه. بهت قول میدم. بیا با هم بررسی کنیم ببینیم چیکار میشه کرد."
    }
    return comfort.get(mood, "همیشه بهت افتخار میکنم داداش. تو عالی‌ای.")

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
        "جوجوبلا میگه امروز یه روز عالی برای یادگیری چیزای جدید هست، نظر شما چیه؟",
        "چه خبر از دنیا؟ یه سناریوی جالب بگید تا باهاش کلی خندیدیم",
        "راستی یادتون باشه که زندگی فقط یه بار اتفاق میفته، پس ازش لذت ببرید 🎉",
        "اگه یه ابرقدرت میتونستید داشته باشید، چی بود؟ من که میخوام پرواز کنم!"
    ]
    return random.choice(ideas)

def extract_name_from_text(text: str) -> str:
    pattern = r'@(\w+)'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None
