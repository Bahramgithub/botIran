import os
import urllib.parse
from dataclasses import dataclass
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# --- Conversation states ---
CHOOSE_TEMPLATE, ASK_NAME, ASK_LOCATION, ASK_CONCERN, SHOW_OUTPUT = range(5)

TEMPLATES = {
    "very_short": {
        "label": "Very short",
        "subject": "Request: Human Rights-Based Review of Australia's Engagement with Iran",
    },
    "formal": {
        "label": "Formal",
        "subject": "Request for Australia to Review Political Legitimacy Afforded to the Islamic Republic of Iran",
    },
    "legal": {
        "label": "More legal",
        "subject": "Request for Values-Based Action on Iran: Human Rights, Accountability, and Engagement with Civil Society",
    },
}

@dataclass
class SessionData:
    template_key: str = "formal"
    name: str = ""
    location: str = ""
    concern: str = ""
    subject: str = ""
    body: str = ""


def build_email_body(template_key: str, name: str, location: str, concern: str) -> str:
    name_line = f"{name}" if name else ""
    signoff = name_line if name_line else "A concerned member of the public"
    loc_line = f"{location}" if location else ""

    concern_sentence = ""
    if concern.strip():
        concern_clean = concern.strip().replace("\n", " ")
        concern_sentence = f"I am particularly concerned about: {concern_clean}\n\n"

    if template_key == "very_short":
        return (
            "Dear Sir or Madam,\n\n"
            "I am writing to urge the Australian Government to take a principled, human-rights-based stance in response to "
            "credible reports of serious and ongoing abuses in Iran.\n\n"
            f"{concern_sentence}"
            "I respectfully ask Australia to review the basis of its diplomatic engagement with the Islamic Republic, "
            "and to engage with credible democratic voices and Iranian civil society in a manner consistent with human rights and accountability.\n\n"
            "Thank you for your attention.\n\n"
            f"Yours sincerely,\n{signoff}"
            + (f"\n{loc_line}" if loc_line else "")
        )

    if template_key == "legal":
        return (
            "Dear Sir or Madam,\n\n"
            "I write to request that the Australian Government adopt a values-based and human-rights-centred approach regarding Iran. "
            "Credible reporting by international bodies and human rights organisations has raised serious concerns about the suppression of "
            "fundamental freedoms and due process.\n\n"
            f"{concern_sentence}"
            "In light of these concerns, I respectfully ask Australia to:\n"
            "1) Review the basis and public framing of diplomatic engagement with the Islamic Republic in view of persistent human rights violations; and\n"
            "2) Engage in structured dialogue with credible democratic opposition figures and representatives of Iranian civil society, consistent with "
            "Australia's commitment to human rights, accountability, and the principles of the UN Charter.\n\n"
            "Thank you for considering this request.\n\n"
            f"Yours sincerely,\n{signoff}"
            + (f"\n{loc_line}" if loc_line else "")
        )

    return (
        "Dear Sir or Madam,\n\n"
        "I am writing to urge the Australian Government to take a principled stance in response to credible reports of ongoing human rights "
        "violations in Iran.\n\n"
        f"{concern_sentence}"
        "I respectfully ask the Government to review the political legitimacy it affords the Islamic Republic through diplomatic engagement, "
        "and to engage with credible democratic opposition figures and representatives of Iranian civil society as part of a human-rights-based foreign policy.\n\n"
        "Such steps would affirm that sustained repression cannot coexist with full political legitimacy.\n\n"
        "Thank you for your attention.\n\n"
        f"Yours sincerely,\n{signoff}"
        + (f"\n{loc_line}" if loc_line else "")
    )


def make_template_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(TEMPLATES["very_short"]["label"], callback_data="tpl:very_short")],
        [InlineKeyboardButton(TEMPLATES["formal"]["label"], callback_data="tpl:formal")],
        [InlineKeyboardButton(TEMPLATES["legal"]["label"], callback_data="tpl:legal")],
    ]
    return InlineKeyboardMarkup(buttons)


def ensure_session(context: ContextTypes.DEFAULT_TYPE) -> SessionData:
    if "session" not in context.user_data:
        context.user_data["session"] = SessionData()
    return context.user_data["session"]


async def handle_start_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    if text in ["start", "/start"]:
        return await start(update, context)
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ensure_session(context)
    await update.message.reply_text(
        "Hi! I can generate a short, rights-based email you can send to the Australian Government.\n\n"
        "Choose a template:",
        reply_markup=make_template_keyboard(),
    )
    return CHOOSE_TEMPLATE


async def on_template_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    session = ensure_session(context)
    tpl_key = query.data.split(":", 1)[1]
    if tpl_key not in TEMPLATES:
        tpl_key = "formal"
    session.template_key = tpl_key

    await query.edit_message_text(
        f"Template selected: {TEMPLATES[tpl_key]['label']}\n\n"
        "What's your name? (Optional — reply with your name, or type /skip)"
    )
    return ASK_NAME


async def skip_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    session.name = ""
    await update.message.reply_text("Your city/state? (Optional — e.g., Sydney, NSW. Or type /skip)")
    return ASK_LOCATION


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    text = update.message.text.strip()
    
    # Allow both "skip" and "/skip"
    if text.lower() in ["skip", "/skip"]:
        session.name = ""
    else:
        session.name = text[:80]
    
    await update.message.reply_text("Your city/state? (Optional — e.g., Sydney, NSW. Or type /skip)")
    return ASK_LOCATION


async def skip_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    session.location = ""
    await update.message.reply_text("One-line concern to include? (Optional — e.g., 'use of lethal force against peaceful protesters'. Or type /skip)")
    return ASK_CONCERN


async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    text = update.message.text.strip()
    
    # Allow both "skip" and "/skip"
    if text.lower() in ["skip", "/skip"]:
        session.location = ""
    else:
        session.location = text[:80]
    
    await update.message.reply_text("One-line concern to include? (Optional — or type /skip)")
    return ASK_CONCERN


async def skip_concern(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    session.concern = ""
    return await show_output(update, context)


async def get_concern(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    text = update.message.text.strip()
    
    # Allow both "skip" and "/skip"
    if text.lower() in ["skip", "/skip"]:
        session.concern = ""
    else:
        session.concern = text[:240]
    
    return await show_output(update, context)


def make_mailto(subject: str, body: str, to_addr: str = "") -> str:
    qs = urllib.parse.urlencode({
        "subject": subject,
        "body": body,
    })
    return f"mailto:{to_addr}?{qs}"


async def show_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    subject = TEMPLATES[session.template_key]["subject"]
    body = build_email_body(session.template_key, session.name, session.location, session.concern)

    session.subject = subject
    session.body = body

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Start over", callback_data="restart")],
    ])

    text = (
        "✅ Here's your email draft.\n\n"
        f"**Subject:**\n`{subject}`\n\n"
        f"**Body:**\n`{body}`\n\n"
        "Tap and hold to copy the text above."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

    return SHOW_OUTPUT


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["session"] = SessionData()
    await query.edit_message_text("Choose a template:", reply_markup=make_template_keyboard())
    return CHOOSE_TEMPLATE


def main() -> None:
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_start_text),
        ],
        states={
            CHOOSE_TEMPLATE: [CallbackQueryHandler(on_template_chosen, pattern=r"^tpl:")],
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
                CommandHandler("skip", skip_name),
            ],
            ASK_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_location),
                CommandHandler("skip", skip_location),
            ],
            ASK_CONCERN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_concern),
                CommandHandler("skip", skip_concern),
            ],
            SHOW_OUTPUT: [CallbackQueryHandler(restart, pattern=r"^restart$")],
        },
        fallbacks=[],
        per_message=False,
    )

    app.add_handler(conv)
    
    # Use polling for now to avoid webhook complexity
    app.run_polling()


if __name__ == "__main__":
    main()