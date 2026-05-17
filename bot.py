"""
bot.py - Main Telegram bot entry point and all handler implementations.

Architecture:
- All handlers are async (python-telegram-bot v20+)
- State machine for registration via user_data
- In-memory mapping for fast chat lookups (backed by DB for persistence)
- Rate limiting via per-user timestamps
- Admin relay: all messages copied to ADMIN_TELEGRAM_ID
"""

import os
import re
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, Bot
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

from database import (
    init_db, get_session_factory,
    UserRepo, ChatRepo, QueueRepo, ReportRepo, BlockRepo, HistoryRepo,
    GenderEnum, LanguageEnum, MessageTypeEnum, ChatStatus
)
import messages as msg

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///anonchat.db")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))  # Set your Telegram ID!
AUTO_BAN_THRESHOLD = 3  # Reports before auto-ban

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Registration States ──────────────────────────────────────────────────────

(
    REG_ALIAS, REG_AGE, REG_GENDER, REG_INTERESTS, REG_BIO,
    FEEDBACK_STATE, CONFIRM_DELETE_STATE,
    EDIT_CHOOSE, EDIT_VALUE,
) = range(9)

# ─── In-memory lookups (mirrors DB for speed) ─────────────────────────────────
# user_id -> partner_id (for active chats)
active_pairs: Dict[int, int] = {}
# user_id -> chat_id
user_chat_ids: Dict[int, str] = {}
# user_id -> timestamp of last message (rate limiting)
last_message_time: Dict[int, datetime] = {}
# user_id -> bool (first photo sent flag)
first_photo_sent: Dict[int, bool] = {}
# user_id -> bool (currently in queue)
in_queue: set = set()

# ─── Profanity filter (basic) ─────────────────────────────────────────────────
try:
    from better_profanity import profanity
    profanity.load_censor_words()
    PROFANITY_ENABLED = True
except ImportError:
    PROFANITY_ENABLED = False
    logger.warning("better-profanity not installed; profanity filter disabled.")

AMHARIC_BAD_WORDS = []  # Add Amharic bad words here as a list of strings


def contains_profanity(text: str) -> bool:
    if not text:
        return False
    if PROFANITY_ENABLED and profanity.contains_profanity(text):
        return True
    lower = text.lower()
    return any(w in lower for w in AMHARIC_BAD_WORDS)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def session_maker():
    return get_session_factory(DATABASE_URL)


async def get_user(telegram_id: int):
    async with session_maker()() as session:
        return await UserRepo(session).get(telegram_id)


async def is_banned(telegram_id: int) -> bool:
    user = await get_user(telegram_id)
    return user is not None and user.is_banned


async def require_registered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user is registered and not banned. Send error otherwise."""
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if user is None:
        await update.effective_message.reply_text(msg.NOT_REGISTERED, parse_mode=ParseMode.MARKDOWN)
        return False
    if user.is_banned:
        reason = user.ban_reason or "Policy violation"
        await update.effective_message.reply_text(
            msg.BANNED_MESSAGE.format(reason=reason), parse_mode=ParseMode.MARKDOWN
        )
        return False
    return True


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def send_admin(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode=ParseMode.MARKDOWN):
    """Send a message to admin silently (ignore errors)."""
    if ADMIN_ID:
        try:
            await context.bot.send_message(ADMIN_ID, text, parse_mode=parse_mode)
        except TelegramError:
            pass


async def relay_to_admin(context, chat_id: str, sender_alias: str, msg_type: str, content: str):
    """Relay all chat messages to admin for monitoring."""
    text = msg.ADMIN_CHAT_RELAY(chat_id, sender_alias, msg_type, content)
    await send_admin(context, text, parse_mode=ParseMode.MARKDOWN)


async def end_chat_for_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    notify_text: str
):
    """Disconnect a user from their chat and notify them."""
    partner_id = active_pairs.pop(user_id, None)
    chat_id = user_chat_ids.pop(user_id, None)
    first_photo_sent.pop(user_id, None)

    # Notify user
    try:
        await context.bot.send_message(user_id, notify_text, parse_mode=ParseMode.MARKDOWN)
    except TelegramError:
        pass

    # End chat in DB
    if chat_id:
        async with session_maker()() as session:
            await ChatRepo(session).end_chat(chat_id)

    return partner_id, chat_id


async def match_users(context: ContextTypes.DEFAULT_TYPE, user1_id: int, user2_id: int):
    """Finalize a match between two users."""
    chat_id = str(uuid.uuid4())[:12]  # Short unique ID

    # Remove both from queue
    async with session_maker()() as session:
        qr = QueueRepo(session)
        await qr.remove(user1_id)
        await qr.remove(user2_id)
        # Record in DB
        cr = ChatRepo(session)
        await cr.create(chat_id, user1_id, user2_id)
        # Record match history (prevent re-match)
        hr = HistoryRepo(session)
        await hr.add(user1_id, user2_id)
        # Get aliases
        ur = UserRepo(session)
        u1 = await ur.get(user1_id)
        u2 = await ur.get(user2_id)

    in_queue.discard(user1_id)
    in_queue.discard(user2_id)

    # Update in-memory state
    active_pairs[user1_id] = user2_id
    active_pairs[user2_id] = user1_id
    user_chat_ids[user1_id] = chat_id
    user_chat_ids[user2_id] = chat_id
    first_photo_sent[user1_id] = False
    first_photo_sent[user2_id] = False

    alias1 = u1.alias if u1 else "Anonymous"
    alias2 = u2.alias if u2 else "Anonymous"

    # Send safety warning to BOTH users (mandatory)
    warning1 = msg.SAFETY_WARNING(alias2)
    warning2 = msg.SAFETY_WARNING(alias1)

    try:
        await context.bot.send_message(user1_id, warning1, parse_mode=ParseMode.MARKDOWN_V2)
    except TelegramError as e:
        logger.error(f"Could not send safety warning to {user1_id}: {e}")

    try:
        await context.bot.send_message(user2_id, warning2, parse_mode=ParseMode.MARKDOWN_V2)
    except TelegramError as e:
        logger.error(f"Could not send safety warning to {user2_id}: {e}")

    # Notify admin
    await send_admin(
        context,
        f"🟢 New chat `{chat_id}` started: *{alias1}* ↔ *{alias2}*"
    )

    logger.info(f"Matched {user1_id} ({alias1}) with {user2_id} ({alias2}) | chat_id={chat_id}")


async def try_match_from_queue(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Try to find a match for user_id from the waiting queue."""
    async with session_maker()() as session:
        user = await UserRepo(session).get(user_id)
        block_repo = BlockRepo(session)
        blocked_ids = await block_repo.get_blocked_ids(user_id)
        hist_repo = HistoryRepo(session)

        # Build exclusion list: blocked + already matched
        exclude = list(set(blocked_ids))

        candidates = await QueueRepo(session).get_waiting(user_id, exclude)

    for candidate in candidates:
        cid = candidate.user_id
        # Skip if they've matched before
        async with session_maker()() as session:
            already = await HistoryRepo(session).have_matched(user_id, cid)
        if already:
            continue

        # Apply gender preference (if set)
        if user and user.pref_gender and user.pref_gender != "any":
            async with session_maker()() as session:
                candidate_user = await UserRepo(session).get(cid)
            if candidate_user and candidate_user.gender:
                if candidate_user.gender.value != user.pref_gender:
                    continue

        # Found a valid match!
        await match_users(context, user_id, cid)
        return True

    return False  # No match found yet


# ─── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if user and user.is_banned:
        await update.message.reply_text(
            msg.BANNED_MESSAGE.format(reason=user.ban_reason or "Policy violation"),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    if user:
        await update.message.reply_text(msg.ALREADY_REGISTERED, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg.WELCOME, parse_mode=ParseMode.MARKDOWN)


# ─── /register ─────────────────────────────────────────────────────────────────

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = await get_user(user_id)
    if existing:
        await update.message.reply_text(msg.ALREADY_REGISTERED, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    if existing and existing.is_banned:
        await update.message.reply_text(
            msg.BANNED_MESSAGE.format(reason=existing.ban_reason or "Violation"),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    await update.message.reply_text(msg.REG_ASK_ALIAS, parse_mode=ParseMode.MARKDOWN)
    return REG_ALIAS


async def reg_got_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alias = update.message.text.strip()
    if not re.match(r'^[\w\s]{2,32}$', alias):
        await update.message.reply_text(msg.REG_ALIAS_INVALID, parse_mode=ParseMode.MARKDOWN)
        return REG_ALIAS
    context.user_data['alias'] = alias
    await update.message.reply_text(msg.REG_ASK_AGE, parse_mode=ParseMode.MARKDOWN)
    return REG_AGE


async def reg_got_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/skip":
        context.user_data['age'] = None
    else:
        try:
            age = int(text)
            if not (13 <= age <= 99):
                raise ValueError
            context.user_data['age'] = age
        except ValueError:
            await update.message.reply_text(msg.REG_AGE_INVALID, parse_mode=ParseMode.MARKDOWN)
            return REG_AGE

    keyboard = [
        [InlineKeyboardButton("👨 Male", callback_data="gender_male"),
         InlineKeyboardButton("👩 Female", callback_data="gender_female")],
        [
         InlineKeyboardButton("🤐 Prefer not to say", callback_data="gender_prefer_not")],
    ]
    await update.message.reply_text(
        msg.REG_ASK_GENDER,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return REG_GENDER


async def reg_got_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gender_map = {
        "gender_male": GenderEnum.male,
        "gender_female": GenderEnum.female,
        "gender_other": GenderEnum.other,
        "gender_prefer_not": GenderEnum.prefer_not,
    }
    context.user_data['gender'] = gender_map.get(query.data, GenderEnum.prefer_not)
    await query.edit_message_text(msg.REG_ASK_INTERESTS, parse_mode=ParseMode.MARKDOWN)
    return REG_INTERESTS


async def reg_got_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/skip":
        context.user_data['interests'] = None
    else:
        tags = [t.strip()[:20] for t in text.split(",") if t.strip()][:5]
        context.user_data['interests'] = ",".join(tags) if tags else None
    await update.message.reply_text(msg.REG_ASK_BIO, parse_mode=ParseMode.MARKDOWN)
    return REG_BIO


async def reg_got_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/skip":
        bio = None
    elif len(text) > 150:
        await update.message.reply_text(
            msg.REG_BIO_LONG.format(count=len(text)), parse_mode=ParseMode.MARKDOWN
        )
        return REG_BIO
    else:
        bio = text

    # Save user to DB
    user_id = update.effective_user.id
    tg_user = update.effective_user
    async with session_maker()() as session:
        new_user = await UserRepo(session).create(
            telegram_id=user_id,
            username=tg_user.username,
            alias=context.user_data.get('alias', tg_user.first_name or "Anonymous"),
            age=context.user_data.get('age'),
            gender=context.user_data.get('gender'),
            interests=context.user_data.get('interests'),
            bio=bio,
            language_pref=LanguageEnum.both,
        )

    await update.message.reply_text(
        msg.REG_COMPLETE.format(profile=new_user.profile_text()),
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── /profile ─────────────────────────────────────────────────────────────────

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # If in chat, show partner's profile
    partner_id = active_pairs.get(user_id)
    if partner_id:
        async with session_maker()() as session:
            partner = await UserRepo(session).get(partner_id)
        if partner:
            await update.message.reply_text(
                f"👤 *Partner's Profile*\n\n{partner.profile_text()}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ Could not load partner profile.")
        return

    # Show own profile
    async with session_maker()() as session:
        user = await UserRepo(session).get(user_id)
    if not user:
        await update.message.reply_text(msg.PROFILE_NOT_REGISTERED, parse_mode=ParseMode.MARKDOWN)
        return

    keyboard = [
        [InlineKeyboardButton("✏️ Edit Name", callback_data="edit_alias"),
         InlineKeyboardButton("🎂 Edit Age", callback_data="edit_age")],
        [InlineKeyboardButton("📝 Edit Bio", callback_data="edit_bio"),
         InlineKeyboardButton("🏷 Edit Interests", callback_data="edit_interests")],
    ]
    await update.message.reply_text(
        f"👤 *Your Profile*\n\n{user.profile_text()}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def edit_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edit_", "")
    context.user_data['editing_field'] = field
    prompts = {
        "alias": "Enter new name/alias (2-32 chars):",
        "age": "Enter new age (13-99) or /skip:",
        "bio": "Enter new bio (max 150 chars) or /skip:",
        "interests": "Enter interests as tags, comma-separated (max 5) or /skip:",
    }
    await query.edit_message_text(prompts.get(field, "Enter new value:"))
    return EDIT_VALUE


async def edit_profile_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get('editing_field')
    text = update.message.text.strip()
    user_id = update.effective_user.id
    updates = {}

    if field == "alias":
        if not re.match(r'^[\w\s]{2,32}$', text):
            await update.message.reply_text(msg.REG_ALIAS_INVALID)
            return EDIT_VALUE
        updates['alias'] = text

    elif field == "age":
        if text == "/skip":
            pass
        else:
            try:
                age = int(text)
                if not (13 <= age <= 99):
                    raise ValueError
                updates['age'] = age
            except ValueError:
                await update.message.reply_text(msg.REG_AGE_INVALID)
                return EDIT_VALUE

    elif field == "bio":
        if text != "/skip":
            if len(text) > 150:
                await update.message.reply_text(msg.REG_BIO_LONG.format(count=len(text)))
                return EDIT_VALUE
            updates['bio'] = text

    elif field == "interests":
        if text != "/skip":
            tags = [t.strip()[:20] for t in text.split(",") if t.strip()][:5]
            updates['interests'] = ",".join(tags)

    if updates:
        async with session_maker()() as session:
            await UserRepo(session).update(user_id, **updates)
        await update.message.reply_text("✅ Profile updated! / ፕሮፋይልዎ ተዘምኗል!")
    else:
        await update.message.reply_text("↩️ No changes made.")

    context.user_data.pop('editing_field', None)
    return ConversationHandler.END


# ─── /delete ─────────────────────────────────────────────────────────────────

async def delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_registered(update, context):
        return ConversationHandler.END
    await update.message.reply_text(msg.CONFIRM_DELETE, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DELETE_STATE


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "YES":
        user_id = update.effective_user.id
        # End any active chat first
        if user_id in active_pairs:
            partner_id = active_pairs[user_id]
            await end_chat_for_user(context, user_id, "Chat ended.")
            if partner_id in active_pairs:
                await end_chat_for_user(context, partner_id, msg.PARTNER_DISCONNECTED)

        async with session_maker()() as session:
            from sqlalchemy import delete as sqla_delete
            from database import User, MatchQueue
            await session.execute(sqla_delete(MatchQueue).where(MatchQueue.user_id == user_id))
            await session.execute(sqla_delete(User).where(User.telegram_id == user_id))
            await session.commit()

        in_queue.discard(user_id)
        await update.message.reply_text(msg.PROFILE_DELETED, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Account deletion cancelled.")
    return ConversationHandler.END


# ─── /search ──────────────────────────────────────────────────────────────────

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_registered(update, context):
        return

    user_id = update.effective_user.id

    # Check if already in active chat
    if user_id in active_pairs:
        await update.message.reply_text(msg.SEARCH_ALREADY_IN_CHAT, parse_mode=ParseMode.MARKDOWN)
        return

    # Check if already in queue
    if user_id in in_queue:
        await update.message.reply_text(msg.SEARCH_ALREADY_IN_QUEUE, parse_mode=ParseMode.MARKDOWN)
        return

    # Add to queue
    async with session_maker()() as session:
        user = await UserRepo(session).get(user_id)
        await QueueRepo(session).add(
            user_id,
            pref_gender=user.pref_gender,
            pref_min_age=user.pref_min_age,
            pref_max_age=user.pref_max_age,
        )

    in_queue.add(user_id)
    await update.message.reply_text(msg.SEARCH_STARTED, parse_mode=ParseMode.MARKDOWN)

    # Try to match immediately
    matched = await try_match_from_queue(context, user_id)
    if not matched:
        # Schedule periodic check (handled by job queue)
        pass


async def stop_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in in_queue:
        await update.message.reply_text(msg.QUEUE_NOT_IN_QUEUE, parse_mode=ParseMode.MARKDOWN)
        return
    async with session_maker()() as session:
        await QueueRepo(session).remove(user_id)
    in_queue.discard(user_id)
    await update.message.reply_text(msg.QUEUE_STOPPED, parse_mode=ParseMode.MARKDOWN)


# ─── /next ────────────────────────────────────────────────────────────────────

async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_registered(update, context):
        return
    user_id = update.effective_user.id

    if user_id not in active_pairs and user_id not in in_queue:
        await update.message.reply_text(msg.NOT_IN_CHAT, parse_mode=ParseMode.MARKDOWN)
        return

    # Disconnect from current partner
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        chat_id = user_chat_ids.get(user_id)

        # End for both
        active_pairs.pop(user_id, None)
        user_chat_ids.pop(user_id, None)
        first_photo_sent.pop(user_id, None)
        active_pairs.pop(partner_id, None)
        user_chat_ids.pop(partner_id, None)
        first_photo_sent.pop(partner_id, None)

        if chat_id:
            async with session_maker()() as session:
                await ChatRepo(session).end_chat(chat_id)

        # Notify partner
        try:
            await context.bot.send_message(partner_id, msg.PARTNER_DISCONNECTED, parse_mode=ParseMode.MARKDOWN)
        except TelegramError:
            pass

    # Start searching again
    await update.message.reply_text(msg.NEXT_SEARCHING, parse_mode=ParseMode.MARKDOWN)

    async with session_maker()() as session:
        user = await UserRepo(session).get(user_id)
        await QueueRepo(session).add(user_id)

    in_queue.add(user_id)
    await try_match_from_queue(context, user_id)


# ─── /end ─────────────────────────────────────────────────────────────────────

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_pairs:
        await update.message.reply_text(msg.NOT_IN_CHAT, parse_mode=ParseMode.MARKDOWN)
        return

    partner_id = active_pairs[user_id]
    chat_id = user_chat_ids.get(user_id)

    # End for both
    active_pairs.pop(user_id, None)
    user_chat_ids.pop(user_id, None)
    first_photo_sent.pop(user_id, None)
    active_pairs.pop(partner_id, None)
    user_chat_ids.pop(partner_id, None)
    first_photo_sent.pop(partner_id, None)

    if chat_id:
        async with session_maker()() as session:
            await ChatRepo(session).end_chat(chat_id)

    await update.message.reply_text(msg.CHAT_ENDED_BY_YOU, parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(partner_id, msg.CHAT_ENDED_BY_PARTNER, parse_mode=ParseMode.MARKDOWN)
    except TelegramError:
        pass


# ─── /report ──────────────────────────────────────────────────────────────────

async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in active_pairs:
        await update.message.reply_text(msg.REPORT_NO_PARTNER, parse_mode=ParseMode.MARKDOWN)
        return

    keyboard = []
    for label, data in msg.REPORT_REASONS:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"report_{data}")])

    await update.message.reply_text(
        msg.REPORT_PROMPT,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    reason = query.data.replace("report_", "")

    partner_id = active_pairs.get(user_id)
    if not partner_id:
        await query.edit_message_text("❌ You're no longer in a chat.")
        return

    chat_id = user_chat_ids.get(user_id, "")

    async with session_maker()() as session:
        report_repo = ReportRepo(session)
        await report_repo.create(user_id, partner_id, chat_id, reason)

        # Check auto-ban threshold
        count = await report_repo.count_against(partner_id)
        if count >= AUTO_BAN_THRESHOLD:
            partner_user = await UserRepo(session).get(partner_id)
            await UserRepo(session).update(partner_id, is_banned=True, ban_reason="Auto-banned: multiple reports")
            alias = partner_user.alias if partner_user else str(partner_id)
            await send_admin(context, msg.AUTO_BAN_NOTICE.format(username=alias))
            # Force disconnect partner
            if partner_id in active_pairs:
                their_partner = active_pairs.pop(partner_id, None)
                user_chat_ids.pop(partner_id, None)
                if their_partner:
                    active_pairs.pop(their_partner, None)
                    user_chat_ids.pop(their_partner, None)

    await query.edit_message_text(msg.REPORT_SUBMITTED, parse_mode=ParseMode.MARKDOWN)

    # Notify admin
    await send_admin(context, f"🚨 New report in chat `{chat_id}`\nReason: *{reason}*\nReporter: `{user_id}` | Reported: `{partner_id}`")


# ─── /block ───────────────────────────────────────────────────────────────────

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = active_pairs.get(user_id)

    if not partner_id:
        await update.message.reply_text(msg.BLOCK_NO_PARTNER, parse_mode=ParseMode.MARKDOWN)
        return

    async with session_maker()() as session:
        await BlockRepo(session).block(user_id, partner_id)

    # End the chat
    await end_chat(update, context)
    await update.message.reply_text(msg.BLOCK_SUCCESS, parse_mode=ParseMode.MARKDOWN)


# ─── /rules ───────────────────────────────────────────────────────────────────

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(msg.RULES, parse_mode=ParseMode.MARKDOWN)


# ─── /help ────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(msg.HELP, parse_mode=ParseMode.MARKDOWN)


# ─── /feedback ────────────────────────────────────────────────────────────────

async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_registered(update, context):
        return ConversationHandler.END
    await update.message.reply_text(msg.FEEDBACK_PROMPT, parse_mode=ParseMode.MARKDOWN)
    return FEEDBACK_STATE


async def feedback_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text(msg.FEEDBACK_CANCEL, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    user_id = update.effective_user.id
    await send_admin(context, f"💬 *Feedback from* `{user_id}`:\n{text}", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text(msg.FEEDBACK_SENT, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


# ─── Message Handler (forwarding between users) ───────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward messages between matched users anonymously."""
    if not update.message:
        return

    user_id = update.effective_user.id

    # Must be registered
    user = await get_user(user_id)
    if not user:
        return  # Silently ignore unregistered

    if user.is_banned:
        return

    # Must be in active chat
    partner_id = active_pairs.get(user_id)
    if not partner_id:
        # If in queue, just ignore non-command messages
        if user_id in in_queue:
            return
        await update.message.reply_text(
            "❌ You're not in a chat. Use /search to find a partner.\n"
            "❌ ቻት ውስጥ አይደሉም። ጓደኛ ለማግኘት /search ይጻፉ።"
        )
        return

    # Rate limiting: 1 message per second
    now = datetime.utcnow()
    last = last_message_time.get(user_id)
    if last and (now - last).total_seconds() < 1.0:
        await update.message.reply_text(msg.RATE_LIMITED, parse_mode=ParseMode.MARKDOWN)
        return
    last_message_time[user_id] = now

    chat_id = user_chat_ids.get(user_id, "unknown")
    msg_type = MessageTypeEnum.text
    content = ""

    try:
        m = update.message

        if m.text:
            # Profanity filter
            clean = m.text
            if contains_profanity(m.text):
                clean = "[message filtered]"
            await context.bot.send_message(partner_id, clean)
            msg_type = MessageTypeEnum.text
            content = clean

        elif m.photo:
            # First photo reminder
            if not first_photo_sent.get(user_id):
                first_photo_sent[user_id] = True
                await context.bot.send_message(user_id, msg.FIRST_PHOTO_REMINDER, parse_mode=ParseMode.MARKDOWN)

            photo = m.photo[-1]  # Largest size
            caption = m.caption or ""
            await context.bot.send_photo(partner_id, photo.file_id, caption=caption)
            msg_type = MessageTypeEnum.photo
            content = photo.file_id

        elif m.video:
            await context.bot.send_video(partner_id, m.video.file_id, caption=m.caption or "")
            msg_type = MessageTypeEnum.video
            content = m.video.file_id

        elif m.sticker:
            await context.bot.send_sticker(partner_id, m.sticker.file_id)
            msg_type = MessageTypeEnum.sticker
            content = m.sticker.file_id

        elif m.voice:
            await context.bot.send_voice(partner_id, m.voice.file_id)
            msg_type = MessageTypeEnum.voice
            content = m.voice.file_id

        elif m.animation:  # GIF
            await context.bot.send_animation(partner_id, m.animation.file_id, caption=m.caption or "")
            msg_type = MessageTypeEnum.gif
            content = m.animation.file_id

        elif m.document:
            await context.bot.send_document(partner_id, m.document.file_id, caption=m.caption or "")
            msg_type = MessageTypeEnum.document
            content = m.document.file_id

        else:
            return  # Unknown type, ignore

        # Store in DB
        async with session_maker()() as session:
            await ChatRepo(session).add_message(chat_id, user_id, content, msg_type)

        # Relay to admin
        await relay_to_admin(context, chat_id, user.alias, msg_type.value, content[:100])

    except TelegramError as e:
        logger.error(f"Error forwarding message: {e}")
        # Partner may have blocked the bot
        if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
            # End chat
            active_pairs.pop(user_id, None)
            active_pairs.pop(partner_id, None)
            user_chat_ids.pop(user_id, None)
            user_chat_ids.pop(partner_id, None)
            await update.message.reply_text(msg.PARTNER_DISCONNECTED, parse_mode=ParseMode.MARKDOWN)


# ─── Typing indicator relay ───────────────────────────────────────────────────

async def handle_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relay typing indicators (not directly possible, but we can simulate)."""
    pass  # Telegram doesn't expose typing events to bots natively


# ─── Queue Matcher Job (runs every 5 seconds) ─────────────────────────────────

async def queue_matcher_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodically try to match users in queue."""
    if not in_queue:
        return

    waiting = list(in_queue)
    for user_id in waiting:
        if user_id in active_pairs:
            in_queue.discard(user_id)
            continue
        try:
            matched = await try_match_from_queue(context, user_id)
        except Exception as e:
            logger.error(f"Queue matcher error for {user_id}: {e}")


# ─── Admin Commands ────────────────────────────────────────────────────────────

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    async with session_maker()() as session:
        ur = UserRepo(session)
        cr = ChatRepo(session)
        qr = QueueRepo(session)
        rr = ReportRepo(session)
        total = await ur.count()
        banned = await ur.banned_count()
        active = await cr.active_count()
        queue = await qr.count()
        total_reports = len(await rr.pending())
        today = await rr.today_count()

    text = msg.ADMIN_STATS(total, active, queue, total_reports, today, banned)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def admin_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    async with session_maker()() as session:
        chats = await ChatRepo(session).all_active()
        ur = UserRepo(session)

    if not chats:
        await update.message.reply_text("📭 No active chats right now.")
        return

    lines = ["💬 *Active Chats:*\n"]
    for chat in chats:
        lines.append(
            f"• Chat `{chat.chat_id}` | "
            f"Users: `{chat.user1_id}` ↔ `{chat.user2_id}` | "
            f"Messages: {chat.message_count}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_view_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /view_chat <chat_id>")
        return

    chat_id = args[0]
    async with session_maker()() as session:
        messages = await ChatRepo(session).get_messages(chat_id, limit=20)

    if not messages:
        await update.message.reply_text(f"No messages found for chat `{chat_id}`.")
        return

    lines = [f"📋 *Last messages in chat `{chat_id}`:*\n"]
    for m in reversed(messages):
        time_str = m.sent_at.strftime("%H:%M:%S")
        lines.append(f"[{time_str}] `{m.sender_id}` [{m.message_type.value}]: {m.message_content or ''}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    async with session_maker()() as session:
        users = await UserRepo(session).all_users()

    if not users:
        await update.message.reply_text("No registered users.")
        return

    lines = ["👥 *Registered Users:*\n"]
    for u in users[:30]:  # Cap at 30 to avoid message limit
        status = "🚫" if u.is_banned else "✅"
        lines.append(
            f"{status} *{u.alias}* | ID: `{u.telegram_id}` | "
            f"Age: {u.age or '?'} | Reports: {u.report_count}"
        )

    if len(users) > 30:
        lines.append(f"\n_...and {len(users) - 30} more_")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /ban <user_id> [reason]")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    reason = " ".join(args[1:]) if len(args) > 1 else "Admin ban"

    async with session_maker()() as session:
        user = await UserRepo(session).get(target_id)
        if not user:
            await update.message.reply_text(msg.ADMIN_USER_NOT_FOUND(target_id))
            return
        await UserRepo(session).update(target_id, is_banned=True, ban_reason=reason)

    # Kick from any active chat
    if target_id in active_pairs:
        partner = active_pairs.pop(target_id, None)
        user_chat_ids.pop(target_id, None)
        if partner:
            active_pairs.pop(partner, None)
            user_chat_ids.pop(partner, None)
            try:
                await context.bot.send_message(partner, msg.PARTNER_DISCONNECTED, parse_mode=ParseMode.MARKDOWN)
            except TelegramError:
                pass
    in_queue.discard(target_id)

    # Notify user
    try:
        await context.bot.send_message(
            target_id,
            msg.BANNED_MESSAGE.format(reason=reason),
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramError:
        pass

    await update.message.reply_text(msg.ADMIN_BAN_SUCCESS(target_id, reason), parse_mode=ParseMode.MARKDOWN)


async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    async with session_maker()() as session:
        user = await UserRepo(session).get(target_id)
        if not user:
            await update.message.reply_text(msg.ADMIN_USER_NOT_FOUND(target_id))
            return
        await UserRepo(session).update(target_id, is_banned=False, ban_reason=None)

    try:
        await context.bot.send_message(
            target_id,
            "✅ Your account has been unbanned. Welcome back!\n✅ መለያዎ ታፍሷል። እንኳን ደህና ተመለሱ!"
        )
    except TelegramError:
        pass

    await update.message.reply_text(msg.ADMIN_UNBAN_SUCCESS(target_id), parse_mode=ParseMode.MARKDOWN)


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    broadcast_text = " ".join(args)

    async with session_maker()() as session:
        users = await UserRepo(session).all_users()

    sent = 0
    failed = 0
    for user in users:
        if user.is_banned:
            continue
        try:
            await context.bot.send_message(
                user.telegram_id,
                f"📢 *Announcement / ማስታወቂያ*\n\n{broadcast_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
            await asyncio.sleep(0.05)  # Rate limit broadcasting
        except TelegramError:
            failed += 1

    await update.message.reply_text(
        f"✅ Broadcast sent to {sent} users. Failed: {failed}."
    )


async def admin_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(msg.ADMIN_ONLY)
        return

    async with session_maker()() as session:
        reports = await ReportRepo(session).pending()

    if not reports:
        await update.message.reply_text("✅ No pending reports.")
        return

    lines = ["🚨 *Pending Reports:*\n"]
    for r in reports[:20]:
        time_str = r.timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"• [{time_str}] Reporter: `{r.reporter_id}` → Reported: `{r.reported_id}`\n"
            f"  Reason: *{r.reason}* | Chat: `{r.chat_id}`"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ─── Error Handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Init DB synchronously before starting
    import asyncio as _asyncio
    _asyncio.run(init_db(DATABASE_URL))

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Registration conversation
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            REG_ALIAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_got_alias)],
            REG_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_got_age),
                CommandHandler("skip", reg_got_age),
            ],
            REG_GENDER: [CallbackQueryHandler(reg_got_gender, pattern="^gender_")],
            REG_INTERESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_got_interests),
                CommandHandler("skip", reg_got_interests),
            ],
            REG_BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_got_bio),
                CommandHandler("skip", reg_got_bio),
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )

    # ── Edit profile conversation
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_profile_callback, pattern="^edit_")],
        states={
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_value)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # ── Delete account conversation
    delete_conv = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_account)],
        states={
            CONFIRM_DELETE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # ── Feedback conversation
    feedback_conv = ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_start)],
        states={
            FEEDBACK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_received)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(reg_conv)
    app.add_handler(edit_conv)
    app.add_handler(delete_conv)
    app.add_handler(feedback_conv)
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("stop", stop_search))
    app.add_handler(CommandHandler("next", next_partner))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("report", report_user))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("help", help_command))

    # Admin commands
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("monitor", admin_monitor))
    app.add_handler(CommandHandler("view_chat", admin_view_chat))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("reports", admin_reports))

    # Report callback
    app.add_handler(CallbackQueryHandler(report_callback, pattern="^report_"))

    # Message forwarder (must be last)
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        handle_message
    ))

    # Error handler
    app.add_error_handler(error_handler)

    # Queue matcher job (every 5 seconds)
    app.job_queue.run_repeating(queue_matcher_job, interval=5, first=5)

    logger.info("🚀 AnonChat Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
