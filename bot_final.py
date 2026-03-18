import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# ─────────────────────────────────────────
#  НАСТРОЙКИ
# ─────────────────────────────────────────
BOT_TOKEN = "8047692214:AAFavW7zNtuZ_ePRC5NRH6G24_ajJInxD0g"
ADMIN_ID  = 658117827

# ─────────────────────────────────────────
#  ТЕКСТЫ
# ─────────────────────────────────────────
POLICY = """
📜 *Правила и политика сервиса*

Добро пожаловать! Прежде чем начать, пожалуйста, ознакомься с нашими правилами:

*1. Оплата*
Предоплата 50% до начала работы, остаток — после сдачи готового материала.

*2. Сроки*
Сроки выполнения обсуждаются индивидуально. Срочные заказы возможны за дополнительную плату.

*3. Правки*
Каждый заказ включает 2 бесплатные правки. Последующие — по договорённости.

*4. Исходники*
Файлы в формате WAV/AIFF, 24 bit / 44.1 kHz. За качество исходников отвечает клиент.

*5. Авторские права*
Материалы передаются после полной оплаты. Мы оставляем право использовать работы в портфолио.

*6. Конфиденциальность*
Мы не передаём данные и материалы клиента третьим лицам.

*7. Отказ от заказа*
При отказе после начала работы предоплата не возвращается.

Нажимая *«Принимаю ✅»*, ты подтверждаешь согласие с правилами.
"""

PRICE_LIST = """
🎛 *Прайс-лист*

🎚 *Сведение + Мастеринг* — от 2 000 ₽
_Балансировка звука, обработка каждого трека, финальный мастеринг для стриминга_

🎨 *Обложка для трека* — 1 500 ₽
_Уникальный дизайн в твоём стиле, форматы для всех платформ_

📣 *Продвижение трека* — от 5 000 ₽
_Размещение на плейлистах, реклама в соцсетях_

🎵 *Написание текста* — 1 000 ₽
_Пишу текст под твой бит и концепцию_

🎹 *Бит* — от 2 000 ₽
_Авторский бит под твой жанр и настроение. Также можем перебить любой бит_

💡 Точная цена зависит от сложности проекта.
Оставь заявку — рассчитаю индивидуально!
"""

FAQ = """
❓ *Часто задаваемые вопросы*

*— В каком формате присылать файлы?*
Присылай WAV или AIFF, минимум 24 bit / 44.1 kHz. MP3 не принимаю.

*— Сколько времени занимает работа?*
Сведение + Мастеринг: сроки обсуждаются индивидуально.
Обложка: 1–3 рабочих дня.
Написание текста: 1–3 рабочих дня.
Продвижение: обговаривается индивидуально.
Срочный заказ — обсуждается отдельно.

*— Как передать файлы?*
Через ссылку на Google Drive или Яндекс Диск.

*— Сколько правок включено?*
2 бесплатные правки. Далее — по договорённости.

*— Как оплатить?*
После согласования заказа выставляю счёт.
Принимаю оплату на карту или по реквизитам.

*— Где найти вас официально?*
Наш официальный канал: @kartxfan_prod
Наш единственный представитель: @no_swag

Остерегайтесь мошенников — мы не пишем первыми и не работаем через других людей.
"""

# ─────────────────────────────────────────
#  СТАТУСЫ
# ─────────────────────────────────────────
STATUSES = {
    "new":         ("🆕", "Новый"),
    "in_progress": ("⚙️", "В работе"),
    "review":      ("🔍", "На проверке"),
    "done":        ("✅", "Готово"),
    "cancelled":   ("❌", "Отменён"),
}

# ─────────────────────────────────────────
#  СОСТОЯНИЯ ДИАЛОГОВ
# ─────────────────────────────────────────
ASK_SERVICE, ASK_TRACK_COUNT, ASK_GENRE, ASK_DRIVE_LINK, ASK_COMMENT, CONFIRM_ORDER = range(6)
REVIEW_SELECT, REVIEW_RATE, REVIEW_WRITE = range(10, 13)
JOB_NAME, JOB_SKILLS, JOB_EXPERIENCE, JOB_CONFIRM = range(20, 24)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  БАЗА ДАННЫХ
# ─────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect("orders.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            username    TEXT,
            service     TEXT,
            track_count TEXT,
            genre       TEXT,
            drive_link  TEXT,
            comment     TEXT,
            status      TEXT DEFAULT 'new',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT,
            order_id   INTEGER,
            rating     INTEGER,
            text       TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS policy_accepted (
            user_id  INTEGER PRIMARY KEY,
            accepted INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS job_applications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT,
            name       TEXT,
            skills     TEXT,
            experience TEXT,
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()


def add_order(user_id, username, service, track_count, genre, drive_link, comment):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO orders (user_id,username,service,track_count,genre,drive_link,comment,status,created_at) VALUES (?,?,?,?,?,?,?,'new',?)",
        (user_id, username, service, track_count, genre, drive_link, comment, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_order(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return row


def get_orders_by_user(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    return rows


def get_all_orders(status_filter=None):
    conn = get_conn()
    if status_filter:
        rows = conn.execute("SELECT * FROM orders WHERE status=? ORDER BY id DESC", (status_filter,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def update_order_status(order_id, status):
    conn = get_conn()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()


def has_accepted_policy(user_id):
    conn = get_conn()
    row = conn.execute("SELECT accepted FROM policy_accepted WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row and row["accepted"]


def set_policy_accepted(user_id):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO policy_accepted (user_id, accepted) VALUES (?, 1)", (user_id,))
    conn.commit()
    conn.close()


def add_review(user_id, username, order_id, rating, text):
    conn = get_conn()
    conn.execute(
        "INSERT INTO reviews (user_id,username,order_id,rating,text,created_at) VALUES (?,?,?,?,?,?)",
        (user_id, username, order_id, rating, text, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    conn.close()


def get_all_reviews():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def add_job(user_id, username, name, skills, experience):
    conn = get_conn()
    conn.execute(
        "INSERT INTO job_applications (user_id,username,name,skills,experience,created_at) VALUES (?,?,?,?,?,?)",
        (user_id, username, name, skills, experience, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    conn.close()


def get_all_jobs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM job_applications ORDER BY id DESC").fetchall()
    conn.close()
    return rows


# ─────────────────────────────────────────
#  КЛАВИАТУРЫ И ФОРМАТИРОВАНИЕ
# ─────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛 Оставить заявку",  callback_data="new_order")],
        [InlineKeyboardButton("📦 Мои заказы",       callback_data="my_orders")],
        [InlineKeyboardButton("⭐ Оставить отзыв",   callback_data="new_review")],
        [InlineKeyboardButton("💰 Прайс-лист",       callback_data="prices")],
        [InlineKeyboardButton("❓ FAQ",               callback_data="faq")],
        [InlineKeyboardButton("🏠 О нас",            callback_data="about")],
    ])


def back_to_menu_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")]])


def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Новые",       callback_data="af_new"),
         InlineKeyboardButton("⚙️ В работе",    callback_data="af_in_progress")],
        [InlineKeyboardButton("🔍 На проверке", callback_data="af_review"),
         InlineKeyboardButton("✅ Готовые",     callback_data="af_done")],
        [InlineKeyboardButton("📋 Все заказы",  callback_data="af_all")],
        [InlineKeyboardButton("⭐ Отзывы",      callback_data="admin_reviews")],
        [InlineKeyboardButton("🤝 Анкеты",      callback_data="admin_jobs")],
    ])


def format_order(row):
    emoji, label = STATUSES.get(row["status"], ("❓", row["status"]))
    # Экранируем спецсимволы в пользовательских данных
    comment = str(row["comment"]).replace("_", "\\_").replace("*", "\\*")
    return (
        f"📋 *Заказ №{row['id']}*\n"
        f"👤 @{row['username']}\n"
        f"🎵 Услуга: {row['service']}\n"
        f"🎼 Кол-во: {row['track_count']}\n"
        f"🎸 Жанр/стиль: {row['genre']}\n"
        f"🔗 Ссылка: {row['drive_link']}\n"
        f"💬 Комментарий: {comment}\n"
        f"📅 Дата: {row['created_at']}\n"
        f"Статус: {emoji} {label}"
    )


# ─────────────────────────────────────────
#  СТАРТ
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if has_accepted_policy(update.effective_user.id):
        await update.message.reply_text(
            "👋 Привет! Выбери, что тебя интересует:",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            POLICY,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Принимаю ✅", callback_data="accept_policy")]]),
        )


# ─────────────────────────────────────────
#  ГЛАВНОЕ МЕНЮ
# ─────────────────────────────────────────
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "accept_policy":
        set_policy_accepted(query.from_user.id)
        await query.edit_message_text(
            "✅ Отлично! Добро пожаловать!\n\nВыбери, что тебя интересует:",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "back_to_menu":
        await query.edit_message_text("Выбери, что тебя интересует:", reply_markup=main_menu_keyboard())

    elif data == "prices":
        await query.edit_message_text(PRICE_LIST, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎛 Оставить заявку", callback_data="new_order")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")],
            ]))

    elif data == "faq":
        await query.edit_message_text(FAQ, parse_mode="Markdown", reply_markup=back_to_menu_btn())

    elif data == "about":
        await query.edit_message_text(
            "🏠 *О нас — kartxfan prod*\n\n"
            "Мы занимаемся профессиональным производством музыки: сведение, мастеринг, биты, обложки, тексты и продвижение.\n\n"
            "Наша цель — помочь артистам звучать на уровне мировых стандартов 🎵\n\n"
            "Хочешь стать частью команды?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤝 Хочу работать в kartxfan prod", callback_data="job_apply")],
                [InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")],
            ]))

    elif data == "my_orders":
        rows = get_orders_by_user(query.from_user.id)
        if not rows:
            await query.edit_message_text("У тебя пока нет заказов.", reply_markup=back_to_menu_btn())
            return
        text = "📦 *Твои заказы:*\n\n"
        for row in rows:
            emoji, label = STATUSES.get(row["status"], ("❓", row["status"]))
            text += f"№{row['id']} — {row['service']} — {emoji} {label}\n"
        buttons = [[InlineKeyboardButton(f"Подробнее №{r['id']}", callback_data=f"od_{r['id']}")] for r in rows]
        buttons.append([InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("od_"):
        order_id = int(data[3:])
        row = get_order(order_id)
        if not row or row["user_id"] != query.from_user.id:
            await query.edit_message_text("Заказ не найден.", reply_markup=back_to_menu_btn())
            return
        await query.edit_message_text(format_order(row), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="my_orders")]]))


# ─────────────────────────────────────────
#  ДИАЛОГ: ЗАКАЗ
# ─────────────────────────────────────────
async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "🎛 *Оформление заявки*\n\nШаг 1/5 — Какая услуга тебя интересует?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎚 Сведение + Мастеринг", callback_data="svc_both")],
            [InlineKeyboardButton("🎨 Обложка для трека",    callback_data="svc_cover")],
            [InlineKeyboardButton("📣 Продвижение трека",    callback_data="svc_promo")],
            [InlineKeyboardButton("🎵 Написание текста",     callback_data="svc_lyrics")],
            [InlineKeyboardButton("🎹 Бит",                  callback_data="svc_beat")],
            [InlineKeyboardButton("❌ Отмена",               callback_data="cancel_order")],
        ]),
    )
    return ASK_SERVICE


SVC_MAP = {
    "svc_both":   "Сведение + Мастеринг",
    "svc_cover":  "Обложка для трека",
    "svc_promo":  "Продвижение трека",
    "svc_lyrics": "Написание текста",
    "svc_beat":   "Бит",
}


async def ask_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["service"] = SVC_MAP[query.data]
    await query.edit_message_text(
        "Шаг 2/5 — Сколько единиц нужно обработать?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1",    callback_data="cnt_1"),
             InlineKeyboardButton("2–5",  callback_data="cnt_2-5")],
            [InlineKeyboardButton("6–10", callback_data="cnt_6-10"),
             InlineKeyboardButton("10+",  callback_data="cnt_10+")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")],
        ]))
    return ASK_TRACK_COUNT


async def ask_track_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["track_count"] = query.data[4:]  # убираем "cnt_"
    await query.edit_message_text(
        "Шаг 3/5 — Напиши жанр или стиль.\n\n_Например: хип-хоп, поп, рок, электронная..._",
        parse_mode="Markdown")
    return ASK_GENRE


async def ask_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["genre"] = update.message.text
    await update.message.reply_text(
        "Шаг 4/5 — Отправь ссылку на Google Drive или Яндекс Диск.\n\n"
        "_Убедись, что доступ по ссылке открыт для всех._",
        parse_mode="Markdown")
    return ASK_DRIVE_LINK


async def ask_drive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not link.startswith("http"):
        await update.message.reply_text("⚠️ Отправь корректную ссылку, начинающуюся с http...")
        return ASK_DRIVE_LINK
    context.user_data["drive_link"] = link
    await update.message.reply_text(
        "Шаг 5/5 — Есть пожелания к работе?\n\n_Если нет — отправь прочерк._",
        parse_mode="Markdown")
    return ASK_COMMENT


async def ask_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text
    d = context.user_data
    await update.message.reply_text(
        f"📋 *Проверь заявку:*\n\n"
        f"🎵 Услуга: *{d['service']}*\n"
        f"🎼 Кол-во: *{d['track_count']}*\n"
        f"🎸 Жанр: *{d['genre']}*\n"
        f"🔗 {d['drive_link']}\n"
        f"💬 {d['comment']}\n\nВсё верно?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Отправить", callback_data="confirm_order")],
            [InlineKeyboardButton("❌ Отменить",  callback_data="cancel_order")],
        ]))
    return CONFIRM_ORDER


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    user = query.from_user
    order_id = add_order(
        user.id, user.username or user.first_name,
        d["service"], d["track_count"], d["genre"], d["drive_link"], d["comment"]
    )
    await query.edit_message_text(
        f"✅ *Заявка №{order_id} принята!*\n\nСвяжусь с тобой в ближайшее время. Спасибо! 🎵",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]]),
    )
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 *Новый заказ №{order_id}*\n\n"
            f"👤 @{user.username or user.first_name}\n"
            f"🎵 {d['service']} | {d['track_count']}\n"
            f"🎸 {d['genre']}\n🔗 {d['drive_link']}\n💬 {d['comment']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Открыть заказ", callback_data=f"aord_{order_id}")]]),
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа: {e}")
    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Заявка отменена.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]]))
    return ConversationHandler.END


# ─────────────────────────────────────────
#  ДИАЛОГ: ОТЗЫВ
# ─────────────────────────────────────────
async def new_review_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    done = [r for r in get_orders_by_user(query.from_user.id) if r["status"] == "done"]
    if not done:
        await query.edit_message_text(
            "⭐ Отзыв можно оставить только после завершения заказа.\nПока завершённых заказов нет.",
            reply_markup=back_to_menu_btn())
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(f"Заказ №{r['id']} — {r['service']}", callback_data=f"rvo_{r['id']}")] for r in done]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_review")])
    await query.edit_message_text("⭐ Выбери заказ для отзыва:", reply_markup=InlineKeyboardMarkup(buttons))
    return REVIEW_SELECT


async def review_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["review_order_id"] = int(query.data[4:])  # убираем "rvo_"
    await query.edit_message_text("Оцени работу:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"{i}⭐", callback_data=f"rvr_{i}") for i in range(1, 6)
        ]]))
    return REVIEW_RATE


async def review_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["review_rating"] = int(query.data[4:])  # убираем "rvr_"
    await query.edit_message_text("Напиши свой отзыв:")
    return REVIEW_WRITE


async def review_write(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    d = context.user_data
    add_review(user.id, user.username or user.first_name, d["review_order_id"], d["review_rating"], update.message.text)
    await update.message.reply_text(
        f"{'⭐' * d['review_rating']} Спасибо за отзыв! 🙏",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]]))
    return ConversationHandler.END


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Отменено.", reply_markup=back_to_menu_btn())
    return ConversationHandler.END


# ─────────────────────────────────────────
#  ДИАЛОГ: АНКЕТА
# ─────────────────────────────────────────
async def job_apply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "🤝 *Анкета — kartxfan prod*\n\nРады, что хочешь к нам!\n\nШаг 1/3 — Как тебя зовут?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_job")]]),
    )
    return JOB_NAME


async def job_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_name"] = update.message.text
    await update.message.reply_text(
        "Шаг 2/3 — Какие у тебя навыки?\n\n"
        "_Например: сведение, мастеринг, дизайн, битмейкинг, SMM..._",
        parse_mode="Markdown")
    return JOB_SKILLS


async def job_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_skills"] = update.message.text
    await update.message.reply_text(
        "Шаг 3/3 — Расскажи об опыте и скинь ссылку на свои лучшие работы.\n\n"
        "_SoundCloud, YouTube, портфолио и т.д. Если ссылки нет — опиши опыт текстом._",
        parse_mode="Markdown")
    return JOB_EXPERIENCE


async def job_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_experience"] = update.message.text
    d = context.user_data
    await update.message.reply_text(
        f"📋 *Проверь анкету:*\n\n"
        f"👤 Имя: {d['job_name']}\n"
        f"🎛 Навыки: {d['job_skills']}\n"
        f"⭐ Опыт: {d['job_experience']}\n\nОтправить?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Отправить", callback_data="confirm_job")],
            [InlineKeyboardButton("❌ Отменить",  callback_data="cancel_job")],
        ]))
    return JOB_CONFIRM


async def confirm_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    user = query.from_user
    add_job(user.id, user.username or user.first_name, d["job_name"], d["job_skills"], d["job_experience"])
    await query.edit_message_text(
        "✅ *Спасибо за заявку!*\n\nЕсли твоя анкета нас заинтересует — с тобой свяжутся в ближайшее время! 🎵",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]]),
    )
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 *Новая анкета!*\n\n"
            f"👤 @{user.username or user.first_name}\n"
            f"📝 {d['job_name']}\n🎛 {d['job_skills']}\n⭐ {d['job_experience']}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа: {e}")
    return ConversationHandler.END


async def cancel_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Анкета отменена.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]]))
    return ConversationHandler.END


# ─────────────────────────────────────────
#  АДМИН-ПАНЕЛЬ
# ─────────────────────────────────────────
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await update.message.reply_text("📊 *Админ-панель*", parse_mode="Markdown", reply_markup=admin_panel_keyboard())


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Нет доступа.")
        return
    await query.answer()
    data = query.data

    # Фильтр заказов
    if data.startswith("af_"):
        status = data[3:]  # убираем "af_"
        rows = get_all_orders(None if status == "all" else status)
        if not rows:
            await query.edit_message_text("Заказов не найдено.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        buttons = [[InlineKeyboardButton(
            f"№{r['id']} {STATUSES.get(r['status'],('❓',''))[0]} {r['username']} — {r['service']}",
            callback_data=f"aord_{r['id']}")] for r in rows]
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
        await query.edit_message_text(f"📋 Найдено заказов: {len(rows)}", reply_markup=InlineKeyboardMarkup(buttons))

    # Детали заказа
    elif data.startswith("aord_"):
        order_id = int(data[5:])  # убираем "ao_"
        row = get_order(order_id)
        if not row:
            await query.edit_message_text("Заказ не найден.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        status_btns = [
            InlineKeyboardButton(f"{e} {l}", callback_data=f"ss_{order_id}_{k}")
            for k, (e, l) in STATUSES.items() if k != row["status"]
        ]
        keyboard = [status_btns[i:i+2] for i in range(0, len(status_btns), 2)]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="af_all")])
        await query.edit_message_text(format_order(row), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Смена статуса — "ss_{order_id}_{status}"
    elif data.startswith("ss_"):
        parts = data[3:].split("_", 1)   # убираем "ss_", делим на id и статус
        order_id = int(parts[0])
        new_status = parts[1]
        update_order_status(order_id, new_status)
        row = get_order(order_id)
        emoji, label = STATUSES.get(new_status, ("❓", new_status))
        try:
            await context.bot.send_message(
                chat_id=row["user_id"],
                text=f"🔔 *Обновление по заказу №{order_id}*\n\nНовый статус: {emoji} *{label}*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")]]),
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить клиента {row['user_id']}: {e}")
        status_btns = [
            InlineKeyboardButton(f"{e} {l}", callback_data=f"ss_{order_id}_{k}")
            for k, (e, l) in STATUSES.items() if k != new_status
        ]
        keyboard = [status_btns[i:i+2] for i in range(0, len(status_btns), 2)]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="af_all")])
        await query.edit_message_text(format_order(get_order(order_id)), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Отзывы
    elif data == "admin_reviews":
        rows = get_all_reviews()
        if not rows:
            await query.edit_message_text("Отзывов пока нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        text = "⭐ *Отзывы клиентов:*\n\n"
        for r in rows:
            text += f"{'⭐' * r['rating']} @{r['username']} (заказ №{r['order_id']})\n{r['text']}\n📅 {r['created_at']}\n\n"
        await query.edit_message_text(text[:4000], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    # Анкеты
    elif data == "admin_jobs":
        rows = get_all_jobs()
        if not rows:
            await query.edit_message_text("Анкет пока нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        text = "🤝 *Анкеты на работу:*\n\n"
        for r in rows:
            text += f"👤 @{r['username']} — {r['name']}\n🎛 {r['skills']}\n⭐ {r['experience']}\n📅 {r['created_at']}\n\n"
        await query.edit_message_text(text[:4000], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    elif data == "admin_back":
        await query.edit_message_text("📊 *Админ-панель*", parse_mode="Markdown", reply_markup=admin_panel_keyboard())


# ─────────────────────────────────────────
#  ЗАПУСК
# ─────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_order_start, pattern="^new_order$")],
        states={
            ASK_SERVICE:     [CallbackQueryHandler(ask_service,     pattern="^svc_")],
            ASK_TRACK_COUNT: [CallbackQueryHandler(ask_track_count, pattern="^cnt_")],
            ASK_GENRE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_genre)],
            ASK_DRIVE_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_drive_link)],
            ASK_COMMENT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_comment)],
            CONFIRM_ORDER:   [CallbackQueryHandler(confirm_order,   pattern="^confirm_order$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_order, pattern="^cancel_order$")],
        allow_reentry=True,
    )

    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_review_start, pattern="^new_review$")],
        states={
            REVIEW_SELECT: [CallbackQueryHandler(review_select, pattern="^rvo_")],
            REVIEW_RATE:   [CallbackQueryHandler(review_rate,   pattern="^rvr_")],
            REVIEW_WRITE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, review_write)],
        },
        fallbacks=[CallbackQueryHandler(cancel_review, pattern="^cancel_review$")],
        allow_reentry=True,
    )

    job_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(job_apply_start, pattern="^job_apply$")],
        states={
            JOB_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, job_name)],
            JOB_SKILLS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, job_skills)],
            JOB_EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_experience)],
            JOB_CONFIRM:    [CallbackQueryHandler(confirm_job, pattern="^confirm_job$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_job, pattern="^cancel_job$")],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(order_conv)
    app.add_handler(review_conv)
    app.add_handler(job_conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(af_|aord_|ss_|admin_reviews|admin_jobs|admin_back)"))
    app.add_handler(CallbackQueryHandler(menu_callback))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
