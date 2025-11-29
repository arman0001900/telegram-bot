import sqlite3
import random
import string
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تنظیمات
BOT_TOKEN = "7892043953:AAGjYraYgo6byvT5ZnvKGAfTki4wMJ-0P40"
ADMIN_USERNAME = "@pesarkhandeadmin"
ADMIN_ID = "YOUR_ADMIN_USER_ID"
CHANNEL_USERNAME = "@Mafiakhand"

JAM_PACKAGES = {
    '200': {'jam': 200, 'required_refs': 5},
    '500': {'jam': 500, 'required_refs': 10},
    '1200': {'jam': 1200, 'required_refs': 18}
}

CARD_PACKAGES = {
    '10000': {'amount': 10000, 'required_refs': 5},
    '20000': {'amount': 20000, 'required_refs': 10},
    '40000': {'amount': 40000, 'required_refs': 18}
}

# دیتابیس ساده
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                referral_code TEXT UNIQUE,
                referrals INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()
    
    def get_user(self, user_id: int):
        cursor = self.conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    def create_user(self, user_id: int, username: str):
        referral_code = self.generate_referral_code()
        self.conn.execute(
            'INSERT OR IGNORE INTO users (user_id, username, referral_code) VALUES (?, ?, ?)',
            (user_id, username, referral_code)
        )
        self.conn.commit()
        return referral_code
    
    def generate_referral_code(self):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            cursor = self.conn.execute('SELECT 1 FROM users WHERE referral_code = ?', (code,))
            if not cursor.fetchone():
                return code
    
    def get_referral_code(self, user_id: int):
        cursor = self.conn.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_total_users(self):
        cursor = self.conn.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]
    
    def get_user_referrals(self, user_id: int):
        cursor = self.conn.execute('SELECT referrals FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def update_referrals(self, user_id: int):
        self.conn.execute('UPDATE users SET referrals = referrals + 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def deduct_referrals(self, user_id: int, amount: int):
        self.conn.execute('UPDATE users SET referrals = referrals - ? WHERE user_id = ?', (amount, user_id))
        self.conn.commit()

db = Database()

# دستور استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    
    # ایجاد کاربر اگر وجود نداشته باشد
    if not db.get_user(user_id):
        db.create_user(user_id, username)
        
        # اولین بار - پیام جوین اجباری
        keyboard = [[InlineKeyboardButton("📢 عضویت در چنل", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔰 برای ثبت رفرال و ادامه کار ربات لطفاً در چنل زیر جوین شوید\n\n"
            f"📢 {CHANNEL_USERNAME}\n\n"
            f"⚠️ در غیر این صورت ربات برای شما خدماتی ندارد\n\n"
            f"✅ پس از عضویت، دوباره روی /start کلیک کنید",
            reply_markup=reply_markup
        )
        return
    
    # بار دوم - منوی اصلی
    keyboard = [
        [InlineKeyboardButton("📥 دریافت لینک رفرال", callback_data="referral")],
        [InlineKeyboardButton("💳 برداشت موجودی", callback_data="withdrawal")],
        [InlineKeyboardButton("👨‍💼 پنل مدیریت", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎉 به ربات خوش آمدید!\n\n"
        "لطفا یکی از گزینه های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

# مدیریت کلیک دکمه‌ها
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "referral":
        await referral_handler(query, context)
    elif data == "withdrawal":
        await withdrawal_handler(query, context)
    elif data == "admin_panel":
        await admin_handler(query, context)
    elif data == "withdraw_jam":
        await withdraw_jam_handler(query, context)
    elif data == "withdraw_card":
        await withdraw_card_handler(query, context)
    elif data.startswith("jam_"):
        await jam_package_handler(query, data, context)
    elif data.startswith("card_"):
        await card_package_handler(query, data, context)
    elif data == "main_menu":
        await main_menu_handler(query, context)

# منوی اصلی
async def main_menu_handler(query, context):
    keyboard = [
        [InlineKeyboardButton("📥 دریافت لینک رفرال", callback_data="referral")],
        [InlineKeyboardButton("💳 برداشت موجودی", callback_data="withdrawal")],
        [InlineKeyboardButton("👨‍💼 پنل مدیریت", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎉 به ربات خوش آمدید!\n\n"
        "لطفا یکی از گزینه های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

# مدیریت رفرال
async def referral_handler(query, context):
    user_id = query.from_user.id
    
    referral_code = db.get_referral_code(user_id)
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🔗 لینک رفرال اختصاصی شما:\n\n"
        f"`{referral_link}`\n\n"
        f"📊 تعداد رفرال های شما: {db.get_user_referrals(user_id)}\n\n"
        "این لینک را برای دوستان خود ارسال کنید!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# مدیریت برداشت
async def withdrawal_handler(query, context):
    keyboard = [
        [InlineKeyboardButton("🎁 کد جم", callback_data="withdraw_jam")],
        [InlineKeyboardButton("💸 کارت به کارت", callback_data="withdraw_card")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💳 روش برداشت خود را انتخاب کنید:",
        reply_markup=reply_markup
    )

# مدیریت جم
async def withdraw_jam_handler(query, context):
    keyboard = [
        [InlineKeyboardButton("۲۰۰ جم - ۵ رفرال", callback_data="jam_200")],
        [InlineKeyboardButton("۵۰۰ جم - ۱۰ رفرال", callback_data="jam_500")],
        [InlineKeyboardButton("۱۲۰۰ جم - ۱۸ رفرال", callback_data="jam_1200")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="withdrawal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎁 پکیج مورد نظر برای دریافت جم را انتخاب کنید:",
        reply_markup=reply_markup
    )

# مدیریت کارت به کارت
async def withdraw_card_handler(query, context):
    keyboard = [
        [InlineKeyboardButton("۱۰ تومن - ۵ رفرال", callback_data="card_10000")],
        [InlineKeyboardButton("۲۰ تومن - ۱۰ رفرال", callback_data="card_20000")],
        [InlineKeyboardButton("۴۰ تومن - ۱۸ رفرال", callback_data="card_40000")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="withdrawal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💸 مبلغ مورد نظر برای کارت به کارت را انتخاب کنید:",
        reply_markup=reply_markup
    )

# مدیریت پکیج‌های جم
async def jam_package_handler(query, data, context):
    user_id = query.from_user.id
    package = data.replace("jam_", "")
    jam_info = JAM_PACKAGES.get(package)
    user_refs = db.get_user_referrals(user_id)
    
    if user_refs >= jam_info['required_refs']:
        db.deduct_referrals(user_id, jam_info['required_refs'])
        message_text = (
            f"✅ خرید شما با موفقیت ثبت شد!\n\n"
            f"📞 برای دریافت جم به ایدی زیر پیام بدید:\n{ADMIN_USERNAME}"
        )
    else:
        message_text = (
            f"❌ تعداد رفرال های شما کافی نیست!\n\n"
            f"📊 رفرال های شما: {user_refs}\n"
            f"📋 رفرال مورد نیاز: {jam_info['required_refs']}\n\n"
            f"لینک رفرال خود را برای دوستانتان ارسال کنید."
        )
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="withdraw_jam")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup)

# مدیریت پکیج‌های کارت به کارت
async def card_package_handler(query, data, context):
    user_id = query.from_user.id
    package = data.replace("card_", "")
    card_info = CARD_PACKAGES.get(package)
    user_refs = db.get_user_referrals(user_id)
    
    if user_refs >= card_info['required_refs']:
        db.deduct_referrals(user_id, card_info['required_refs'])
        message_text = (
            f"✅ خرید شما با موفقیت ثبت شد!\n\n"
            f"💸 برای دریافت پول، شماره کارت خود را به ایدی زیر ارسال کنید:\n{ADMIN_USERNAME}"
        )
    else:
        message_text = (
            f"❌ تعداد رفرال های شما کافی نیست!\n\n"
            f"📊 رفرال های شما: {user_refs}\n"
            f"📋 رفرال مورد نیاز: {card_info['required_refs']}\n\n"
            f"لینک رفرال خود را برای دوستانتان ارسال کنید."
        )
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="withdraw_card")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup)

# مدیریت پنل ادمین
async def admin_handler(query, context):
    user_id = query.from_user.id
    username = query.from_user.username
    
    if f"@{username}" != ADMIN_USERNAME and str(user_id) != ADMIN_ID:
        await query.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    total_users = db.get_total_users()
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👨‍💼 پنل مدیریت\n\n"
        f"📊 تعداد کل کاربران: {total_users}",
        reply_markup=reply_markup
    )

# اجرای ربات
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 ربات فعال شد...")
    application.run_polling()

if __name__ == "__main__":
    main()
