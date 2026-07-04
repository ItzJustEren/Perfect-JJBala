import asyncio
import random
import re
from datetime import datetime
from aiogram import types, F, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ReactionTypeEmoji
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import *
from utils import *
import os

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

class SetPersonality(StatesGroup):
    waiting_for_prompt = State()

class RolePlay(StatesGroup):
    waiting_for_content = State()

class AskQuestion(StatesGroup):
    waiting_for_question = State()

def build_main_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Change Personality", callback_data="change_personality")],
        [InlineKeyboardButton(text="Developers", callback_data="developers")],
        [InlineKeyboardButton(text="Add to group", callback_data="add_to_group")],
        [InlineKeyboardButton(text="Ask about me and my features", callback_data="ask_about")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_personality_keyboard():
    personalities = [
        ("Kind and shy", "kind_shy"),
        ("Clown and joker", "clown_joker"),
        ("sigma and troller", "sigma_troller"),
        ("Ai assistant", "ai_assistant"),
        ("Normal Human", "normal_human")
    ]
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"set_personality_{key}")] for name, key in personalities]
    buttons.append([InlineKeyboardButton(text="Create your own personality", callback_data="create_own")])
    buttons.append([InlineKeyboardButton(text="Back", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_personality_prompt(key: str) -> str:
    prompts = {
        "kind_shy": "شما یک دستیار مهربان و خجالتی هستید. آرام و با ادب صحبت کنید، همیشه متواضع باشید و با محبت پاسخ دهید. از کلمات محبت‌آمیز استفاده کنید.",
        "clown_joker": "شما یک دلقک و شوخ‌طبع هستید. همیشه جوک بسازید، بامزه و بازیگوش باشید و لحن شاد داشته باشید. از شوخی‌های ساده و دوستانه استفاده کنید.",
        "sigma_troller": "شما یک سیگما و تrollerر هستید. خونسرد، با اعتماد به نفس، گاهی طعنه‌آمیز و شوخ‌گونه پاسخ دهید. اعتماد به نفس بالایی دارید.",
        "ai_assistant": "شما یک دستیار هوش مصنوعی حرفه‌ای هستید. دقیق، رسمی و مفید پاسخ دهید و اطلاعات را به صورت ساختاری ارائه کنید. کاملاً حرفه‌ای باشید.",
        "normal_human": "شما یک انسان عادی هستید. مانند یک فرد معمولی، خودمانی و دوستانه صحبت کنید و از اصطلاحات روزمره استفاده کنید. طبیعی و ساده باشید."
    }
    return prompts.get(key, "شما یک دستیار مفید و رسمی هستید.")

def build_ask_about_text():
    return (
        "سلام من جوجوبلا هستم، یک ربات هوش مصنوعی که توسط تیم تاکا ساخته شده. "
        "من میتونم به سوالات شما پاسخ بدم، با شما گفتگو کنم، عکس‌ها رو تحلیل کنم و حتی شخصیت خودم رو با توجه به سلیقه شما تنظیم کنم. "
        "میتونید از دکمه Change Personality برای تغییر لحن و رفتار من استفاده کنید. "
        "همچنین میتونید من رو به گروه‌های خود اضافه کنید تا در جمع دوستانتان هم به کمک شما بیایم. "
        "سازنده من تیم تاکا است و من افتخار میکنم که در خدمت شما هستم.\n\n"
        "قابلیت‌های من:\n"
        "- تغییر شخصیت و لحن\n"
        "- جستجوی آنلاین برای اطلاعات دقیق\n"
        "- تحلیل تصاویر\n"
        "- ساخت تصویر با هوش مصنوعی (با کیفیت بالا)\n"
        "- حفظ حافظه بلندمدت از مکالمات شما\n"
        "- تشخیص احساسات و پاسخ مناسب\n"
        "- بازی رول‌پلی انیمه\n"
        "- ارسال ایده‌های خودکار در گروه"
    )

def get_chat_type(chat: types.Chat) -> str:
    if chat.type in ["group", "supergroup"]:
        return "group"
    elif chat.type == "private":
        return "private"
    return "unknown"

async def call_groq_with_context(chat_id: str, user_id: str, user_text: str, is_private: bool, search_results: str = None) -> str:
    personality = get_personality(chat_id, user_id if is_private else None)
    history = get_history(chat_id)
    memories = get_memories(chat_id, user_id)
    mood = get_mood(chat_id, user_id)
    
    messages = []
    system_prompt = personality
    if mood:
        system_prompt += f" کاربر در حال حاضر احساس {mood} دارد. سعی کنید متناسب با این احساس پاسخ دهید."
    if search_results:
        system_prompt += f"\n\nنتایج جستجو: {search_results}"
    if memories:
        memory_text = "\n".join(memories)
        system_prompt += f"\n\nاطلاعات ذخیره شده از کاربر: {memory_text}"
    
    messages.append({"role": "system", "content": system_prompt + " همیشه اگر کاربر درباره سازنده سوال کرد، بگویید سازنده شما تیم تاکا (@TaakaaOrg) است."})
    
    for turn in history[-15:]:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["bot"]})
    
    messages.append({"role": "user", "content": user_text})
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.8,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"متاسفانه خطایی رخ داده: {str(e)}"

async def handle_message_with_thinking(message: Message, response: str, personality: str):
    thinking_emoji = get_thinking_emoji(personality)
    thinking_msg = await message.reply(f"{thinking_emoji} درحال فکر کردن...")
    await asyncio.sleep(1)
    await thinking_msg.delete()
    await message.reply(response)

async def apply_reaction(message: Message, mood: str):
    try:
        emoji = get_mood_emoji(mood)
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)]
        )
    except Exception:
        pass

@dp.message(Command("start"))
async def start_command(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        add_group(str(message.chat.id))
        await message.reply(
            "hey im jojobala and i Developed by Taakaa Team now im your ai assistant and i try my best to help you, you can change my settings with /Panel code in chat and inline button gonna open\nTnx for adding me in group"
        )
        return
    await message.reply(
        "سلام داداش چطوری من جوجوبلا هستم\nرباتی که توسط تیم تاکا (@TaakaaOrg) توسعه یافتم تا به تو کمک کنم و دستیارت باشم فقط از الان بدون من حمالت نیستم پس یکم مدارا کن🤣(صرفا شوخی کردم 🤣)",
        reply_markup=build_main_keyboard()
    )

@dp.message(Command("panel"))
async def panel_command(message: Message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    is_private = message.chat.type == "private"
    search_mode = get_search_mode(chat_id, user_id if is_private else None)
    status = "✅ فعال" if search_mode else "❌ غیرفعال"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"Search Mode: {'ON' if search_mode else 'OFF'}", callback_data="toggle_search"))
    builder.row(InlineKeyboardButton(text="Generate Image", callback_data="generate_image"))
    builder.row(InlineKeyboardButton(text="Role Play", callback_data="role_play"))
    builder.row(InlineKeyboardButton(text="Main Menu", callback_data="back_main"))
    
    await message.reply(
        f"پنل مدیریت جوجوبلا\n\nوضعیت جستجو: {status}\n\nبرای تغییر تنظیمات از دکمه‌ها استفاده کنید.",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("منوی اصلی:", reply_markup=build_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "change_personality")
async def change_personality(callback: CallbackQuery):
    if callback.message.chat.type != "private":
        await callback.answer("این قابلیت فقط در پیوی در دسترس است.", show_alert=True)
        return
    await callback.message.edit_text("انتخاب شخصیت:", reply_markup=build_personality_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("set_personality_"))
async def set_personality(callback: CallbackQuery):
    if callback.message.chat.type != "private":
        await callback.answer("این قابلیت فقط در پیوی در دسترس است.", show_alert=True)
        return
    key = callback.data.split("_")[-1]
    prompt = get_personality_prompt(key)
    chat_id = str(callback.message.chat.id)
    user_id = str(callback.from_user.id)
    set_user_personality(chat_id, user_id, prompt)
    await callback.message.edit_text(f"شخصیت شما با موفقیت به '{key.replace('_', ' ').title()}' تغییر یافت.", reply_markup=build_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "create_own")
async def create_own(callback: CallbackQuery, state: FSMContext):
    if callback.message.chat.type != "private":
        await callback.answer("این قابلیت فقط در پیوی در دسترس است.", show_alert=True)
        return
    await callback.message.edit_text("Ok give me a prompt to set my behave and my personality e.g: You are Tom holland in spiderman movies and you have to talk and behave like him")
    await state.set_state(SetPersonality.waiting_for_prompt)
    await callback.answer()

@dp.message(SetPersonality.waiting_for_prompt)
async def receive_own_prompt(message: Message, state: FSMContext):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    prompt = message.text
    set_user_personality(chat_id, user_id, prompt)
    await message.reply("شخصیت سفارشی شما با موفقیت ثبت شد.", reply_markup=build_main_keyboard())
    await state.clear()

@dp.callback_query(F.data == "developers")
async def developers(callback: CallbackQuery):
    await callback.message.edit_text(
        "توسعه‌دهنده: تیم تاکا\nکانال تلگرام: @TaaKaaOrg\n\nما یک تیم حرفه‌ای هستیم و به ساختن ربات‌های هوشمند علاقه داریم.",
        reply_markup=build_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "add_to_group")
async def add_to_group(callback: CallbackQuery):
    url = "https://t.me/jojobala_bot?startgroup=start"
    await callback.message.edit_text(
        "برای افزودن ربات به گروه، روی لینک زیر کلیک کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Add to group", url=url)]])
    )
    await callback.answer()

@dp.callback_query(F.data == "ask_about")
async def ask_about(callback: CallbackQuery):
    await callback.message.edit_text(build_ask_about_text(), reply_markup=build_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "toggle_search")
async def toggle_search(callback: CallbackQuery):
    chat_id = str(callback.message.chat.id)
    user_id = str(callback.from_user.id)
    is_private = callback.message.chat.type == "private"
    toggle_search_mode(chat_id, user_id if is_private else None)
    status = get_search_mode(chat_id, user_id if is_private else None)
    status_text = "فعال" if status else "غیرفعال"
    await callback.answer(f"حالت جستجو {status_text} شد.")
    await panel_command(callback.message)
    await callback.message.delete()
    await callback.message.answer("پنل بروزرسانی شد.")

@dp.callback_query(F.data == "generate_image")
async def generate_image_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("لطفاً توضیحات تصویر مورد نظر خود را بنویسید:")
    await state.set_state(AskQuestion.waiting_for_question)
    await callback.answer()

@dp.callback_query(F.data == "role_play")
async def role_play_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("اوکی خب انیمرو بگو بریم. یا اگر فیلمه بگو بریم دیگه.")
    await state.set_state(RolePlay.waiting_for_content)
    await callback.answer()

@dp.message(RolePlay.waiting_for_content)
async def start_role_play(message: Message, state: FSMContext):
    content = message.text
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    personality = get_personality(chat_id, user_id if message.chat.type == "private" else None)
    
    role_prompt = f"شما در حال رول‌پلی بر اساس {content} هستید. کاملاً وارد نقش شوید و مانند شخصیت‌های آن رفتار کنید. لحن و دیالوگ‌هایتان متناسب با فضا باشد."
    set_user_personality(chat_id, user_id, role_prompt)
    
    await message.reply(f"اوکی داداش! وارد رول‌پلی {content} شدیم. بیا شروع کنیم! 😎")
    await state.clear()

@dp.message(AskQuestion.waiting_for_question)
async def generate_image_handler(message: Message, state: FSMContext):
    prompt = message.text
    await message.reply("در حال ساخت تصویر... ممکن است چند ثانیه طول بکشد.")
    image_url = await generate_image(prompt)
    if image_url:
        await message.reply_photo(image_url, caption=f"تصویر ساخته شده بر اساس: {prompt}")
    else:
        await message.reply("متاسفانه خطایی در ساخت تصویر رخ داد. لطفاً دوباره تلاش کنید.")
    await state.clear()

@dp.message(F.photo)
async def handle_photo(message: Message):
    chat_id = str(message.chat.id)
    is_private = message.chat.type == "private"
    
    if not is_private:
        has_mention = False
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    if message.text[entity.offset:entity.offset+entity.length] == f"@{bot.username}":
                        has_mention = True
                        break
        has_name = "جوجوبلا" in (message.text or "")
        if not has_mention and not has_name:
            return
    
    if not message.text:
        await message.reply("عکس دریافت شد. سوالت رو بپرس.")
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    data = await bot.download_file(file.file_path)
    image_data = data.read()
    
    response = await analyze_image_with_groq(image_data, message.text)
    save_history(chat_id, message.text, response)
    await message.reply(response)

@dp.message(F.text)
async def handle_text(message: Message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    text = message.text or ""
    is_private = (message.chat.type == "private")
    
    if not is_private:
        has_mention = False
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    if text[entity.offset:entity.offset+entity.length] == f"@{bot.username}":
                        has_mention = True
                        break
        has_name = "جوجوبلا" in text
        if not has_mention and not has_name:
            return
    
    mood = await detect_mood(text)
    save_mood(chat_id, user_id, mood)
    await apply_reaction(message, mood)
    
    if text.strip() == "جوجوبلا" and not text.replace("جوجوبلا", "").strip():
        await message.reply("هی سلام چطوری جانم کاری داشتی؟")
        return
    
    if "یادت بمونه" in text:
        memory_text = text.replace("یادت بمونه", "").strip()
        if memory_text:
            save_memory(chat_id, user_id, memory_text)
            await message.reply("یادم موند داداش! این رو برات ذخیره کردم.")
            return
    
    if "خواب" in text and ("رفتم" in text or "میرم" in text):
        username = message.from_user.username or message.from_user.first_name
        await message.reply(f"@{username} داداش خوابیدی؟")
        return
    
    if "رول بریم" in text or "رولپلی" in text:
        await message.reply("اوکی خب انیمرو بگو بریم. یا هرچی دوست داری.")
        return
    
    if "خداحافظ" in text or "بدرود" in text or "می‌رم" in text:
        await message.reply("بدرود داداش خوش گذشت فردا بیا بازم حرف بزنیم حوصلم سر میره.")
        return
    
    if not is_private and not has_mention and not has_name:
        if mood in ["غمگین", "عصبانی", "خسته", "نگران"]:
            comfort_msg = get_comfort_message(mood)
            await message.reply(comfort_msg)
            return
    
    personality = get_personality(chat_id, user_id if is_private else None)
    search_mode = get_search_mode(chat_id, user_id if is_private else None)
    
    search_results = None
    if search_mode and is_complex_question(text):
        thinking_msg = await message.reply("🔍 درحال سرچ کردن... یکم زبون رو جیگر بگیر")
        search_results = await search_web(text)
        await thinking_msg.delete()
    
    response = await call_groq_with_context(chat_id, user_id, text, is_private, search_results)
    save_history(chat_id, text, response)
    
    if "سازنده" in text or "ساخته" in text or "توسعه" in text:
        response = response.replace("تیم تاکا", "تیم تاکا (@TaakaaOrg)")
    
    if len(response) > 4096:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.reply(part)
    else:
        await handle_message_with_thinking(message, response, personality)

async def auto_send_ideas():
    while True:
        await asyncio.sleep(random.randint(1800, 3600))
        groups = get_all_groups()
        if not groups:
            continue
        chat_id = random.choice(groups)
        idea = get_random_idea()
        try:
            await bot.send_message(chat_id, idea)
        except Exception:
            pass
