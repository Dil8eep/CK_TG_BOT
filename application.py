import asyncio
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, CallbackContext, filters
)

# 🔹 Telegram Bot Token
TOKEN = "7774060581:AAGHejkowSwVMP-5YuPONHdHuujquvJaCKo"

# 🔹 Google Sheets Setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "global-standard-449604-u7-524c4fc817f7.json"
SPREADSHEET_NAME = "jobsApplications"

credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
gc = gspread.authorize(credentials)
sheet = gc.open(SPREADSHEET_NAME).sheet1

# 🔹 In-memory user state tracking
user_data = {}

# 🔹 Admin Telegram IDs
ADMINS = [5686251645]

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Welcome to the Job Bot!\nUse /jobs to see job postings.\nUse /subscribe to get job alerts!"
    )

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📌 *Available Commands:*\n"
        "/start - Start the bot\n"
        "/jobs - View job postings\n"
        "/postjob - Post a job (Admin only)\n"
        "/settings - Update your preferences\n"
        "/help - Show this help message",
        parse_mode="Markdown"
    )

async def settings(update: Update, context: CallbackContext):
    await update.message.reply_text("⚙️ Settings feature coming soon!")

async def jobs(update: Update, context: CallbackContext):
    try:
        # Access the correct spreadsheet and sheet
        jobs_sheet = gc.open("Jobs").worksheet("Jobs")  # change "Jobs" to your actual sheet name
        jobs_data = jobs_sheet.get_all_records()

        if not jobs_data:
            await update.message.reply_text("🚫 No job postings available at the moment.")
            return

        for job in jobs_data[-3:]:  # Show only the latest 3 jobs
            job_details = (
                "📢 *New Job Available!*\n\n"
                f"🔹 *Role:* {job.get('role')}\n"
                f"🛠 *Skills:* {job.get('skills')}\n"
                f"📍 *Location:* {job.get('location')}\n"
                f"💰 *Salary:* {job.get('salary')}\n"
            )

            job_url = job.get("url", "https://codekrafters.in/career")
            keyboard = [[
                InlineKeyboardButton("✅ Interested", callback_data="interest"),
                InlineKeyboardButton("🔗 View Job", url=job_url)
            ]]
            await update.message.reply_text(
                job_details, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        await update.message.reply_text(f"⚠ Error fetching jobs: {e}")


# ──────── Job Posting (Admin Only) ────────

JOB_FORM_FIELDS = ["role", "skills", "location", "salary", "url"]

async def post_job(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if update.message.chat.type != "private":
        await update.message.reply_text("⚠ This command can only be used in private chat.")
        return

    if user_id not in ADMINS:
        await update.message.reply_text("❌ You are not authorized to post jobs.")
        return

    user_data[user_id] = {"form_step": 0, "job_data": {}}

    await update.message.reply_text("📋 Let's create a new job posting!")
    await update.message.reply_text("🔹 Please enter the *Role* (e.g., Software Engineer):", parse_mode="Markdown")
    # 🔹 Notify Users with Matching Subscriptions
#     await notify_subscribers(job)


from telegram import Update
from telegram.ext import ContextTypes

# Global user_data dictionary if not already defined
user_data = {}

async def handle_interest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data[user_id] = {
        "waiting_for_name": True,
        "waiting_for_email": False,
        "waiting_for_phone": False,
        "waiting_for_resume": False,
        "waiting_for_confirmation": False,
        "edit_field": None,
    }

    await query.message.reply_text("👤 Please enter your *full name*:", parse_mode="Markdown")

import re
import time

# Rate limiting tracker
cooldown_tracker = {}
COOLDOWN_SECONDS = 5  # Adjust as needed

# Admin ID list
ADMIN_IDS = [5686251645]  # Replace with actual Telegram user IDs


def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_valid_phone(phone):
    return phone.isdigit() and len(phone) == 10


async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text.strip().lower() if update.message.text else ""
    user = user_data.get(user_id, {})

    # ─────── Edit Command ───────
    if text.startswith("edit "):
        field = text.split(" ", 1)[1]
        if field in ["name", "email", "phone"]:
            user["edit_field"] = field
            await update.message.reply_text(f"✏ Please enter your new *{field}*:", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Unknown field. You can edit: name, email, phone.")
        return

    if user.get("edit_field"):
        field = user["edit_field"]
        if field == "email" and not is_valid_email(text):
            await update.message.reply_text("❌ Invalid email format. Try again:")
            return
        if field == "phone" and not is_valid_phone(text):
            await update.message.reply_text("❌ Phone number must be 10 digits. Try again:")
            return
        user[field] = text
        del user["edit_field"]
        await update.message.reply_text(f"✅ *{field}* updated successfully!", parse_mode="Markdown")
        return

    # ─────── Rate Limiting ───────
    now = time.time()
    if user_id in cooldown_tracker and now - cooldown_tracker[user_id] < COOLDOWN_SECONDS:
        await update.message.reply_text("⏳ Please wait a moment before sending another message.")
        return
    cooldown_tracker[user_id] = now

    # ─────── Job Posting Flow ───────
    if "form_step" in user:
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("🚫 You are not authorized to post jobs.")
            return

        step = user["form_step"]
        key = JOB_FORM_FIELDS[step]
        user["job_data"][key] = text
        user["form_step"] += 1

        if user["form_step"] < len(JOB_FORM_FIELDS):
            next_key = JOB_FORM_FIELDS[user["form_step"]]
            prompts = {
                "skills": "🛠 Enter required *Skills* (comma separated):",
                "location": "📍 Enter the *Location* of the job:",
                "salary": "💰 Enter the *Salary* offered:",
                "url": "🔗 Optional: Enter the *Job URL* (or type 'skip'):"
            }
            await update.message.reply_text(prompts[next_key], parse_mode="Markdown")
        else:
            job = user["job_data"]
            job_url = job["url"] if job["url"].lower() != "skip" else "https://codekrafters.in/career"

            job_post = (
                "📢 *New Job Available!*\n\n"
                f"🔹 *Role:* {job['role']}\n"
                f"🛠 *Skills:* {job['skills']}\n"
                f"📍 *Location:* {job['location']}\n"
                f"💰 *Salary:* {job['salary']}\n"
            )

            keyboard = [[
                InlineKeyboardButton("✅ Interested", callback_data="interest"),
                InlineKeyboardButton("🔗 View Job", url=job_url)
            ]]
            await update.message.reply_text(job_post, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

            try:
                jobs_sheet = gc.open("Jobs").worksheet("Jobs")
                jobs_sheet.append_row([
                    job['role'],
                    job['skills'],
                    job['location'],
                    job['salary'],
                    job_url
                ])
                await update.message.reply_text("✅ Job has been posted and saved to Google Sheets!")
            except Exception as e:
                await update.message.reply_text(f"⚠ Error saving job to sheet: {e}")

            user_data.pop(user_id, None)
        return

    # ─────── Interest Form Flow ───────
    if user.get("waiting_for_name"):
        user["name"] = update.message.text
        user["waiting_for_name"] = False
        user["waiting_for_email"] = True
        await update.message.reply_text("📧 Enter your *email address*:", parse_mode="Markdown")

    elif user.get("waiting_for_email"):
        if not is_valid_email(update.message.text):
            await update.message.reply_text("❌ Invalid email format. Please try again:")
            return
        user["email"] = update.message.text
        user["waiting_for_email"] = False
        user["waiting_for_phone"] = True
        await update.message.reply_text("📱 Enter your *phone number*:", parse_mode="Markdown")

    elif user.get("waiting_for_phone"):
        if not is_valid_phone(update.message.text):
            await update.message.reply_text("❌ Phone number must be 10 digits. Please try again:")
            return
        user["phone"] = update.message.text
        user["waiting_for_phone"] = False
        user["waiting_for_resume"] = True
        await update.message.reply_text("📄 Upload your *resume* as a file:", parse_mode="Markdown")

    elif user.get("waiting_for_resume"):
        if update.message.document:
            file_name = update.message.document.file_name
            if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
                await update.message.reply_text("❌ Invalid file type. Please upload a .pdf or .docx resume.")
                return

            bot = Bot(TOKEN)
            file = await bot.get_file(update.message.document.file_id)
            file_url = file.file_path
            user["resume_url"] = file_url
            user["waiting_for_resume"] = False
            user["waiting_for_confirmation"] = True

            await update.message.reply_text(
                "📝 *Please confirm your submission:*\n\n"
                f"👤 *Name:* {user['name']}\n"
                f"📧 *Email:* {user['email']}\n"
                f"📱 *Phone:* {user['phone']}\n"
                f"📄 *Resume:* [Download]({file_url})\n\n"
                "✅ Type *confirm* to submit.\n"
                "✏ Or type *edit [field]* (e.g., `edit email`).",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠ Please upload a valid resume file.")

    elif user.get("waiting_for_confirmation"):
        if text == "confirm":
            try:
                sheet.append_row([
                    user["name"],
                    user["email"],
                    user["phone"],
                    user["resume_url"]
                ])
                await update.message.reply_text(
                    "🎉 *Thank you for your interest!*\n\n"
                    "✅ Your form has been submitted *successfully*.\n"
                    "📬 Our team will review your information and get in touch with you *soon* if your profile matches our requirements.\n\n"
                    "We appreciate you taking the time to apply. Have a great day! 🌟",
                    parse_mode="Markdown"
                )
            except Exception as e:
                await update.message.reply_text(f"⚠ Error saving to Google Sheets: {e}")
            finally:
                user_data.pop(user_id, None)
        else:
            await update.message.reply_text("❌ Type *confirm* to submit, or use `edit [field]` to change something.")

# ──────── Main Application ────────

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("jobs", jobs))
    app.add_handler(CommandHandler("postjob", post_job))

    app.add_handler(CallbackQueryHandler(handle_interest, pattern="^interest$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_message))

    print("🚀 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())       

