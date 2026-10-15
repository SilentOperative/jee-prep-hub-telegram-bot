import asyncio
import logging
import os
from datetime import datetime, timezone, date
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in environment.")
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing Supabase server credentials in environment.")

# This is a backend-only bot. Never place the service-role key in frontend code,
# public repositories, screenshots, or Telegram messages.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

HOME = [
    ("⚡ Today's Mission", "mission"),
    ("🧠 Mistake Memory", "mistakes"),
    ("🛟 Backlog Rescue", "backlog"),
    ("📚 Resource Universe", "resources"),
    ("📊 My Progress", "progress"),
    ("❓ Quick Quiz", "quiz"),
]

def menu_markup():
    kb = InlineKeyboardBuilder()
    for label, action in HOME:
        kb.button(text=label, callback_data=action)
    kb.adjust(2, 2, 2)
    return kb.as_markup()

def tg_id(message_or_callback):
    if isinstance(message_or_callback, Message):
        return message_or_callback.from_user.id
    return message_or_callback.from_user.id

def ensure_profile(user):
    uid = user.id
    existing = supabase.table("bot_profiles").select("telegram_id,xp,level,streak,last_active").eq("telegram_id", uid).limit(1).execute().data
    today = date.today().isoformat()
    if not existing:
        supabase.table("bot_profiles").insert({
            "telegram_id": uid,
            "display_name": (user.full_name or "Student")[:80],
            "username": user.username,
            "xp": 0, "level": 1, "streak": 0,
            "last_active": today
        }).execute()
    else:
        supabase.table("bot_profiles").update({
            "display_name": (user.full_name or "Student")[:80],
            "username": user.username,
            "last_active": today
        }).eq("telegram_id", uid).execute()

def add_xp(uid: int, amount: int):
    row = supabase.table("bot_profiles").select("xp").eq("telegram_id", uid).single().execute().data
    xp = int(row.get("xp", 0)) + amount
    level = 1 + xp // 100
    supabase.table("bot_profiles").update({"xp": xp, "level": level}).eq("telegram_id", uid).execute()
    return xp, level

@dp.message(CommandStart())
async def start(message: Message):
    ensure_profile(message.from_user)
    await message.answer(
        "🚀 *JEE Prep Hub — Mission Control*\n\n"
        "Not another PDF dump. This bot turns preparation into daily missions, "
        "tracks mistakes worth revisiting, and helps you recover backlogs without panic.\n\n"
        "Choose your next move:",
        reply_markup=menu_markup(),
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "/start — Mission Control\n"
        "/mission — Today's mission\n"
        "/quiz — Quick practice quiz\n"
        "/mistakes — Review saved mistakes\n"
        "/backlog — Add a backlog task\n"
        "/resources — Browse approved resource links\n"
        "/progress — XP and level"
    )

@dp.message(Command("mission"))
async def mission_cmd(message: Message):
    ensure_profile(message.from_user)
    await show_mission(message, message.from_user.id)

async def show_mission(target, uid):
    today = date.today().isoformat()
    row = supabase.table("daily_missions").select("*").eq("mission_date", today).eq("telegram_id", uid).limit(1).execute().data
    if row:
        mission = row[0]
        text = f"⚡ *Today's Mission*\n\n{mission['title']}\n{mission['description']}\n\nReward: +{mission['xp_reward']} XP"
    else:
        # Simple daily mission generated from a rotating, practical template.
        templates = [
            ("Concept Sprint", "Revise one small concept for 20 minutes, then write 3 key points from memory.", 20),
            ("Practice Run", "Solve 8 questions from one topic. Mark every guess and every error.", 25),
            ("Recall Check", "Close your notes and explain one concept aloud in your own words.", 15),
            ("Error Hunter", "Revisit 3 old mistakes and write why the correct method works.", 25),
        ]
        index = date.today().toordinal() % len(templates)
        title, description, reward = templates[index]
        saved = supabase.table("daily_missions").insert({
            "telegram_id": uid, "mission_date": today, "title": title,
            "description": description, "xp_reward": reward, "completed": False
        }).execute().data
        mission = saved[0] if saved else {"title": title, "description": description, "xp_reward": reward}
        text = f"⚡ *Today's Mission*\n\n{title}\n{description}\n\nReward: +{reward} XP"
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Complete mission", callback_data="mission_done")
    kb.button(text="↩️ Main menu", callback_data="home")
    kb.adjust(1)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    else:
        await target.message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "mission")
async def mission_callback(callback: CallbackQuery):
    ensure_profile(callback.from_user)
    await show_mission(callback, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data == "mission_done")
async def mission_done(callback: CallbackQuery):
    uid = callback.from_user.id
    today = date.today().isoformat()
    rows = supabase.table("daily_missions").select("*").eq("telegram_id", uid).eq("mission_date", today).limit(1).execute().data
    if not rows:
        await callback.answer("Open today's mission first.", show_alert=True)
        return
    mission = rows[0]
    if mission.get("completed"):
        await callback.answer("Mission already completed today!", show_alert=True)
        return
    supabase.table("daily_missions").update({"completed": True}).eq("id", mission["id"]).execute()
    xp, level = add_xp(uid, int(mission["xp_reward"]))
    await callback.message.answer(f"🏆 Mission complete! +{mission['xp_reward']} XP\nTotal XP: {xp} · Level {level}")
    await callback.answer("Mission cleared!")

@dp.message(Command("quiz"))
async def quiz_cmd(message: Message):
    ensure_profile(message.from_user)
    await send_quiz(message, message.from_user.id)

async def send_quiz(target, uid):
    questions = supabase.table("quiz_questions").select("*").eq("is_active", True).limit(50).execute().data
    if not questions:
        await target.answer("🧪 The question bank is empty right now. Add authorized questions to `quiz_questions` using the included SQL guide.")
        return
    # Select a question not answered correctly recently if possible.
    recent = supabase.table("quiz_attempts").select("question_id,correct").eq("telegram_id", uid).order("created_at", desc=True).limit(30).execute().data
    missed = {r["question_id"] for r in recent if not r.get("correct")}
    pool = [q for q in questions if q["id"] in missed] or questions
    q = pool[0]
    kb = InlineKeyboardBuilder()
    for i, option in enumerate(q["options"]):
        kb.button(text=f"{'ABCD'[i]}. {option}", callback_data=f"answer:{q['id']}:{i}")
    kb.adjust(1)
    await target.answer(f"🧠 *{q['subject']} · {q['topic']}*\n\n{q['question']}", reply_markup=kb.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "quiz")
async def quiz_callback(callback: CallbackQuery):
    ensure_profile(callback.from_user)
    await send_quiz(callback.message, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("answer:"))
async def answer_callback(callback: CallbackQuery):
    _, qid, choice = callback.data.split(":")
    uid = callback.from_user.id
    rows = supabase.table("quiz_questions").select("*").eq("id", qid).limit(1).execute().data
    if not rows:
        await callback.answer("Question not found.", show_alert=True)
        return
    q = rows[0]
    chosen = int(choice)
    correct = chosen == int(q["correct_index"])
    supabase.table("quiz_attempts").insert({
        "telegram_id": uid, "question_id": qid, "chosen_index": chosen,
        "correct": correct, "subject": q["subject"], "topic": q["topic"]
    }).execute()
    if correct:
        xp, level = add_xp(uid, 10)
        await callback.message.answer(f"✅ Correct! +10 XP\n\n{q.get('explanation','Review the method and note why it works.')}\n\nTotal: {xp} XP · Level {level}")
    else:
        supabase.table("mistake_memory").insert({
            "telegram_id": uid, "question_id": qid, "subject": q["subject"],
            "topic": q["topic"], "question_snapshot": q["question"],
            "explanation_snapshot": q.get("explanation", ""),
            "reviewed": False
        }).execute()
        await callback.message.answer(
            f"Not quite — saved to *Mistake Memory* 🧠\n\n"
            f"Correct answer: {'ABCD'[int(q['correct_index'])]}. {q['options'][int(q['correct_index'])]}\n"
            f"{q.get('explanation','Review this concept and try a similar question.')}",
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.message(Command("mistakes"))
async def mistakes_cmd(message: Message):
    ensure_profile(message.from_user)
    await show_mistakes(message, message.from_user.id)

async def show_mistakes(target, uid):
    rows = supabase.table("mistake_memory").select("*").eq("telegram_id", uid).eq("reviewed", False).order("created_at", desc=True).limit(5).execute().data
    if not rows:
        await target.answer("🧠 Your Mistake Memory is clear for now. Get a question wrong in Quick Quiz and it will be saved here for revision.")
        return
    lines = ["🧠 *Mistake Memory — review queue*\n"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. *{r['subject']} · {r['topic']}*\n{r['question_snapshot'][:240]}")
    kb = InlineKeyboardBuilder()
    for r in rows:
        kb.button(text=f"Reviewed: {r['topic'][:20]}", callback_data=f"reviewed:{r['id']}")
    kb.adjust(1)
    await target.answer("\n\n".join(lines), reply_markup=kb.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "mistakes")
async def mistakes_callback(callback: CallbackQuery):
    ensure_profile(callback.from_user)
    await show_mistakes(callback.message, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("reviewed:"))
async def reviewed_callback(callback: CallbackQuery):
    mid = callback.data.split(":", 1)[1]
    supabase.table("mistake_memory").update({"reviewed": True, "reviewed_at": datetime.now(timezone.utc).isoformat()}).eq("id", mid).eq("telegram_id", callback.from_user.id).execute()
    xp, level = add_xp(callback.from_user.id, 3)
    await callback.message.answer(f"📌 Marked reviewed. +3 XP for closing the learning loop. Total: {xp} XP.")
    await callback.answer()

@dp.message(Command("backlog"))
async def backlog_cmd(message: Message):
    ensure_profile(message.from_user)
    parts = message.text.split(maxsplit=1)
    if len(parts) == 1:
        await message.answer("🛟 *Backlog Rescue*\nAdd a task like:\n`/backlog Physics — 2 lectures on Kinematics`\n\nI'll save it as a task you can work through realistically.", parse_mode="Markdown")
        return
    title = parts[1][:180]
    supabase.table("backlog_tasks").insert({
        "telegram_id": message.from_user.id, "title": title,
        "status": "open", "priority": "normal"
    }).execute()
    await message.answer(f"🛟 Added to Backlog Rescue:\n*{title}*\n\nTiny rule: keep today's current lectures first; rescue old backlog in manageable blocks.", parse_mode="Markdown")

@dp.callback_query(F.data == "backlog")
async def backlog_callback(callback: CallbackQuery):
    uid = callback.from_user.id
    rows = supabase.table("backlog_tasks").select("*").eq("telegram_id", uid).eq("status", "open").order("created_at", desc=False).limit(8).execute().data
    if not rows:
        await callback.message.answer("🛟 No open backlog tasks. Add one with `/backlog Subject — task description`.", parse_mode="Markdown")
    else:
        text = "🛟 *Backlog Rescue — open tasks*\n\n" + "\n".join(f"• {r['title']}" for r in rows)
        kb = InlineKeyboardBuilder()
        for r in rows:
            kb.button(text=f"Complete: {r['title'][:22]}", callback_data=f"backlog_done:{r['id']}")
        kb.adjust(1)
        await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("backlog_done:"))
async def backlog_done(callback: CallbackQuery):
    task_id = callback.data.split(":", 1)[1]
    supabase.table("backlog_tasks").update({"status": "done", "completed_at": datetime.now(timezone.utc).isoformat()}).eq("id", task_id).eq("telegram_id", callback.from_user.id).execute()
    xp, level = add_xp(callback.from_user.id, 5)
    await callback.message.answer(f"One less thing hanging over you. +5 XP. Total: {xp} XP.")
    await callback.answer()

@dp.message(Command("resources"))
async def resources_cmd(message: Message):
    ensure_profile(message.from_user)
    await show_resources(message)

async def show_resources(target):
    rows = supabase.table("resource_links").select("title,subject,topic,url,description").eq("is_published", True).order("subject").limit(15).execute().data
    if not rows:
        await target.answer("📚 Resource Universe is ready, but no approved links have been added yet. Add official or authorized links to `resource_links`.")
        return
    lines = ["📚 *Resource Universe — approved links*\n"]
    for r in rows:
        lines.append(f"• *{r['title']}* — {r['subject']} / {r['topic']}\n{r.get('description','')}\n{r['url']}")
    await target.answer("\n\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

@dp.callback_query(F.data == "resources")
async def resources_callback(callback: CallbackQuery):
    await show_resources(callback.message)
    await callback.answer()

@dp.message(Command("progress"))
async def progress_cmd(message: Message):
    ensure_profile(message.from_user)
    await show_progress(message, message.from_user.id)

async def show_progress(target, uid):
    p = supabase.table("bot_profiles").select("*").eq("telegram_id", uid).single().execute().data
    attempts = supabase.table("quiz_attempts").select("correct").eq("telegram_id", uid).execute().data
    correct = sum(1 for a in attempts if a["correct"])
    total = len(attempts)
    mistakes = len(supabase.table("mistake_memory").select("id").eq("telegram_id", uid).eq("reviewed", False).execute().data)
    accuracy = round(correct * 100 / total) if total else 0
    await target.answer(
        f"📊 *Your Progress*\n\nXP: {p.get('xp',0)}\nLevel: {p.get('level',1)}\n"
        f"Questions attempted: {total}\nAccuracy: {accuracy}%\nOpen mistakes to review: {mistakes}\n\n"
        "Progress means learning from mistakes, not just collecting points.",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "progress")
async def progress_callback(callback: CallbackQuery):
    await show_progress(callback.message, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):
    await callback.message.answer("🚀 *Mission Control* — choose your next move:", reply_markup=menu_markup(), parse_mode="Markdown")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
