import os
import urllib.parse
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
CHOOSE_ENTITY, CHOOSE_TEMPLATE, ASK_NAME, ASK_LOCATION, ASK_CONCERN, SHOW_OUTPUT = range(6)

ENTITIES = {
    "pm": {
        "label": "Prime Minister",
        "contact": "Contact form: https://www.pm.gov.au/contact",
        "emails": None,
    },
    "parliament": {
        "label": "Parliament of Australia", 
        "contact": "Contact form: https://www.aph.gov.au/Help/Contact_Us",
        "emails": None,
    },
    "foreign_minister": {
        "label": "Minister for Foreign Affairs",
        "contact": "Contact form: https://www.foreignminister.gov.au/contact-foreign-minister", 
        "emails": None,
    },
    "dfat": {
        "label": "Department of Foreign Affairs",
        "contact": None,
        "emails": ["media@dfat.gov.au", "legalisations.australia@dfat.gov.au", "lara.nassau@dfat.gov.au"],
    },
    "oni": {
        "label": "Office of National Intelligence",
        "contact": None,
        "emails": ["info@igis.gov.au", "hotline@nationalsecurity.gov.au"],
    },
    "us_embassy": {
        "label": "US Embassy in Australia",
        "contact": None,
        "emails": ["SydneyACS@state.gov"],
    },
}

TEMPLATES = {
    "short": {"label": "Short"},
    "formal": {"label": "Formal"},
    "detailed": {"label": "Detailed"},
}

@dataclass
class SessionData:
    entity_key: str = ""
    template_key: str = ""
    name: str = ""
    location: str = ""
    concern: str = ""

def build_subject(entity_key: str) -> str:
    subjects = {
        "pm": "Urgent: Human Rights Concerns Regarding Iran",
        "parliament": "Parliamentary Inquiry Request: Australia's Iran Policy",
        "foreign_minister": "Foreign Policy Review: Australia's Engagement with Iran",
        "dfat": "Request: Human Rights-Based Review of Australia's Engagement with Iran",
        "oni": "Intelligence Assessment Request: Iran Human Rights Situation",
        "us_embassy": "Urgent: Request for US Intervention on Iran Human Rights Crisis",
    }
    return subjects.get(entity_key, "Human Rights Concerns Regarding Iran")

def build_email_body(entity_key: str, template_key: str, name: str, location: str, concern: str) -> str:
    signoff = name if name else "A concerned Australian citizen"
    loc_line = f"\n{location}" if location else ""
    
    concern_sentence = ""
    if concern.strip():
        concern_clean = concern.strip().replace("\n", " ")
        concern_sentence = f"I am particularly concerned about: {concern_clean}\n\n"

    # Entity-specific greetings and content
    greetings = {
        "pm": "Dear Prime Minister,",
        "parliament": "Dear Members of Parliament,", 
        "foreign_minister": "Dear Minister,",
        "dfat": "Dear Sir or Madam,",
        "oni": "Dear Intelligence Officials,",
        "us_embassy": "Dear US Embassy Officials,",
    }
    
    greeting = greetings.get(entity_key, "Dear Sir or Madam,")
    
    if template_key == "short":
        if entity_key == "us_embassy":
            return f"""{greeting}

I am writing to urgently request US government intervention regarding the mass killing of protesters in Iran by the Islamic Republic regime.

{concern_sentence}I respectfully urge the United States to take immediate action to stop these atrocities and hold the Iranian regime accountable for crimes against humanity.

Thank you for your urgent attention.

Yours sincerely,
{signoff}{loc_line}"""
        
        return f"""{greeting}

I am writing to express serious concerns about human rights violations in Iran and urge a principled Australian response.

{concern_sentence}I respectfully request that Australia review its diplomatic engagement with the Islamic Republic and engage with credible Iranian civil society representatives.

Thank you for your attention.

Yours sincerely,
{signoff}{loc_line}"""

    elif template_key == "detailed":
        return f"""{greeting}

I write to request that the Australian Government adopt a comprehensive, human-rights-centred approach regarding Iran. Credible reporting by international bodies has documented serious concerns about the suppression of fundamental freedoms and due process.

{concern_sentence}In light of these concerns, I respectfully ask Australia to:
1) Review the basis of diplomatic engagement with the Islamic Republic in view of persistent human rights violations;
2) Engage in structured dialogue with credible democratic opposition figures and Iranian civil society representatives;
3) Support accountability measures consistent with Australia's commitment to human rights and the UN Charter.

Thank you for considering this important matter.

Yours sincerely,
{signoff}{loc_line}"""

    # Default "formal" template
    return f"""{greeting}

I am writing to urge the Australian Government to take a principled stance in response to credible reports of ongoing human rights violations in Iran.

{concern_sentence}I respectfully ask the Government to review the political legitimacy it affords the Islamic Republic through diplomatic engagement, and to engage with credible democratic opposition figures and representatives of Iranian civil society as part of a human-rights-based foreign policy.

Such steps would affirm that sustained repression cannot coexist with full political legitimacy.

Thank you for your attention.

Yours sincerely,
{signoff}{loc_line}"""

def make_entity_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(ENTITIES["pm"]["label"], callback_data="entity:pm")],
        [InlineKeyboardButton(ENTITIES["parliament"]["label"], callback_data="entity:parliament")],
        [InlineKeyboardButton(ENTITIES["foreign_minister"]["label"], callback_data="entity:foreign_minister")],
        [InlineKeyboardButton(ENTITIES["dfat"]["label"], callback_data="entity:dfat")],
        [InlineKeyboardButton(ENTITIES["oni"]["label"], callback_data="entity:oni")],
        [InlineKeyboardButton(ENTITIES["us_embassy"]["label"], callback_data="entity:us_embassy")],
    ]
    return InlineKeyboardMarkup(buttons)

def make_template_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(TEMPLATES["short"]["label"], callback_data="tpl:short")],
        [InlineKeyboardButton(TEMPLATES["formal"]["label"], callback_data="tpl:formal")],
        [InlineKeyboardButton(TEMPLATES["detailed"]["label"], callback_data="tpl:detailed")],
    ]
    return InlineKeyboardMarkup(buttons)

def ensure_session(context: ContextTypes.DEFAULT_TYPE) -> SessionData:
    if "session" not in context.user_data:
        context.user_data["session"] = SessionData()
    return context.user_data["session"]

async def handle_start_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    logger.info(f"User interaction: user_id={user_id}, chat_id={chat_id}, text={update.effective_message.text if update.effective_message else None}")
    
    logger.info(f"Received message: {update.message.text}")
    text = update.message.text.strip().lower()
    if text in ["start", "/start"]:
        logger.info("Starting conversation")
        return await start(update, context)
    logger.info("Message not recognized as start")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id if update.effective_user else None
    logger.info(f"Start function called for user_id={user_id}")
    ensure_session(context)
    await update.message.reply_text(
        "Hi! I can help you contact Australian Government entities about human rights concerns regarding Iran.\n\n"
        "Choose who you want to contact:",
        reply_markup=make_entity_keyboard(),
    )
    logger.info("Start message sent")
    return CHOOSE_ENTITY

async def on_entity_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    session = ensure_session(context)
    entity_key = query.data.split(":", 1)[1]
    session.entity_key = entity_key

    # Send new message instead of editing
    await update.effective_chat.send_message(
        f"Entity selected: {ENTITIES[entity_key]['label']}\n\n"
        "Choose message style:",
        reply_markup=make_template_keyboard(),
    )
    return CHOOSE_TEMPLATE

async def on_template_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    session = ensure_session(context)
    template_key = query.data.split(":", 1)[1]
    session.template_key = template_key

    # Send new message instead of editing
    await update.effective_chat.send_message(
        f"Style selected: {TEMPLATES[template_key]['label']}\n\n"
        "What's your name? (Optional — reply with your name, or type skip)"
    )
    return ASK_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    text = update.message.text.strip()
    
    if text.lower() in ["skip", "/skip"]:
        session.name = ""
    else:
        session.name = text[:80]
    
    try:
        entity_label = ENTITIES[session.entity_key]['label']
        template_label = TEMPLATES[session.template_key]['label']
    except KeyError as e:
        logger.error(f"Invalid session state: {e}")
        await update.message.reply_text("Session error. Please start over with /start")
        return ConversationHandler.END
    name_info = f"Name: {session.name}" if session.name else "Name: (skipped)"
    
    await update.message.reply_text(
        f"📋 **Current Selection:**\n"
        f"Entity: {entity_label}\n"
        f"Style: {template_label}\n"
        f"{name_info}\n\n"
        "Your city/state? (Optional — e.g., Sydney, NSW. Or type skip)",
        parse_mode="Markdown"
    )
    return ASK_LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    text = update.message.text.strip()
    
    if text.lower() in ["skip", "/skip"]:
        session.location = ""
    else:
        session.location = text[:80]
    
    try:
        entity_label = ENTITIES[session.entity_key]['label']
        template_label = TEMPLATES[session.template_key]['label']
    except KeyError as e:
        logger.error(f"Invalid session state: {e}")
        await update.message.reply_text("Session error. Please start over with /start")
        return ConversationHandler.END
    name_info = f"Name: {session.name}" if session.name else "Name: (skipped)"
    location_info = f"Location: {session.location}" if session.location else "Location: (skipped)"
    
    await update.message.reply_text(
        f"📋 **Current Selection:**\n"
        f"Entity: {entity_label}\n"
        f"Style: {template_label}\n"
        f"{name_info}\n"
        f"{location_info}\n\n"
        "One-line concern to include? (Optional — or type skip)",
        parse_mode="Markdown"
    )
    return ASK_CONCERN

async def get_concern(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    text = update.message.text.strip()
    
    if text.lower() in ["skip", "/skip"]:
        session.concern = ""
    else:
        session.concern = text[:240]
    
    return await show_output(update, context)

async def show_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session = ensure_session(context)
    user_id = update.effective_user.id if update.effective_user else None
    logger.info(f"Message generated for user_id={user_id}, entity={session.entity_key}, template={session.template_key}")
    
    try:
        entity = ENTITIES[session.entity_key]
        subject = build_subject(session.entity_key)
        body = build_email_body(session.entity_key, session.template_key, session.name, session.location, session.concern)
    except KeyError as e:
        logger.error(f"Invalid session state: {e}")
        await update.message.reply_text("Session error. Please start over with /start")
        return ConversationHandler.END

    logger.info(f"Generated subject: {subject}")
    logger.info(f"Generated body length: {len(body)}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Start over", callback_data="restart")],
    ])

    if entity["emails"]:
        recipients = "\n".join(entity["emails"])
        contact_info = f"**To:**\n`{recipients}`"
    else:
        contact_info = f"**Contact:**\n{entity['contact']}"

    text = (
        f"✅ Here's your message for {entity['label']}.\n\n"
        f"{contact_info}\n\n"
        f"**Subject:**\n`{subject}`\n\n"
        f"**Message:**\n`{body}`\n\n"
        "Copy the text above and paste into your email app or contact form."
    )

    logger.info(f"Sending message with length: {len(text)}")

    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info("Message sent successfully")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        # Try without markdown if it fails
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        else:
            await update.message.reply_text(text, reply_markup=keyboard)

    return SHOW_OUTPUT

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["session"] = SessionData()
    
    # Send new message instead of editing
    await update.effective_chat.send_message(
        "Choose who you want to contact:", 
        reply_markup=make_entity_keyboard()
    )
    return CHOOSE_ENTITY

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Type 'start' to begin again.")
    return ConversationHandler.END


def main() -> None:
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ENTITY: [CallbackQueryHandler(on_entity_chosen, pattern=r"^entity:")],
            CHOOSE_TEMPLATE: [CallbackQueryHandler(on_template_chosen, pattern=r"^tpl:")],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
            ASK_CONCERN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_concern)],
            SHOW_OUTPUT: [CallbackQueryHandler(restart, pattern=r"^restart$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )

    app.add_handler(conv)
    
    # Add handler for messages outside conversation
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_start_text))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()