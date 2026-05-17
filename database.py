"""
database.py - Database models and async session management
Uses SQLite with SQLAlchemy 2.0 async for production-ready persistence.
"""

import asyncio
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean,
    DateTime, ForeignKey, Enum as SAEnum, select, update, delete, func
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ─── Enums ────────────────────────────────────────────────────────────────────

class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not = "prefer_not"

class LanguageEnum(str, enum.Enum):
    english = "english"
    amharic = "amharic"
    both = "both"

class ChatStatus(str, enum.Enum):
    active = "active"
    ended = "ended"

class ReportStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    actioned = "actioned"

class MessageTypeEnum(str, enum.Enum):
    text = "text"
    photo = "photo"
    video = "video"
    sticker = "sticker"
    voice = "voice"
    gif = "gif"
    document = "document"
    other = "other"


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)          # @username from Telegram
    alias = Column(String(32), nullable=False)             # Display name in chats
    age = Column(Integer, nullable=True)
    gender = Column(SAEnum(GenderEnum), nullable=True)
    interests = Column(Text, nullable=True)                # Comma-separated tags
    bio = Column(String(150), nullable=True)
    language_pref = Column(SAEnum(LanguageEnum), default=LanguageEnum.both)
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(String(200), nullable=True)
    report_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    # Preferences for matching
    pref_gender = Column(String(20), nullable=True)        # "male","female","any"
    pref_min_age = Column(Integer, nullable=True)
    pref_max_age = Column(Integer, nullable=True)

    # Registration state machine
    reg_state = Column(String(30), nullable=True)          # used during /register flow

    def profile_text(self, show_full=False):
        """Render profile as Telegram markdown text."""
        parts = [f"👤 *{self.alias}*"]
        if self.age:
            parts.append(f"🎂 Age: {self.age}")
        if self.gender and self.gender != GenderEnum.prefer_not:
            g = {"male": "Male", "female": "Female", "other": "Other"}.get(self.gender.value, "")
            parts.append(f"⚧ Gender: {g}")
        if self.bio:
            parts.append(f"📝 Bio: {self.bio}")
        if self.interests:
            tags = " ".join(f"#{t.strip()}" for t in self.interests.split(",") if t.strip())
            parts.append(f"🏷 Interests: {tags}")
        lang_map = {"english": "🇬🇧 English", "amharic": "🇪🇹 Amharic", "both": "🌍 Both"}
        lang = lang_map.get(self.language_pref.value if self.language_pref else "both", "Both")
        parts.append(f"🗣 Language: {lang}")
        return "\n".join(parts)


class ActiveChat(Base):
    __tablename__ = "active_chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID string
    user1_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    user2_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    status = Column(SAEnum(ChatStatus), default=ChatStatus.active)
    message_count = Column(Integer, default=0)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(36), ForeignKey("active_chats.chat_id"), nullable=False, index=True)
    sender_id = Column(BigInteger, nullable=False)
    message_content = Column(Text, nullable=True)   # text or file_id
    message_type = Column(SAEnum(MessageTypeEnum), default=MessageTypeEnum.text)
    sent_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reporter_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    reported_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    chat_id = Column(String(36), nullable=True)
    reason = Column(String(100), nullable=False)
    extra_notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(SAEnum(ReportStatus), default=ReportStatus.pending)


class BlockedUser(Base):
    __tablename__ = "blocked_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    blocked_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    blocked_at = Column(DateTime, default=datetime.utcnow)


class MatchQueue(Base):
    __tablename__ = "match_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), unique=True, nullable=False)
    pref_gender = Column(String(20), nullable=True)
    pref_min_age = Column(Integer, nullable=True)
    pref_max_age = Column(Integer, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)


class MatchHistory(Base):
    """Track who matched with whom to prevent repeat matches."""
    __tablename__ = "match_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user1_id = Column(BigInteger, nullable=False)
    user2_id = Column(BigInteger, nullable=False)
    matched_at = Column(DateTime, default=datetime.utcnow)


# ─── DB Setup ────────────────────────────────────────────────────────────────

_engine = None
_session_factory = None


def get_engine(database_url: str):
    global _engine
    if _engine is None:
        # Convert sync sqlite:// to async aiosqlite://
        if database_url.startswith("sqlite:///"):
            database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        _engine = create_async_engine(database_url, echo=False)
    return _engine


def get_session_factory(database_url: str):
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def init_db(database_url: str):
    """Create all tables if they don't exist."""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ─── Repository helpers ───────────────────────────────────────────────────────

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, telegram_id: int) -> Optional[User]:
        result = await self.s.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> User:
        user = User(**kwargs)
        self.s.add(user)
        await self.s.commit()
        await self.s.refresh(user)
        return user

    async def update(self, telegram_id: int, **kwargs):
        await self.s.execute(
            update(User).where(User.telegram_id == telegram_id).values(**kwargs)
        )
        await self.s.commit()

    async def all_users(self) -> List[User]:
        result = await self.s.execute(select(User).order_by(User.created_at.desc()))
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.s.execute(select(func.count(User.id)))
        return result.scalar()

    async def banned_count(self) -> int:
        result = await self.s.execute(select(func.count(User.id)).where(User.is_banned == True))
        return result.scalar()


class ChatRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_active_by_user(self, telegram_id: int) -> Optional[ActiveChat]:
        result = await self.s.execute(
            select(ActiveChat).where(
                ActiveChat.status == ChatStatus.active,
                (ActiveChat.user1_id == telegram_id) | (ActiveChat.user2_id == telegram_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_chat_id(self, chat_id: str) -> Optional[ActiveChat]:
        result = await self.s.execute(select(ActiveChat).where(ActiveChat.chat_id == chat_id))
        return result.scalar_one_or_none()

    async def create(self, chat_id: str, user1_id: int, user2_id: int) -> ActiveChat:
        chat = ActiveChat(chat_id=chat_id, user1_id=user1_id, user2_id=user2_id)
        self.s.add(chat)
        await self.s.commit()
        await self.s.refresh(chat)
        return chat

    async def end_chat(self, chat_id: str):
        await self.s.execute(
            update(ActiveChat)
            .where(ActiveChat.chat_id == chat_id)
            .values(status=ChatStatus.ended, ended_at=datetime.utcnow())
        )
        await self.s.commit()

    async def active_count(self) -> int:
        result = await self.s.execute(
            select(func.count(ActiveChat.id)).where(ActiveChat.status == ChatStatus.active)
        )
        return result.scalar()

    async def all_active(self) -> List[ActiveChat]:
        result = await self.s.execute(
            select(ActiveChat).where(ActiveChat.status == ChatStatus.active)
        )
        return result.scalars().all()

    async def add_message(self, chat_id: str, sender_id: int, content: str, msg_type: MessageTypeEnum):
        msg = ChatMessage(chat_id=chat_id, sender_id=sender_id, message_content=content, message_type=msg_type)
        self.s.add(msg)
        # Increment message count
        await self.s.execute(
            update(ActiveChat)
            .where(ActiveChat.chat_id == chat_id)
            .values(message_count=ActiveChat.message_count + 1)
        )
        await self.s.commit()

    async def get_messages(self, chat_id: str, limit: int = 50) -> List[ChatMessage]:
        result = await self.s.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.sent_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


class QueueRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def add(self, user_id: int, **prefs):
        # Remove first if already in queue
        await self.remove(user_id)
        entry = MatchQueue(user_id=user_id, **prefs)
        self.s.add(entry)
        await self.s.commit()

    async def remove(self, user_id: int):
        await self.s.execute(delete(MatchQueue).where(MatchQueue.user_id == user_id))
        await self.s.commit()

    async def get_waiting(self, exclude_user: int, exclude_ids: List[int]) -> List[MatchQueue]:
        """Get all queued users except the given user and blocked/excluded ones."""
        query = select(MatchQueue).where(MatchQueue.user_id != exclude_user)
        if exclude_ids:
            query = query.where(MatchQueue.user_id.not_in(exclude_ids))
        query = query.order_by(MatchQueue.joined_at)
        result = await self.s.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.s.execute(select(func.count(MatchQueue.id)))
        return result.scalar()


class ReportRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, reporter_id: int, reported_id: int, chat_id: str, reason: str) -> Report:
        r = Report(reporter_id=reporter_id, reported_id=reported_id, chat_id=chat_id, reason=reason)
        self.s.add(r)
        await self.s.commit()
        return r

    async def pending(self) -> List[Report]:
        result = await self.s.execute(
            select(Report).where(Report.status == ReportStatus.pending).order_by(Report.timestamp.desc())
        )
        return result.scalars().all()

    async def count_against(self, user_id: int) -> int:
        result = await self.s.execute(
            select(func.count(Report.id)).where(Report.reported_id == user_id)
        )
        return result.scalar()

    async def today_count(self) -> int:
        today = datetime.utcnow().date()
        result = await self.s.execute(
            select(func.count(Report.id)).where(
                func.date(Report.timestamp) == today
            )
        )
        return result.scalar()


class BlockRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def block(self, user_id: int, blocked_id: int):
        # Check not already blocked
        result = await self.s.execute(
            select(BlockedUser).where(
                BlockedUser.user_id == user_id,
                BlockedUser.blocked_user_id == blocked_id
            )
        )
        if not result.scalar_one_or_none():
            b = BlockedUser(user_id=user_id, blocked_user_id=blocked_id)
            self.s.add(b)
            await self.s.commit()

    async def get_blocked_ids(self, user_id: int) -> List[int]:
        """Return all user IDs that `user_id` has blocked, plus who blocked them."""
        result = await self.s.execute(
            select(BlockedUser.blocked_user_id).where(BlockedUser.user_id == user_id)
        )
        blocked_by_me = [r[0] for r in result.all()]

        result2 = await self.s.execute(
            select(BlockedUser.user_id).where(BlockedUser.blocked_user_id == user_id)
        )
        who_blocked_me = [r[0] for r in result2.all()]

        return list(set(blocked_by_me + who_blocked_me))


class HistoryRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def add(self, u1: int, u2: int):
        h = MatchHistory(user1_id=min(u1, u2), user2_id=max(u1, u2))
        self.s.add(h)
        await self.s.commit()

    async def have_matched(self, u1: int, u2: int) -> bool:
        result = await self.s.execute(
            select(MatchHistory).where(
                MatchHistory.user1_id == min(u1, u2),
                MatchHistory.user2_id == max(u1, u2)
            )
        )
        return result.scalar_one_or_none() is not None
