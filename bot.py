import logging
import os
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from database import Database

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# ==================== USER HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.full_name)

    if db.is_admin(user.id):
        await show_admin_panel(update, context)
        return

    settings = db.get_settings()
    welcome_text = settings.get('welcome_text',
        "🏛 <b>DLS Ismoilovning OpenBudget Ovoz Berish Botiga Xush Kelibsiz!</b>\n\n"
        "Ushbu bot orqali siz loyihalarga ovoz berishingiz mumkin. Ovoz bering va sovg'alarga ega bo'ling. \n\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    keyboard = [
        [KeyboardButton("🗳 Ovoz Berish")],
        [KeyboardButton("📋 Ma'lumotlar"), KeyboardButton("🎓 Video Qo'llanma")],
    ]
    await update.message.reply_text(
        welcome_text, parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def vote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = db.get_settings()
    vote_link = settings.get('vote_link', '')
    vote_text = settings.get('vote_text',
        "🗳 <b>Ovoz Berish</b>\n\n"
        "Quyidagi tugma orqali ovoz berish sahifasiga o'ting.\n"
        "Ovoz berganingizdan so'ng <b>screenshot</b> olib, shu yerga yuboring.\n\n"
        "📸 Screenshot yuborilgandan so'ng adminlar tekshirib siz bilan bog'lanishadi."
    )
    if not vote_link:
        await update.message.reply_text(
            "⚠️ Hozircha ovoz berish linki sozlanmagan. Iltimos, keyinroq urinib ko'ring."
        )
        return
    keyboard = [
        [InlineKeyboardButton("🗳 Ovoz Berish Sahifasiga O'tish", url=vote_link)],
        [InlineKeyboardButton("📸 Screenshot Yuborish", callback_data="send_screenshot")]
    ]
    await update.message.reply_text(
        vote_text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def screenshot_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 <b>Screenshot Yuborish</b>\n\n"
        "Iltimos, ovoz berganingizni tasdiqlovchi <b>screenshot rasmini</b> shu yerga yuboring.\n\n"
        "⚠️ Faqat rasm (foto) qabul qilinadi.",
        parse_mode='HTML'
    )
    context.user_data['waiting_screenshot'] = True


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if db.is_admin(user.id) and context.user_data.get('admin_action') == 'set_video':
        return
    if not context.user_data.get('waiting_screenshot'):
        return

    photo = update.message.photo[-1]
    db.save_screenshot(user.id, photo.file_id, user.full_name, user.username)

    admins = db.get_admins()
    for admin_id in admins:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=(
                    f"📸 <b>Yangi Screenshot!</b>\n\n"
                    f"👤 Foydalanuvchi: <b>{user.full_name}</b>\n"
                    f"🆔 Username: @{user.username or 'yoq'}\n"
                    f"🔢 ID: <code>{user.id}</code>\n\n"
                    f"Foydalanuvchi bilan bog'lanish uchun ID dan foydalaning."
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    context.user_data['waiting_screenshot'] = False
    await update.message.reply_text(
        "✅ <b>Screenshot muvaffaqiyatli yuborildi!</b>\n\n"
        "🔍 Adminlar tekshirib, tez orada siz bilan <b>aloqaga chiqishadi</b>.\n\n"
        "Rahmat! 🙏",
        parse_mode='HTML'
    )


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = db.get_settings()
    info_text = settings.get('info_text',
        "📋 <b>Ma'lumotlar</b>\n\n"
        "Bu bo'limda OpenBudget haqida ma'lumotlar joylashtiriladi.\n\n"
        "Admin tomonidan ma'lumotlar kiritilmagan."
    )
    keyboard = [[InlineKeyboardButton("🏠 Bosh Sahifa", callback_data="main_menu")]]
    await update.message.reply_text(
        info_text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def video_guide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = db.get_settings()
    video_file_id = settings.get('guide_video_id', '')
    video_text = settings.get('video_text',
        "🎓 <b>Video Qo'llanma</b>\n\n"
        "Ovoz berish jarayonini o'rganish uchun quyidagi videoni tomosha qiling."
    )
    keyboard = [[InlineKeyboardButton("🏠 Bosh Sahifa", callback_data="main_menu")]]
    if video_file_id:
        await update.message.reply_video(
            video=video_file_id, caption=video_text,
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "🎓 <b>Video Qo'llanma</b>\n\n"
            "⚠️ Hozircha video qo'llanma yuklanmagan.\nIltimos, keyinroq urinib ko'ring.",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if db.is_admin(user.id):
        await show_admin_panel_edit(query)
        return
    settings = db.get_settings()
    welcome_text = settings.get('welcome_text', "🏛 <b>OpenBudget Ovoz Berish Botiga Xush Kelibsiz!</b>")
    keyboard = [
        [KeyboardButton("🗳 Ovoz Berish")],
        [KeyboardButton("📋 Ma'lumotlar"), KeyboardButton("🎓 Video Qo'llanma")],
    ]
    await query.message.reply_text(
        welcome_text, parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# ==================== ADMIN HELPERS ====================

def build_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Ovoz Berish Linkini O'zgartirish", callback_data="admin_set_link")],
        [InlineKeyboardButton("📝 Xush Kelibsiz Matni", callback_data="admin_set_welcome")],
        [InlineKeyboardButton("📋 Ma'lumotlar Matni", callback_data="admin_set_info")],
        [InlineKeyboardButton("🎬 Video Qo'llanma Yuklash", callback_data="admin_set_video")],
        [
            InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users_p1"),
        ],
        [InlineKeyboardButton("📸 Screenshotlar", callback_data="admin_screenshots_p1")],
        [InlineKeyboardButton("🔐 Adminlar Boshqaruvi", callback_data="admin_manage")],
    ])


def get_admin_panel_text():
    stats = db.get_stats()
    return (
        f"⚙️ <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['users']}</b>\n"
        f"📸 Jami screenshotlar: <b>{stats['screenshots']}</b>\n"
        f"🗳 Ovoz berganlar (unique): <b>{stats['voters']}</b>"
    )


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        get_admin_panel_text(), parse_mode='HTML',
        reply_markup=build_admin_keyboard()
    )


async def show_admin_panel_edit(query):
    try:
        await query.message.edit_text(
            get_admin_panel_text(), parse_mode='HTML',
            reply_markup=build_admin_keyboard()
        )
    except Exception:
        await query.message.reply_text(
            get_admin_panel_text(), parse_mode='HTML',
            reply_markup=build_admin_keyboard()
        )


# ==================== ADMIN CALLBACK ====================

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not db.is_admin(user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await query.answer()
    data = query.data

    if data == "admin_set_link":
        context.user_data['admin_action'] = 'set_link'
        await query.message.reply_text(
            "🔗 <b>Yangi ovoz berish linkini yuboring:</b>\n(https:// bilan boshlansin)",
            parse_mode='HTML'
        )

    elif data == "admin_set_welcome":
        context.user_data['admin_action'] = 'set_welcome'
        await query.message.reply_text(
            "📝 <b>Yangi xush kelibsiz matnini yuboring:</b>\nHTML mumkin: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;",
            parse_mode='HTML'
        )

    elif data == "admin_set_info":
        context.user_data['admin_action'] = 'set_info'
        await query.message.reply_text(
            "📋 <b>Yangi ma'lumotlar matnini yuboring:</b>\nHTML mumkin: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;",
            parse_mode='HTML'
        )

    elif data == "admin_set_video":
        context.user_data['admin_action'] = 'set_video'
        await query.message.reply_text(
            "🎬 <b>Video faylini yuboring (MP4):</b>",
            parse_mode='HTML'
        )

    # --- Statistika ---
    elif data == "admin_stats":
        stats = db.get_stats()
        top_voters = db.get_top_voters(5)
        text = (
            f"📊 <b>Statistika</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{stats['users']}</b>\n"
            f"📸 Jami screenshotlar: <b>{stats['screenshots']}</b>\n"
            f"🗳 Ovoz berganlar (unique): <b>{stats['voters']}</b>\n\n"
        )
        if top_voters:
            text += "🏆 <b>Ko'p ovoz berganlar (Top 5):</b>\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, v in enumerate(top_voters):
                uname = f"@{v['username']}" if v['username'] else v['full_name']
                text += f"{medals[i]} {uname} — <b>{v['vote_count']} ta ovoz</b>\n"
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]
        await query.message.reply_text(text, parse_mode='HTML',
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    # --- Foydalanuvchilar ro'yxati ---
    elif data.startswith("admin_users_p"):
        page = int(data.replace("admin_users_p", ""))
        per_page = 10
        voters = db.get_voters_list(page, per_page)
        total = db.get_stats()['voters']
        total_pages = max(1, (total + per_page - 1) // per_page)

        if not voters:
            text = "👥 <b>Hali ovoz bergan foydalanuvchi yo'q.</b>"
        else:
            text = f"👥 <b>Ovoz Berganlar Ro'yxati</b>  ({page}/{total_pages}-sahifa)\n\n"
            for i, v in enumerate(voters, start=(page - 1) * per_page + 1):
                uname = f"@{v['username']}" if v['username'] else "username yo'q"
                text += (
                    f"{i}. <b>{v['full_name']}</b>\n"
                    f"   {uname} | ID: <code>{v['user_id']}</code>\n"
                    f"   🗳 Ovozlar soni: <b>{v['vote_count']} ta</b>\n\n"
                )

        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin_users_p{page-1}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("➡️ Keyingi", callback_data=f"admin_users_p{page+1}"))

        keyboard = []
        if nav:
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        await query.message.reply_text(text, parse_mode='HTML',
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    # --- Screenshotlar ---
    elif data.startswith("admin_screenshots_p"):
        page = int(data.replace("admin_screenshots_p", ""))
        per_page = 8
        screenshots = db.get_screenshots_paged(page, per_page)
        total = db.get_stats()['screenshots']
        total_pages = max(1, (total + per_page - 1) // per_page)

        if not screenshots:
            text = "📸 <b>Hali screenshot yo'q.</b>"
        else:
            text = f"📸 <b>Screenshotlar</b>  ({page}/{total_pages}-sahifa)\n\n"
            for i, s in enumerate(screenshots, start=(page - 1) * per_page + 1):
                uname = f"@{s['username']}" if s['username'] else "—"
                text += (
                    f"{i}. <b>{s['full_name']}</b> {uname}\n"
                    f"   ID: <code>{s['user_id']}</code> | 📅 {s['created_at']}\n\n"
                )

        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin_screenshots_p{page-1}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("➡️ Keyingi", callback_data=f"admin_screenshots_p{page+1}"))

        keyboard = []
        if nav:
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        await query.message.reply_text(text, parse_mode='HTML',
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    # --- Adminlar ---
    elif data == "admin_manage":
        admins = db.get_admins_info()
        text = "🔐 <b>Adminlar Ro'yxati:</b>\n\n"
        for i, a in enumerate(admins, 1):
            text += f"{i}. {a['full_name']} | ID: <code>{a['user_id']}</code>\n"
        keyboard = [
            [InlineKeyboardButton("➕ Admin Qo'shish", callback_data="admin_add")],
            [InlineKeyboardButton("➖ Admin O'chirish", callback_data="admin_remove")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")],
        ]
        await query.message.reply_text(text, parse_mode='HTML',
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_add":
        context.user_data['admin_action'] = 'add_admin'
        await query.message.reply_text(
            "➕ <b>Yangi admin Telegram ID sini yuboring:</b>", parse_mode='HTML'
        )

    elif data == "admin_remove":
        context.user_data['admin_action'] = 'remove_admin'
        await query.message.reply_text(
            "➖ <b>O'chiriladigan admin ID sini yuboring:</b>", parse_mode='HTML'
        )

    elif data == "admin_back":
        await show_admin_panel_edit(query)


# ==================== ADMIN INPUT HANDLERS ====================

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    action = context.user_data.get('admin_action')
    if not db.is_admin(user.id) or not action:
        return
    text = update.message.text

    if action == 'set_link':
        if not text.startswith('http'):
            await update.message.reply_text("❌ Link https:// bilan boshlanishi kerak!")
            return
        db.update_setting('vote_link', text)
        await update.message.reply_text("✅ Ovoz berish linki yangilandi!")
        context.user_data['admin_action'] = None

    elif action == 'set_welcome':
        db.update_setting('welcome_text', text)
        await update.message.reply_text("✅ Xush kelibsiz matni yangilandi!")
        context.user_data['admin_action'] = None

    elif action == 'set_info':
        db.update_setting('info_text', text)
        await update.message.reply_text("✅ Ma'lumotlar matni yangilandi!")
        context.user_data['admin_action'] = None

    elif action == 'add_admin':
        try:
            new_id = int(text.strip())
            db.add_admin(new_id)
            await update.message.reply_text(
                f"✅ Admin qo'shildi: <code>{new_id}</code>", parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID! Faqat raqam kiriting.")
        context.user_data['admin_action'] = None

    elif action == 'remove_admin':
        try:
            rem_id = int(text.strip())
            db.remove_admin(rem_id)
            await update.message.reply_text(
                f"✅ Admin o'chirildi: <code>{rem_id}</code>", parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID! Faqat raqam kiriting.")
        context.user_data['admin_action'] = None


async def admin_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    action = context.user_data.get('admin_action')
    if not db.is_admin(user.id) or action != 'set_video':
        return
    if update.message.video:
        db.update_setting('guide_video_id', update.message.video.file_id)
        await update.message.reply_text("✅ Video qo'llanma yangilandi!")
        context.user_data['admin_action'] = None
    else:
        await update.message.reply_text("❌ Iltimos, video fayl yuboring!")


# ==================== MAIN ====================

def main():
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi! .env faylni tekshiring.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🗳 Ovoz Berish$"), vote_handler))
    app.add_handler(MessageHandler(filters.Regex("^📋 Ma'lumotlar$"), info_handler))
    app.add_handler(MessageHandler(filters.Regex("^🎓 Video Qo'llanma$"), video_guide_handler))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Admin Panel$"), admin_panel_handler))

    app.add_handler(CallbackQueryHandler(screenshot_button_handler, pattern="^send_screenshot$"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

    app.add_handler(MessageHandler(filters.VIDEO, admin_video_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))

    print("🤖 OpenBudget Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        await update.message.reply_text("❌ Sizda admin huquqi yo'q.")
        return
    await show_admin_panel(update, context)


if __name__ == '__main__':
    main()
