"""
messages.py - All bot messages in English and Amharic (Bilingual strings)
"""

# ─── Welcome & Registration ───────────────────────────────────────────────────

WELCOME = """
👋 *Welcome to AnonChat Bot!*
*እንኳን ደህና መጡ ወደ AnonChat Bot!*

Connect with random strangers anonymously and chat safely.


To get started, register your profile:
ለመጀመር ፕሮፋይልዎን ይመዝግቡ:

/register - Create your profile / ፕሮፋይል ፍጠሩ
/help - Help menu / የእርዳታ ዝርዝር
"""

ALREADY_REGISTERED = """
✅ You already have a profile!
✅ ፕሮፋይል አስቀድሞ አለዎት!

/search - Find a chat partner / የቻት ጓደኛ ፈልጉ
/profile - View/edit your profile / ፕሮፋይልዎን ይመልከቱ/ያርትዑ
"""

REG_ASK_ALIAS = """
📝 *Step 1/5 - Name / Alias*

Enter the name or alias you want others to see.
ሌሎች እንዲያዩዎት የሚፈልጉት ስም ወይም ቅጽል ስም ያስገቡ።

_(2-32 characters / 2-32 ፊደሎች)_
"""

REG_ASK_AGE = """
🎂 *Step 2/5 - Age*

How old are you? Enter a number (13-99)
እድሜዎ ስንት ነው? ቁጥር ያስገቡ (13-99)

_Or type /skip to skip / ለመዝለል /skip ይጻፉ_
"""

REG_ASK_GENDER = """
⚧ *Step 3/5 - Gender*

Select your gender / ጾታዎን ይምረጡ:
"""

REG_ASK_INTERESTS = """
🏷 *Step 4/5 - Interests*

Enter your interests as comma-separated tags (max 5):

Example / ምሳሌ: `music, movies, sports, art, travel`

_Or type /skip to skip / ለመዝለል /skip ይጻፉ_
"""

REG_ASK_BIO = """
📝 *Step 5/5 - Short Bio*

Write a short bio about yourself (max 150 characters):
ስለራስዎ አጭር መረጃ ይጻፉ (ቢበዛ 150 ፊደሎች):

_Or type /skip to skip / ለመዝለል /skip ይጻፉ_
"""

REG_COMPLETE = """
🎉 *Registration Complete! / ምዝገባ ተጠናቋል!*

Your profile has been created successfully.
ፕሮፋይልዎ በተሳካ ሁኔታ ተፈጥሯል።

{profile}

Ready to start chatting? / ለማውራት ዝግጁ ነዎት?
/search - Find a partner / ጓደኛ ፈልጉ
/help - See all commands / ሁሉንም ትዕዛዞች ይመልከቱ
"""

REG_ALIAS_INVALID = """
❌ Alias must be 2-32 characters, letters/numbers/spaces only.
"""

REG_AGE_INVALID = """
❌ Please enter a valid age between 18 and 99.
❌ እባኮትን ከ18 እስከ 99 ያለ ዕድሜ ያስገቡ።
"""

REG_BIO_LONG = """
❌ Bio must be 150 characters or less. Yours is {count} characters.
❌ Bio ቢበዛ 150 ፊደሎች መሆን አለበት። የናንተ {count} ፊደሎች ነው።
"""

# ─── Safety Warning (CRITICAL - sent every chat start) ────────────────────────

def SAFETY_WARNING(partner_alias: str) -> str:
    return f"""
🛡️ *SAFETY REMINDER \\- የደህንነት ማሳሰቢያ* 🛡️

⚠️ እባኮትን ፊቶን የሚያሳይ ፎቶ ለማንም አይላኩ
Please don't send any nude photo when your face is visible

━━━━━━━━━━━━━━━━━━━━
👤 You are now chatting with: *{partner_alias}*
💬 Say hello\\! / ሰላም በሉ\\!

Commands: /next \\| /end \\| /report \\| /block \\| /rules
"""

FIRST_PHOTO_REMINDER = """
📸 *Reminder / ማሳሰቢያ*

⚠️ Please make sure your face is NOT visible in photos you share.
⚠️ እባኮትን የሚጋሩዋቸው ፎቶዎች ፊቶን እንዳያሳዩ ያረጋግጡ።

Your safety matters! / ደህንነትዎ ያስፈልጋል!
"""

# ─── Matching / Queue ─────────────────────────────────────────────────────────

SEARCH_STARTED = """
🔍 *Looking for a partner... / ጓደኛ በመፈለግ ላይ...*

You're now in the queue. Please wait...
 እባኮትን ይጠብቁ...

_Type /stop to leave the queue / stop ይጻፉ_
"""

SEARCH_ALREADY_IN_CHAT = """
⚠️ You're already in a chat!


Use /next to skip or /end to end the current chat.
ለመዝለል /next ወይም ቻቱን ለማቆም /end ይጻፉ።
"""

SEARCH_ALREADY_IN_QUEUE = """
⏳ You're already in the queue, please wait...
⏳ አስቀድሞ ተርፌ ውስጥ ነዎት፣ እባኮትን ይጠብቁ...

_Type /stop to leave / ለቀናት /stop ይጻፉ_
"""

QUEUE_STOPPED = """
✅ You've left the queue.
✅ ከተርፌ ወጥተዋል።

/search - Search again / እንደገና ፈልጉ
"""

QUEUE_NOT_IN_QUEUE = """
❌ You're not in the queue.
"""

PARTNER_DISCONNECTED = """
👋 *Your partner has disconnected.*
👋 *ጓደኛዎ ግንኙነቱን አቋርል።*

/search - Find a new partner / አዲስ ጓደኛ ፈልጉ
/help - Help menu
"""

# ─── Active Chat ──────────────────────────────────────────────────────────────

NOT_IN_CHAT = """
❌ You're not in an active chat.
❌ ንቁ ቻት ውስጥ አይደሉም።

/search - Find a partner / ጓደኛ ፈልጉ
"""

CHAT_ENDED_BY_YOU = """
👋 *You ended the chat.*
👋 *ቻቱን ጨርሰዋል።*

/search - Find a new partner / አዲስ ጓደኛ ፈልጉ
"""

CHAT_ENDED_BY_PARTNER = """
👋 *Your partner ended the chat.*
👋 *ጓደኛዎ ቻቱን አጠናቋል።*

/search - Find a new partner / አዲስ ጓደኛ ፈልጉ
"""

NEXT_SEARCHING = """
⏭ *Skipping... / ዘልሎ ማለፍ...*

Looking for a new partner...
አዲስ ጓደኛ በመፈለግ ላይ...
"""

RATE_LIMITED = """
⏱ *Slow down! /

You're sending messages too fast. Please wait a moment.
መልዕክቶቹን በፍጥነት ነው የሚልኩት። ትንሽ ይጠብቁ።
"""

# ─── Report ───────────────────────────────────────────────────────────────────

REPORT_PROMPT = """
⚠️ *Report User / ተጠቃሚ ሪፖርት ያድርጉ*

Select the reason for reporting:
ሪፖርት ለማድረግ ምክንያቱን ይምረጡ:
"""

REPORT_REASONS = [
    ("1. 📸 Inappropriate photo / ተገቢ ያልሆነ ፎቶ", "inappropriate_photo"),
    ("2. 😱 Nude with face visible / ፊት የሚታይ ራቁት", "nude_face"),
    ("3. 😡 Harassment / ትንኮሳ", "harassment"),
    ("4. 📢 Spam / አይፈለጌ መልእክት", "spam"),
    ("5. 🎭 Fake profile / ሀሰተኛ ፕሮፋይል", "fake_profile"),
    ("6. 🔖 Other / ሌላ", "other"),
]

REPORT_SUBMITTED = """
✅ *Report submitted. Thank you!*
✅ *ሪፖርቱ ተላልፏል። ያመሰግናሉ!*

Our admin team will review this report.
የአስተዳዳሪ ቡድናችን ሪፖርቱን ይገመግማል።

/next - Find a new partner / አዲስ ጓደኛ ፈልጉ
"""

REPORT_NO_PARTNER = """
❌ You must be in a chat to report someone.
❌ ሪፖርት ለማድረግ ቻት ውስጥ መሆን አለብዎ።
"""

AUTO_BAN_NOTICE = """
🚫 *User @{username} has been auto-banned due to multiple reports.*
"""

# ─── Block ────────────────────────────────────────────────────────────────────

BLOCK_SUCCESS = """
🚫 *User blocked successfully.*
🚫 *ተጠቃሚው በተሳካ ሁኔታ ታግዷል።*

You won't be matched with this person again.
ከዚህ ሰው ጋር ዳግመኛ አይዛመዱም።

/search - Find a new partner / አዲስ ጓደኛ ፈልጉ
"""

BLOCK_NO_PARTNER = """
❌ You must be in a chat to block someone.
❌ ለማገድ ቻት ውስጥ መሆን አለብዎ።
"""

# ─── Rules ────────────────────────────────────────────────────────────────────

RULES = """
📋 *SAFETY RULES / የደህንነት ደንቦች*

━━━━━━━━━━━━━━━━━━━━
🇬🇧 *ENGLISH RULES:*
━━━━━━━━━━━━━━━━━━━━

1. 🚫 Never send nude photos where your face is visible
2. 🔒 Do not share personal information (phone, address, social media)
3. 🤝 Be respectful to all users
4. 🛑 No harassment, threats, or hate speech
5. 📵 No spam or advertisement
6. 🎭 No impersonation of others
7. 👶 Users must be 13 years or older
8. 👁 All chats are monitored by admins
9. ⚠️ Violations result in permanent ban

━━━━━━━━━━━━━━━━━━━━
🇪🇹 *የአማርኛ ደንቦች:*
━━━━━━━━━━━━━━━━━━━━

1. 🚫 ፊትዎ የሚታይ ራቁት ፎቶ አይላኩ
2. 🔒 የግል መረጃ አይስጡ (ስልክ፣ አድራሻ፣ ሶሻል ሚዲያ)
3. 🤝 ለሁሉም ተጠቃሚዎች ያከብሩ
4. 🛑 ትንኮሳ፣ ዛቻ ወይም የጥላቻ ንግግር አይፈቀድም
5. 📵 ስፓም ወይም ማስታወቂያ አይፈቀድም
6. 🎭 ሌሎችን አስቀሮ መምሰል አይፈቀድም
7. 👶 ተጠቃሚዎች ቢያንስ 13 ዓመት መሆን አለባቸው
8. 👁 ሁሉም ቻቶች በአስተዳዳሪዎች ይቆጣጠራሉ
9. ⚠️ ደንቦቹን መጣስ ዘላቂ እገዳ ያስከትላል

━━━━━━━━━━━━━━━━━━━━
_/report if someone breaks these rules_
"""

# ─── Help ─────────────────────────────────────────────────────────────────────

HELP = """
📚 *HELP MENU / የእርዳታ ዝርዝር*

━━━━━━━━━━━━━━━━━━━━
🔍 *Finding a Chat / ቻት ማግኘት*
/search — Find a random partner / ዘፈቀደ ጓደኛ ፈልጉ
/stop — Leave the queue / ተርፌ ይውጡ

━━━━━━━━━━━━━━━━━━━━
💬 *During a Chat / ቻት ውስጥ*
/next — Skip to next person / ቀጣዩ ሰው
/end — End chat politely / ቻቱን ጨርሱ
/report — Report this user / ሪፖርት ያድርጉ
/block — Block this user / ታጉ
/profile — View partner's profile / ፕሮፋይል ይመልከቱ
/rules — Safety rules / የደህንነት ደንቦች

━━━━━━━━━━━━━━━━━━━━
👤 *Your Account / መለያዎ*
/register — Create profile / ፕሮፋይል ፍጠሩ
/profile — View/edit profile / ፕሮፋይል ይመልከቱ/ያርትዑ
/delete — Delete account / መለያ ሰርዙ
/feedback — Send feedback / አስተያየት ላኩ

━━━━━━━━━━━━━━━━━━━━
⚠️ *All chats are anonymous and monitored for safety.*
⚠️ *ሁሉም ቻቶች ስም አልባ ናቸው፣ ለደህንነት ይቆጣጠራሉ።*
"""

# ─── Profile ──────────────────────────────────────────────────────────────────

PROFILE_NOT_REGISTERED = """
❌ You don't have a profile yet.
❌ ፕሮፋይል እስካሁን የለዎትም።

/register - Create your profile / ፕሮፋይল ይፍጠሩ
"""

EDIT_PROFILE_PROMPT = """
✏️ *Edit Profile / ፕሮፋይል ያርትዑ*

What would you like to edit?
ምን ማርትዕ ይፈልጋሉ?
"""

PROFILE_DELETED = """
🗑 *Your account has been deleted.*
🗑 *መለያዎ ተሰርዟል።*

All your data has been removed.
ሁሉም ውሂቦችዎ ተሰርዘዋል።

/register - Create a new account / አዲስ መለያ ይፍጠሩ
"""

CONFIRM_DELETE = """
⚠️ *Are you sure you want to delete your account?*
⚠️ *መለያዎን እርግጠኛ ሆነው መሰርዝ ይፈልጋሉ?*

This will remove ALL your data permanently.
ይህ ሁሉንም ውሂቦችዎን ዘለቄታዊ ሆኖ ይሰርዘዋል።

Type YES to confirm / ለማረጋገጥ YES ይጻፉ
"""

# ─── Banned ───────────────────────────────────────────────────────────────────

BANNED_MESSAGE = """
🚫 *Your account has been banned.*
🚫 *መለያዎ ታግዷል።*

Reason: {reason}
ምክንያት: {reason}

If you believe this is a mistake, please contact the admin.
ስህተት ነው ብለው ካሰቡ እባኮትን አስተዳዳሪውን ያናግሩ።
"""

NOT_REGISTERED = """
❌ You need to register first!
❌ መጀመሪያ ምዝገባ ያስፈልጋል!

/register - Create your profile / ፕሮፋይል ይፍጠሩ
"""

# ─── Feedback ─────────────────────────────────────────────────────────────────

FEEDBACK_PROMPT = """
💬 *Send Feedback / አስተያየት ላኩ*

Type your feedback or suggestion below:
አስተያየትዎን ወይም ሀሳብዎን ከዚህ በታች ይጻፉ:

_(Type /cancel to cancel / ለመሰረዝ /cancel ይጻፉ)_
"""

FEEDBACK_SENT = """
✅ *Feedback sent! Thank you.*
✅ *አስተያየቱ ተላልፏል። ያመሰግናሉ።*
"""

FEEDBACK_CANCEL = """
❌ Feedback cancelled.
❌ አስተያየቱ ተሰርዟል።
"""

# ─── Admin ────────────────────────────────────────────────────────────────────

ADMIN_ONLY = "🔒 This command is for admins only. / ይህ ትዕዛዝ ለአስተዳዳሪዎች ብቻ ነው።"

def ADMIN_STATS(total_users, active_chats, queue_size, total_reports, today_reports, banned):
    return f"""
📊 *BOT STATISTICS / የቦት ስታቲስቲክስ*

━━━━━━━━━━━━━━━━━━━━
👥 Total Users: *{total_users}*
🚫 Banned Users: *{banned}*
💬 Active Chats: *{active_chats}*
⏳ In Queue: *{queue_size}*
━━━━━━━━━━━━━━━━━━━━
🚨 Total Reports: *{total_reports}*
📅 Reports Today: *{today_reports}*
━━━━━━━━━━━━━━━━━━━━
"""

def ADMIN_BAN_SUCCESS(user_id, reason):
    return f"✅ User `{user_id}` has been banned.\nReason: {reason}"

def ADMIN_UNBAN_SUCCESS(user_id):
    return f"✅ User `{user_id}` has been unbanned."

def ADMIN_USER_NOT_FOUND(user_id):
    return f"❌ User `{user_id}` not found."

def ADMIN_CHAT_RELAY(chat_id, sender_alias, msg_type, content):
    return f"[Chat `{chat_id}`] *{sender_alias}* [{msg_type}]: {content}"
