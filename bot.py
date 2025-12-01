import sqlite3
import random
import string
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# تنظیمات
BOT_TOKEN = "7892043953:AAGjYraYgo6byvT5ZnvKGAfTki4wMJ-0P40"
ADMIN_USERNAMES = ["@pesarkhandeadmin", "@MrArmanQ", "@PvApb"]
ADMIN_IDS = ["YOUR_ADMIN_USER_ID", "ARMANS_USER_ID", "PVAPB_USER_ID"]
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

# دیتابیس
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
                referrals INTEGER DEFAULT 0,
                has_started BOOLEAN DEFAULT FALSE
            )
        ''')
        
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                product_type TEXT,
                product_name TEXT,
                amount INTEGER,
                refs_used INTEGER,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        self.conn.commit()
    
    def get_user(self, user_id: int):
        cursor = self.conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    def create_user(self, user_id: int, username: str, referral_code: str = None):
        if not referral_code:
            referral_code = self.generate_referral_code()
        self.conn.execute(
            'INSERT OR IGNORE INTO users (user_id, username, referral_code) VALUES (?, ?, ?)',
            (user_id, username, referral_code)
        )
        self.conn.commit()
        return referral_code
    
    def mark_user_started(self, user_id: int):
        self.conn.execute(
            'UPDATE users SET has_started = TRUE WHERE user_id = ?',
            (user_id,)
        )
        self.conn.commit()
    
    def has_user_started(self, user_id: int):
        cursor = self.conn.execute('SELECT has_started FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else False
    
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
    
    def get_user_by_referral_code(self, referral_code: str):
        cursor = self.conn.execute('SELECT user_id, username FROM users WHERE referral_code = ?', (referral_code,))
        result = cursor.fetchone()
        return result if result else None
    
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
    
    def set_user_referrals(self, user_id: int, amount: int):
        self.conn.execute('UPDATE users SET referrals = ? WHERE user_id = ?', (amount, user_id))
        self.conn.commit()
    
    def get_all_users(self):
        cursor = self.conn.execute('SELECT user_id, username, referrals FROM users ORDER BY referrals DESC')
        return cursor.fetchall()
    
    def add_order(self, user_id: int, username: str, product_type: str, product_name: str, amount: int, refs_used: int):
        self.conn.execute(
            'INSERT INTO orders (user_id, username, product_type, product_name, amount, refs_used) VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, username, product_type, product_name, amount, refs_used)
        )
        self.conn.commit()
    
    def get_all_orders(self):
        cursor = self.conn.execute('''
            SELECT user_id, username, product_type, product_name, amount, refs_used, order_date 
            FROM orders 
            ORDER BY order_date DESC
        ''')
        return cursor.fetchall()
    
    def get_pending_orders_count(self):
        cursor = self.conn.execute('SELECT COUNT(*) FROM orders WHERE status = ?', ('pending',))
        return cursor.fetchone()[0]

db = Database()

# دیکشنری برای ذخیره وضعیت تنظیم رفرال
user_set_refs_state = {}

# بررسی دسترسی ادمین
def is_admin(user_id: int, username: str):
    user_username = f"@{username}" if username else ""
    return (str(user_id) in ADMIN_IDS or user_username in ADMIN_USERNAMES)

# ارسال پیام به ادمین‌ها
async def send_to_admins(bot, message: str):
    for admin_id in ADMIN_IDS:
        if admin_id != "YOUR_ADMIN_USER_ID" and admin_id != "ARMANS_USER_ID" and admin_id != "PVAPB_USER_ID":
            try:
                await bot.send_message(chat_id=admin_id, text=message)
            except:
                pass

# دستور استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    
    # بررسی آیا کاربر با لینک رفرال آمده یا نه
    referral_owner_info = None
    if context.args:
        referral_code = context.args[0]
        referral_owner_info = db.get_user_by_referral_code(referral_code)
        
        # اگر کاربر با لینک رفرال آمده و صاحب لینک خودش نیست و قبلاً استارت نکرده
        if (referral_owner_info and 
            referral_owner_info[0] != user_id and 
            not db.has_user_started(user_id)):
            
            db.update_referrals(referral_owner_info[0])
            db.mark_user_started(user_id)
            
            # ارسال پیام به صاحب لینک
            referral_owner_id = referral_owner_info[0]
            referral_owner_username = referral_owner_info[1] or "بدون یوزرنیم"
            current_refs = db.get_user_referrals(referral_owner_id)
            
            try:
                await context.bot.send_message(
                    chat_id=referral_owner_id,
                    text=f"🎉 کاربر جدید!\n\n"
                         f"📊 یک کاربر با لینک شما وارد ربات شد\n"
                         f"👤 رفرال های فعلی شما: {current_refs}"
                )
            except:
                pass
    
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
        [InlineKeyboardButton("👤 حساب کاربری", callback_data="user_profile")],
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
    elif data == "user_profile":
        await user_profile_handler(query, context)
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
    elif data == "admin_manage_refs":
        await admin_manage_refs_handler(query, context)
    elif data == "admin_view_orders":
        await admin_view_orders_handler(query, context)
    elif data.startswith("admin_user_"):
        await admin_user_detail_handler(query, data, context)
    elif data.startswith("admin_set_refs_"):
        await admin_set_refs_handler(query, data, context)

# منوی اصلی
async def main_menu_handler(query, context):
    keyboard = [
        [InlineKeyboardButton("👤 حساب کاربری", callback_data="user_profile")],
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

# حساب کاربری
async def user_profile_handler(query, context):
    user_id = query.from_user.id
    username = query.from_user.username or "بدون یوزرنیم"
    first_name = query.from_user.first_name or "بدون نام"
    
    # گرفتن اطلاعات از دیتابیس
    user_refs = db.get_user_referrals(user_id)
    
    # ایجاد متن حساب کاربری
    profile_text = (
        f"👤 حساب کاربری\n\n"
        f"نام کاربری 🌹 | {first_name}\n"
        f"یوزرنیم شما ✌️ | @{username}\n"
        f"شناسه عددی 🆔 | {user_id}\n"
        f"موجودی رفرال 💎 | {user_refs}\n\n"
        f"📊 شما تاکنون {user_refs} رفرال جمع آوری کرده‌اید!"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        profile_text,
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
    username = query.from_user.username or "بدون یوزرنیم"
    package = data.replace("jam_", "")
    jam_info = JAM_PACKAGES.get(package)
    user_refs = db.get_user_referrals(user_id)
    
    if user_refs >= jam_info['required_refs']:
        db.deduct_referrals(user_id, jam_info['required_refs'])
        # ذخیره سفارش در دیتابیس
        db.add_order(user_id, username, "جم", f"{jam_info['jam']} جم", jam_info['jam'], jam_info['required_refs'])
        
        message_text = (
            f"✅ خرید شما با موفقیت ثبت شد!\n\n"
            f"📞 برای دریافت جم به ایدی زیر پیام بدید:\n{ADMIN_USERNAMES[0]}"
        )
        
        # ارسال پیام به ادمین‌ها
        admin_message = (
            f"🛒 سفارش جدید!\n\n"
            f"👤 کاربر: @{username}\n"
            f"🎁 محصول: {jam_info['jam']} جم\n"
            f"📊 رفرال مصرف شده: {jam_info['required_refs']}\n"
            f"🆔 آی‌دی: {user_id}"
        )
        await send_to_admins(context.bot, admin_message)
        
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
    username = query.from_user.username or "بدون یوزرنیم"
    package = data.replace("card_", "")
    card_info = CARD_PACKAGES.get(package)
    user_refs = db.get_user_referrals(user_id)
    
    if user_refs >= card_info['required_refs']:
        db.deduct_referrals(user_id, card_info['required_refs'])
        # ذخیره سفارش در دیتابیس
        db.add_order(user_id, username, "کارت به کارت", f"{card_info['amount']:,} تومان", card_info['amount'], card_info['required_refs'])
        
        message_text = (
            f"✅ خرید شما با موفقیت ثبت شد!\n\n"
            f"💸 برای دریافت پول، شماره کارت خود را به ایدی زیر ارسال کنید:\n{ADMIN_USERNAMES[0]}"
        )
        
        # ارسال پیام به ادمین‌ها
        admin_message = (
            f"🛒 سفارش جدید!\n\n"
            f"👤 کاربر: @{username}\n"
            f"💳 محصول: {card_info['amount']:,} تومان\n"
            f"📊 رفرال مصرف شده: {card_info['required_refs']}\n"
            f"🆔 آی‌دی: {user_id}"
        )
        await send_to_admins(context.bot, admin_message)
        
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
    
    if not is_admin(user_id, username):
        await query.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    total_users = db.get_total_users()
    pending_orders = db.get_pending_orders_count()
    
    keyboard = [
        [InlineKeyboardButton("📊 مدیریت رفرال کاربران", callback_data="admin_manage_refs")],
        [InlineKeyboardButton("📋 بررسی سفارش ها", callback_data="admin_view_orders")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👨‍💼 پنل مدیریت\n\n"
        f"📊 تعداد کل کاربران: {total_users}\n"
        f"🛒 سفارش‌های pending: {pending_orders}\n"
        f"👤 ادمین‌ها: {', '.join(ADMIN_USERNAMES)}",
        reply_markup=reply_markup
    )

# مدیریت رفرال کاربران توسط ادمین
async def admin_manage_refs_handler(query, context):
    user_id = query.from_user.id
    username = query.from_user.username
    
    if not is_admin(user_id, username):
        await query.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    users = db.get_all_users()
    
    if not users:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ هیچ کاربری وجود ندارد!", reply_markup=reply_markup)
        return
    
    keyboard = []
    for user in users[:50]:
        user_id, username, referrals = user
        user_display = f"@{username}" if username else f"User#{user_id}"
        keyboard.append([InlineKeyboardButton(
            f"{user_display} - {referrals} رفرال", 
            callback_data=f"admin_user_{user_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👥 لیست کاربران:\n\n"
        "برای مدیریت رفرال هر کاربر، روی آن کلیک کنید:",
        reply_markup=reply_markup
    )

# مشاهده سفارش‌ها توسط ادمین
async def admin_view_orders_handler(query, context):
    user_id = query.from_user.id
    username = query.from_user.username
    
    if not is_admin(user_id, username):
        await query.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    orders = db.get_all_orders()
    
    if not orders:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ هیچ سفارشی وجود ندارد!", reply_markup=reply_markup)
        return
    
    orders_text = "📋 لیست سفارش‌ها:\n\n"
    
    for i, order in enumerate(orders[:20], 1):
        user_id, username, product_type, product_name, amount, refs_used, order_date = order
        
        order_date_str = order_date.split('.')[0] if '.' in order_date else order_date
        
        orders_text += (
            f"🛒 سفارش #{i}\n"
            f"👤 کاربر: @{username or 'بدون یوزرنیم'}\n"
            f"🆔 آی‌دی: {user_id}\n"
            f"📦 محصول: {product_name}\n"
            f"📊 رفرال مصرف شده: {refs_used}\n"
            f"⏰ تاریخ: {order_date_str}\n"
            f"────────────────────\n\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(orders_text, reply_markup=reply_markup)

# جزئیات کاربر برای ادمین
async def admin_user_detail_handler(query, data, context):
    user_id = query.from_user.id
    username = query.from_user.username
    
    if not is_admin(user_id, username):
        await query.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    target_user_id = int(data.replace("admin_user_", ""))
    target_user = db.get_user(target_user_id)
    
    if not target_user:
        await query.answer("❌ کاربر پیدا نشد!", show_alert=True)
        return
    
    target_username = target_user[1] or "بدون یوزرنیم"
    current_refs = db.get_user_referrals(target_user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ افزایش رفرال", callback_data=f"admin_set_refs_{target_user_id}_inc")],
        [InlineKeyboardButton("➖ کاهش رفرال", callback_data=f"admin_set_refs_{target_user_id}_dec")],
        [InlineKeyboardButton("🔢 تنظیم دستی رفرال", callback_data=f"admin_set_refs_{target_user_id}_manual")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_manage_refs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👤 اطلاعات کاربر:\n\n"
        f"🆔 آی‌دی: {target_user_id}\n"
        f"👤 یوزرنیم: @{target_username}\n"
        f"📊 رفرال های فعلی: {current_refs}",
        reply_markup=reply_markup
    )

# تنظیم رفرال کاربر
async def admin_set_refs_handler(query, data, context):
    user_id = query.from_user.id
    username = query.from_user.username
    
    if not is_admin(user_id, username):
        await query.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    parts = data.replace("admin_set_refs_", "").split("_")
    target_user_id = int(parts[0])
    action = parts[1]
    
    target_user = db.get_user(target_user_id)
    if not target_user:
        await query.answer("❌ کاربر پیدا نشد!", show_alert=True)
        return
    
    current_refs = db.get_user_referrals(target_user_id)
    target_username = target_user[1] or "بدون یوزرنیم"
    
    if action == "inc":
        db.set_user_referrals(target_user_id, current_refs + 1)
        new_refs = current_refs + 1
        message = f"✅ رفرال کاربر @{target_username} افزایش یافت\n\nرفرال جدید: {new_refs}"
    
    elif action == "dec":
        new_refs = max(0, current_refs - 1)
        db.set_user_referrals(target_user_id, new_refs)
        message = f"✅ رفرال کاربر @{target_username} کاهش یافت\n\nرفرال جدید: {new_refs}"
    
    elif action == "manual":
        # ذخیره وضعیت برای دریافت عدد از کاربر
        user_set_refs_state[user_id] = {
            'target_user_id': target_user_id,
            'target_username': target_username,
            'current_refs': current_refs
        }
        
        message = (
            f"🔢 تنظیم دستی رفرال برای کاربر @{target_username}\n\n"
            f"📊 رفرال فعلی: {current_refs}\n\n"
            f"لطفاً عدد جدید رفرال را ارسال کنید:"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_user_{target_user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)

# هندلر برای دریافت عدد از کاربر
async def handle_set_refs_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ شما دسترسی به این بخش را ندارید!")
        return
    
    if user_id not in user_set_refs_state:
        await update.message.reply_text("❌ درخواست نامعتبر!")
        return
    
    try:
        new_refs = int(update.message.text)
        if new_refs < 0:
            await update.message.reply_text("❌ عدد نمی‌تواند منفی باشد!")
            return
        
        target_info = user_set_refs_state[user_id]
        target_user_id = target_info['target_user_id']
        target_username = target_info['target_username']
        
        # تنظیم رفرال جدید
        db.set_user_referrals(target_user_id, new_refs)
        
        # حذف وضعیت
        del user_set_refs_state[user_id]
        
        await update.message.reply_text(
            f"✅ رفرال کاربر @{target_username} تنظیم شد\n\n"
            f"📊 رفرال جدید: {new_refs}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر ارسال کنید!")

# اجرای ربات
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_refs_number))
    
    print("🤖 ربات فعال شد...")
    application.run_polling()

if __name__ == "__main__":
    main()
