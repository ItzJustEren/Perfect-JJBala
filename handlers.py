import asyncio
import random
from aiogram import types, F, Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, ReactionTypeEmoji
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import *
from utils import *
import os

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
BOT_USERNAME = os.getenv("BOT_USERNAME")

class SetPersonality(StatesGroup):
    waiting_for_prompt = State()

class RolePlay(StatesGroup):
    waiting_for_content = State()

class AskQuestion(StatesGroup):
    waiting_for_question = State()
    waiting_for_video_prompt = State()

# ====== Keyboards ======
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton(text="📊 Panel", callback_data="panel")]
    ])

def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Change Personality", callback_data="change_personality")],
        [InlineKeyboardButton(text="Developers", callback_data="developers")],
        [InlineKeyboardButton(text="Add to group", callback_data="add_to_group")],
        [InlineKeyboardButton(text="Ask about me", callback_data="ask_about")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_main")]
    ])

def panel_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Search Mode: ON/OFF", callback_data="toggle_search"))
    builder.row(InlineKeyboardButton(text="🖼️ Generate Image", callback_data="generate_image"))
    builder.row(InlineKeyboardButton(text="🎬 Generate Video", callback_data="generate_video"))
    builder.row(InlineKeyboardButton(text="Role Play", callback_data="role_play"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="back_main"))
    return builder.as_markup()

def personality_menu():
    buttons = [
        [InlineKeyboardButton(text="🤪 Funny Friend", callback_data="set_funny")],
        [InlineKeyboardButton(text="😎 Cool Sigma", callback_data="set_sigma")],
        [InlineKeyboardButton(text="😊 Kind and Shy", callback_data="set_kind_shy")],
        [InlineKeyboardButton(text="🤖 AI Assistant", callback_data="set_ai_assistant")],
        [InlineKeyboardButton(text="👤 Normal Human", callback_data="set_normal_human")],
        [InlineKeyboardButton(text="✨ Create your own", callback_data="create_own")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

personality_prompts = {
    "funny": "تو یه رفیق شوخ و خودمونی هستی. با لحن دوستانه و غیررسمی حرف بزن. می‌تونی شوخی کنی ولی هیچ‌وقت خودت رو دلقک خطاب نکن. مثل یه رفیق صمیمی رفتار کن.",
    "sigma": "تو یه آدم خونسرد و با اعتماد به نفس هستی. آروم و مودب حرف بزن، گاهی با یه کم طنز. مثل یه بزرگ‌تر خونسرد رفتار کن.",
    "kind_shy": "تو یه آدم مهربان و کمی خجالتی هستی. با محبت و آرام حرف بزن، همیشه خوش‌برخورد باش.",
    "ai_assistant": "شما یک دستیار هوش مصنوعی حرفه‌ای هستید. دقیق، رسمی و مفید پاسخ دهید. اطلاعات را به صورت ساختاری ارائه کنید.",
    "normal_human": "تو یه انسان عادی هستی. خودمانی و دوستانه صحبت کن، مثل یه هم‌صحبت معمولی."
}

# ====== Helper Functions ======
async def apply_reaction(message: Message, text: str, mood: str = None):
    try:
        emoji = get_reaction_emoji(text, mood)
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)]
        )
    except Exception:
        pass

async def call_groq_with_context(chat_id: str, user_id: str, text: str, is_private: bool, search_result: str = None):
    personality = get_personality(chat_id, user_id if is_private else None)
    history = get_history(chat_id)
    memories = get_memories(chat_id, user_id)
    mood = get_mood(chat_id, user_id)
    
    system = personality
    if mood and mood != "خنثی":
        system += f" کاربر در حال حاضر احساس {mood} دارد. سعی کنید متناسب با این احساس پاسخ دهید."
    if search_result:
        system += f"\n\nاطلاعات جستجو: {search_result}"
    if memories:
        memory_text = "\n".join(memories)
        system += f"\n\nاطلاعات ذخیره شده از کاربر: {memory_text}"
    
    system += " فقط در صورتی که کاربر مستقیماً درباره سازنده سوال کرد، بگو تیم تاکا (@TaakaaOrg). در غیر این صورت نیازی به اشاره به سازنده نیست."
    
    messages = [{"role": "system", "content": system}]
    for turn in history[-15:]:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["bot"]})
    messages.append({"role": "user", "content": text})
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=700
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"متاسفانه خطایی رخ داده: {str(e)}"

async def show_thinking_and_reply(message: Message, response: str, personality: str = None):
    emoji = get_thinking_emoji(personality)
    thinking_msg = await message.reply(emoji)
    await asyncio.sleep(0.3)
    await thinking_msg.delete()
    
    if len(response) > 4096:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.reply(part)
    else:
        await message.reply(response)

# ====== Handlers ======
@dp.message(Command("start"))
async def start_command(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        add_group(str(message.chat.id))
        await message.reply(
            "hey im jojobala and i Developed by Taakaa Team now im your ai assistant and i try my best to help you, you can change my settings with /Panel code in chat and inline button gonna open\nTnx for adding me in group"
        )
        return
    await message.reply(
        "سلام داداش چطوری من جوجوبلا هستم\nرباتی که توسط تیم تاکا (@TaakaaOrg) توسعه یافتم تا به تو کمک کنم و دستیارت باشم.",
        reply_markup=main_menu()
    )

@dp.message(Command("settings"))
async def settings_command(message: Message):
    await message.reply("🔧 تنظیمات:", reply_markup=settings_menu())

@dp.message(Command("panel"))
async def panel_command(message: Message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    search_mode = get_search_mode(chat_id, user_id)
    status = "✅ فعال" if search_mode else "❌ غیرفعال"
    await message.reply(f"📊 پنل مدیریت\nوضعیت جستجو: {status}", reply_markup=panel_menu())

# ====== Callbacks ======
@dp.callback_query(F.data == "settings")
async def settings_callback(callback):
    await callback.message.edit_text("🔧 تنظیمات:", reply_markup=settings_menu())
    await callback.answer()

@dp.callback_query(F.data == "panel")
async def panel_callback(callback):
    chat_id = str(callback.message.chat.id)
    user_id = str(callback.from_user.id)
    search_mode = get_search_mode(chat_id, user_id)
    status = "✅ فعال" if search_mode else "❌ غیرفعال"
    await callback.message.edit_text(f"📊 پنل مدیریت\nوضعیت جستجو: {status}", reply_markup=panel_menu())
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main_callback(callback):
    await callback.message.edit_text(
        "سلام داداش چطوری من جوجوبلا هستم\nرباتی که توسط تیم تاکا (@TaakaaOrg) توسعه یافتم تا به تو کمک کنم و دستیارت باشم.",
        reply_markup=main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "change_personality")
async def change_personality_callback(callback):
    if callback.message.chat.type != "private":
        await callback.answer("این قابلیت فقط در پیوی در دسترس است.", show_alert=True)
        return
    await callback.message.edit_text("انتخاب شخصیت:", reply_markup=personality_menu())
    await callback.answer()

@dp.callback_query(F.data.startswith("set_"))
async def set_personality_callback(callback):
    if callback.message.chat.type != "private":
        await callback.answer("این قابلیت فقط در پیوی در دسترس است.", show_alert=True)
        return
    key = callback.data[4:]
    if key in personality_prompts:
        chat_id = str(callback.message.chat.id)
        user_id = str(callback.from_user.id)
        set_user_personality(chat_id, user_id, personality_prompts[key])
        await callback.message.edit_text(f"شخصیت به '{key.replace('_', ' ')}' تغییر کرد.", reply_markup=settings_menu())
    await callback.answer()

@dp.callback_query(F.data == "create_own")
async def create_own_callback(callback, state: FSMContext):
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
    await message.reply("شخصیت سفارشی شما با موفقیت ثبت شد.", reply_markup=settings_menu())
    await state.clear()

@dp.callback_query(F.data == "developers")
async def developers_callback(callback):
    await callback.message.edit_text(
        "توسعه‌دهنده: تیم تاکا\nکانال تلگرام: @TaaKaaOrg\n\nما یک تیم حرفه‌ای هستیم و به ساختن ربات‌های هوشمند علاقه داریم.",
        reply_markup=settings_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "add_to_group")
async def add_to_group_callback(callback):
    url = f"https://t.me/{BOT_USERNAME}?startgroup=start"
    await callback.message.edit_text(
        "برای افزودن ربات به گروه، روی لینک زیر کلیک کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Add to group", url=url)]])
    )
    await callback.answer()

@dp.callback_query(F.data == "ask_about")
async def ask_about_callback(callback):
    await callback.message.edit_text(
        "سلام من جوجوبلا هستم، یک ربات هوش مصنوعی که توسط تیم تاکا ساخته شده. "
        "من میتونم به سوالات شما پاسخ بدم، با شما گفتگو کنم، عکس‌ها رو تحلیل کنم و حتی شخصیت خودم رو با توجه به سلیقه شما تنظیم کنم. "
        "میتونید از دکمه Change Personality برای تغییر لحن و رفتار من استفاده کنید. "
        "همچنین میتونید من رو به گروه‌های خود اضافه کنید تا در جمع دوستانتان هم به کمک شما بیایم. "
        "سازنده من تیم تاکا است و من افتخار میکنم که در خدمت شما هستم.\n\n"
        "قابلیت‌های من:\n"
        "- تغییر شخصیت و لحن\n"
        "- جستجوی آنلاین برای اطلاعات دقیق\n"
        "- تحلیل تصاویر\n"
        "- ساخت تصویر با هوش مصنوعی (کیفیت بالا)\n"
        "- ساخت ویدیو با هوش مصنوعی\n"
        "- حفظ حافظه بلندمدت از مکالمات شما\n"
        "- تشخیص احساسات و پاسخ مناسب\n"
        "- بازی رول‌پلی انیمه\n"
        "- ارسال ایده‌های خودکار در گروه",
        reply_markup=settings_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "toggle_search")
async def toggle_search_callback(callback):
    chat_id = str(callback.message.chat.id)
    user_id = str(callback.from_user.id)
    toggle_search_mode(chat_id, user_id)
    status = get_search_mode(chat_id, user_id)
    status_text = "فعال" if status else "غیرفعال"
    await callback.answer(f"حالت جستجو {status_text} شد.")
    await callback.message.edit_text(
        f"📊 پنل مدیریت\nوضعیت جستجو: {'✅ فعال' if status else '❌ غیرفعال'}",
        reply_markup=panel_menu()
    )

@dp.callback_query(F.data == "generate_image")
async def generate_image_callback(callback, state: FSMContext):
    await callback.message.edit_text("🖼️ توضیحات تصویر مورد نظر خود را بنویسید:")
    await state.set_state(AskQuestion.waiting_for_question)
    await callback.answer()

@dp.callback_query(F.data == "generate_video")
async def generate_video_callback(callback, state: FSMContext):
    await callback.message.edit_text("🎬 توضیحات ویدیو مورد نظر خود را بنویسید:")
    await state.set_state(AskQuestion.waiting_for_video_prompt)
    await callback.answer()

@dp.message(AskQuestion.waiting_for_question)
async def generate_image_handler(message: Message, state: FSMContext):
    prompt = message.text
    await message.reply("🖼️ در حال ساخت تصویر... ممکن است چند ثانیه طول بکشد.")
    image_url = await generate_image(prompt)
    if image_url:
        try:
            await message.reply_photo(image_url, caption=f"تصویر ساخته شده بر اساس: {prompt}")
        except Exception:
            await message.reply("خطا در ارسال تصویر. لطفاً دوباره تلاش کنید.")
    else:
        await message.reply("متاسفانه تصویر ساخته نشد. لطفاً پرامپت دقیق‌تری بنویسید و دوباره تلاش کنید.")
    await state.clear()

@dp.message(AskQuestion.waiting_for_video_prompt)
async def generate_video_handler(message: Message, state: FSMContext):
    prompt = message.text
    await message.reply("🎬 در حال ساخت ویدیو... ممکن است ۲۰-۳۰ ثانیه طول بکشد.")
    video_url = await generate_video(prompt, duration=5)
    if video_url:
        try:
            await message.reply_video(video_url, caption=f"ویدیو ساخته شده بر اساس: {prompt}")
        except Exception:
            await message.reply("خطا در ارسال ویدیو. لطفاً دوباره تلاش کنید.")
    else:
        await message.reply("متاسفانه ویدیو ساخته نشد. لطفاً پرامپت دقیق‌تری بنویسید و دوباره تلاش کنید.")
    await state.clear()

@dp.callback_query(F.data == "role_play")
async def role_play_callback(callback, state: FSMContext):
    await callback.message.edit_text("اوکی خب انیمرو بگو بریم. یا اگر فیلمه بگو بریم دیگه.")
    await state.set_state(RolePlay.waiting_for_content)
    await callback.answer()

@dp.message(RolePlay.waiting_for_content)
async def start_role_play(message: Message, state: FSMContext):
    content = message.text
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    
    role_prompt = f"شما در حال رول‌پلی بر اساس {content} هستید. کاملاً وارد نقش شوید و مانند شخصیت‌های آن رفتار کنید."
    set_user_personality(chat_id, user_id, role_prompt)
    
    await message.reply(f"اوکی داداش! وارد رول‌پلی {content} شدیم. بیا شروع کنیم! 😎")
    await state.clear()

# ====== Photo Handler ======
@dp.message(F.photo)
async def handle_photo(message: Message):
    chat_id = str(message.chat.id)
    is_private = message.chat.type == "private"
    
    if not is_private:
        has_mention = False
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    if message.text[entity.offset:entity.offset+entity.length] == f"@{BOT_USERNAME}":
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
    
    response = await analyze_image(image_data, message.text)
    save_history(chat_id, message.text, response)
    await message.reply(response)

# ====== Text Handler ======
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
                    if text[entity.offset:entity.offset+entity.length] == f"@{BOT_USERNAME}":
                        has_mention = True
                        break
        has_name = "جوجوبلا" in text
        if not has_mention and not has_name:
            return
    
    mood = await detect_mood(text)
    save_mood(chat_id, user_id, mood)
    await apply_reaction(message, text, mood)
    
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
    
    search_result = None
    if search_mode and is_complex_question(text):
        thinking_msg = await message.reply("🔍 دارم جستجو میکنم... دو دقیقه زبون رو جیگر بزار")
        await asyncio.sleep(0.5)
        await thinking_msg.delete()
        search_result = await search_web(text)
    
    response = await call_groq_with_context(chat_id, user_id, text, is_private, search_result)
    save_history(chat_id, text, response)
    
    await show_thinking_and_reply(message, response, personality)

# ====== Auto Ideas ======
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
