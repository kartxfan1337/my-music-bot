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
#  НАСТРОЙКИ — заполни перед запуском
# ─────────────────────────────────────────
BOT_TOKEN = "8047692214:AAFavW7zNtuZ_ePRC5NRH6G24_ajJInxD0g"
ADMIN_ID  = 658117827

# ─────────────────────────────────────────
#  ПРАЙС-ЛИСТ
# ─────────────────────────────────────────
PRICE_LIST = """
🎛 *Прайс-лист*

🔹 *Сведение (Mixing)*
• 1 трек — от 2 000 ₽
• EP (3–5 треков) — от 5 000 ₽
• Альбом (6+ треков) — от 8 000 ₽

🔸 *Мастеринг (Mastering)*
• 1 трек — от 1 000 ₽
• EP (3–5 треков) — от 3 000 ₽
• Альбом (6+ треков) — от 5 000 ₽

🔷 *Сведение + Мастеринг*
• 1 трек — от 2 500 ₽
• EP (3–5 треков) — от 6 500 ₽
• Альбом (6+ треков) — от 10 000 ₽

💡 Точная цена зависит от сложности проекта.
Оставь заявку — рассчитаю индивидуально!
"""

# ─────────────────────────────────────────
#  FAQ
# ─────────────────────────────────────────
FAQ = """
❓ *Часто задаваемые вопросы*

*— В каком формате присылать файлы?*
Присылай WAV или AIFF, минимум 24 bit / 44.1 kHz. MP3 не принимаю.

*— Сколько времени занимает работа?*
Сведение: 2–5 рабочих дней.
Мастеринг: 1–2 рабочих дня.
Срочный заказ — обсуждается отдельно.

*— Как передать треки?*
Через ссылку на Google Drive или Яндекс Диск.

*— Сколько правок включено?*
2 бесплатные правки. Далее — по договорённости.

*— Как оплатить?*
После согласования заказа выставляю счёт.
Принимаю оплату на карту или по реквизитам.

*— Работаешь с любыми жанрами?*
Да — поп, хип-хоп, электронная музыка, рок, джаз и другие.
"""

# Статусы заказов
STATUSES = {
    "new":         ("🆕", "Новый"),
    "in_progress": ("⚙️", "В работе"),
    "review":      ("🔍", "На проверке"),
    "done":        ("✅", "Готово"),
    "cancelled":   ("❌", "Отменён"),
}

# Состояния диалога заказа
(
    ASK_SERVICE,
    ASK_TRACK_COUNT,
    ASK_GENRE,
    ASK_DRIVE_LINK,
    ASK_COMMENT,
    CONFIRM_ORDER,
) = range(6)

# Состояния диалога отзыва
REVIEW_RATING, REVIEW_TEXT = range(10, 12)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  БАЗА ДАННЫХ
# ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            service     TEXT,
            track_count TEXT,
            genre       TEXT,
            drive_link  TEXT,
            comment     TEXT,
            status      TEXT DEFAULT 'new',
            created_at  TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT,
            order_id   INTEGER,
            rating     INTEGER,
            text       TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_order(user_id, username, service, track_count, genre, drive_link, comment):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (user_id, username, service, track_count, genre, drive_link, comment, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)
    """, (user_id, username, service, track_count, genre, drive_link, comment, datetime.now().strftime("%d.%m.%Y %H:%M")))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_order(order_id):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_orders_by_user(user_id):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_orders(status_filter=None):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    if status_filter:
        c.execute("SELECT * FROM orders WHERE status=? ORDER BY id DESC", (status_filter,))
    else:
        c.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows


def update_order_status(order_id, status):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()


def add_review(user_id, username, order_id, rating, text):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO reviews (user_id, username, order_id, rating, text, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, order_id, rating, text, datetime.now().strftime("%d.%m.%Y %H:%M")))
    conn.commit()
    conn.close()


def get_all_reviews():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("SELECT * FROM reviews ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows


# ─────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────
def format_order(row):
    # row: id, user_id, username, service, track_count, genre, drive_link, comment, status, created_at
    emoji, label = STATUSES.get(row[8], ("❓", row[8]))
    return (
        f"📋 *Заказ №{row[0]}*\n"
        f"👤 @{row[2]}\n"
        f"🎵 Услуга: {row[3]}\n"
        f"🎼 Треков: {row[4]}\n"
        f"🎸 Жанр: {row[5]}\n"
        f"🔗 Ссылка: {row[6]}\n"
        f"💬 Комментарий: _{row[7]}_\n"
        f"📅 Дата: {row[9]}\n"
        f"Статус: {emoji} {label}"
    )


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛 Оставить заявку", callback_data="new_order")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="new_review")],
        [InlineKeyboardButton("💰 Прайс-лист", callback_data="prices")],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton("📞 Связаться напрямую", callback_data="contact")],
    ])


def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")]])


# ─────────────────────────────────────────
#  СТАРТ
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я помогу тебе оформить заказ на *сведение* или *мастеринг*.\n\nВыбери, что тебя интересует:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ─────────────────────────────────────────
#  ГЛАВНОЕ МЕНЮ — статичные разделы
# ─────────────────────────────────────────
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "prices":
        await query.edit_message_text(PRICE_LIST, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎛 Оставить заявку", callback_data="new_order")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")],
            ]))

    elif query.data == "faq":
        await query.edit_message_text(FAQ, parse_mode="Markdown", reply_markup=back_btn())

    elif query.data == "contact":
        await query.edit_message_text(
            "📞 *Связаться напрямую:*\n\nTelegram: @твой\\_ник\nПочта: email@example.com\n\nНапишу в течение нескольких часов 🎵",
            parse_mode="Markdown", reply_markup=back_btn())

    elif query.data == "back_to_menu":
        await query.edit_message_text("Выбери, что тебя интересует:", reply_markup=main_menu_keyboard())

    # Мои заказы
    elif query.data == "my_orders":
        rows = get_orders_by_user(query.from_user.id)
        if not rows:
            await query.edit_message_text("У тебя пока нет заказов.", reply_markup=back_btn())
            return
        text = "📦 *Твои заказы:*\n\n"
        for row in rows:
            emoji, label = STATUSES.get(row[8], ("❓", row[8]))
            text += f"№{row[0]} — {row[3]} ({row[4]}) — {emoji} {label}\n"
        buttons = [[InlineKeyboardButton(f"Подробнее №{r[0]}", callback_data=f"order_detail_{r[0]}")] for r in rows]
        buttons.append([InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("order_detail_"):
        order_id = int(query.data.split("_")[-1])
        row = get_order(order_id)
        if not row:
            await query.edit_message_text("Заказ не найден.", reply_markup=back_btn())
            return
        await query.edit_message_text(format_order(row), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="my_orders")],
            ]))


# ─────────────────────────────────────────
#  ДИАЛОГ: ОФОРМЛЕНИЕ ЗАКАЗА
# ─────────────────────────────────────────
async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "🎛 *Оформление заявки*\n\nШаг 1/5 — Какая услуга тебя интересует?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎚 Сведение", callback_data="svc_mixing")],
            [InlineKeyboardButton("💿 Мастеринг", callback_data="svc_mastering")],
            [InlineKeyboardButton("🎚💿 Сведение + Мастеринг", callback_data="svc_both")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")],
        ]),
    )
    return ASK_SERVICE


async def ask_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["service"] = {"svc_mixing": "Сведение", "svc_mastering": "Мастеринг", "svc_both": "Сведение + Мастеринг"}[query.data]
    await query.edit_message_text("Шаг 2/5 — Сколько треков нужно обработать?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1 трек", callback_data="cnt_1"), InlineKeyboardButton("2–5 треков", callback_data="cnt_2-5")],
            [InlineKeyboardButton("6–10 треков", callback_data="cnt_6-10"), InlineKeyboardButton("10+ треков", callback_data="cnt_10+")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")],
        ]))
    return ASK_TRACK_COUNT


async def ask_track_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["track_count"] = query.data.replace("cnt_", "")
    await query.edit_message_text("Шаг 3/5 — Напиши жанр или стиль музыки.\n\n_Например: хип-хоп, поп, рок, электронная и т.д._", parse_mode="Markdown")
    return ASK_GENRE


async def ask_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["genre"] = update.message.text
    await update.message.reply_text("Шаг 4/5 — Отправь ссылку на Google Drive или Яндекс Диск с файлами.\n\n_Убедись, что доступ по ссылке открыт для всех._", parse_mode="Markdown")
    return ASK_DRIVE_LINK


async def ask_drive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    if not link.startswith("http"):
        await update.message.reply_text("⚠️ Пожалуйста, отправь корректную ссылку (начинается с http...).")
        return ASK_DRIVE_LINK
    context.user_data["drive_link"] = link
    await update.message.reply_text("Шаг 5/5 — Есть ли дополнительные пожелания?\n\n_Если нет — отправь прочерк._", parse_mode="Markdown")
    return ASK_COMMENT


async def ask_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text
    d = context.user_data
    summary = (
        f"📋 *Проверь свою заявку:*\n\n"
        f"🎵 Услуга: *{d['service']}*\n"
        f"🎼 Треков: *{d['track_count']}*\n"
        f"🎸 Жанр: *{d['genre']}*\n"
        f"🔗 Ссылка: {d['drive_link']}\n"
        f"💬 Комментарий: _{d['comment']}_\n\nВсё верно?"
    )
    await update.message.reply_text(summary, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Отправить заявку", callback_data="confirm_order")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_order")],
        ]))
    return CONFIRM_ORDER


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    user = query.from_user
    order_id = add_order(user.id, user.username or user.first_name, d["service"], d["track_count"], d["genre"], d["drive_link"], d["comment"])

    await query.edit_message_text(
        f"✅ *Заявка №{order_id} принята!*\n\nСвяжусь с тобой в ближайшее время для уточнения деталей.\nСпасибо! 🎵",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_menu")]]),
    )

    # Уведомление админу
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 *Новый заказ №{order_id}!*\n\n"
            f"👤 @{user.username or user.first_name}\n"
            f"🎵 {d['service']} | {d['track_count']} треков\n"
            f"🎸 Жанр: {d['genre']}\n"
            f"🔗 {d['drive_link']}\n"
            f"💬 {d['comment']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Открыть админ-панель", callback_data=f"admin_order_{order_id}")],
            ])
        )
    except Exception:
        pass

    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Заявка отменена.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_menu")]]))
    return ConversationHandler.END


# ─────────────────────────────────────────
#  ДИАЛОГ: ОТЗЫВ
# ─────────────────────────────────────────
async def new_review_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows = get_orders_by_user(query.from_user.id)
    done_orders = [r for r in rows if r[8] == "done"]
    if not done_orders:
        await query.edit_message_text(
            "⭐ Отзыв можно оставить только после завершения заказа.\nПока у тебя нет завершённых заказов.",
            reply_markup=back_btn())
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(f"Заказ №{r[0]} — {r[3]}", callback_data=f"review_order_{r[0]}")] for r in done_orders]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_review")])
    await query.edit_message_text("⭐ *Оставить отзыв*\n\nВыбери заказ:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return REVIEW_RATING


async def review_select_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["review_order_id"] = int(query.data.split("_")[-1])
    await query.edit_message_text("Оцени работу от 1 до 5 ⭐",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(str(i) + "⭐", callback_data=f"rating_{i}") for i in range(1, 6)
        ]]))
    return REVIEW_TEXT


async def review_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["review_rating"] = int(query.data.split("_")[1])
    await query.edit_message_text("Напиши свой отзыв текстом:")
    return REVIEW_TEXT


async def review_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    d = context.user_data
    add_review(user.id, user.username or user.first_name, d.get("review_order_id", 0), d["review_rating"], update.message.text)
    await update.message.reply_text(
        f"{'⭐' * d['review_rating']} Спасибо за отзыв! Это очень важно для меня 🙏",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_menu")]]))
    return ConversationHandler.END


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Отменено.", reply_markup=back_btn())
    return ConversationHandler.END


# ─────────────────────────────────────────
#  АДМИН-ПАНЕЛЬ
# ─────────────────────────────────────────
def is_admin(user_id):
    return user_id == ADMIN_ID


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await update.message.reply_text(
        "📊 *Админ-панель*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🆕 Новые", callback_data="admin_filter_new"),
             InlineKeyboardButton("⚙️ В работе", callback_data="admin_filter_in_progress")],
            [InlineKeyboardButton("🔍 На проверке", callback_data="admin_filter_review"),
             InlineKeyboardButton("✅ Готовые", callback_data="admin_filter_done")],
            [InlineKeyboardButton("📋 Все заказы", callback_data="admin_filter_all")],
            [InlineKeyboardButton("⭐ Отзывы", callback_data="admin_reviews")],
        ]),
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа.")
        return
    await query.answer()
    data = query.data

    # Фильтр заказов
    if data.startswith("admin_filter_"):
        status = data.replace("admin_filter_", "")
        rows = get_all_orders(None if status == "all" else status)
        if not rows:
            await query.edit_message_text("Заказов не найдено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        buttons = [[InlineKeyboardButton(
            f"№{r[0]} | {r[3]} | {STATUSES.get(r[8], ('❓',''))[0]} {r[2]}",
            callback_data=f"admin_order_{r[0]}")] for r in rows]
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
        await query.edit_message_text(f"📋 Заказов найдено: {len(rows)}", reply_markup=InlineKeyboardMarkup(buttons))

    # Детали заказа
    elif data.startswith("admin_order_"):
        order_id = int(data.split("_")[-1])
        row = get_order(order_id)
        if not row:
            await query.edit_message_text("Заказ не найден.")
            return
        status_buttons = [
            InlineKeyboardButton(f"{e} {l}", callback_data=f"setstatus_{order_id}_{k}")
            for k, (e, l) in STATUSES.items() if k != row[8]
        ]
        keyboard = [status_buttons[i:i+2] for i in range(0, len(status_buttons), 2)]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_filter_all")])
        await query.edit_message_text(format_order(row), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Смена статуса
    elif data.startswith("setstatus_"):
        _, order_id, new_status = data.split("_", 2)
        order_id = int(order_id)
        update_order_status(order_id, new_status)
        row = get_order(order_id)

        # Уведомить клиента
        emoji, label = STATUSES.get(new_status, ("❓", new_status))
        try:
            await context.bot.send_message(
                row[1],
                f"🔔 *Обновление по заказу №{order_id}*\n\nНовый статус: {emoji} *{label}*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")]]),
            )
        except Exception:
            pass

        # Обновить сообщение
        status_buttons = [
            InlineKeyboardButton(f"{e} {l}", callback_data=f"setstatus_{order_id}_{k}")
            for k, (e, l) in STATUSES.items() if k != new_status
        ]
        keyboard = [status_buttons[i:i+2] for i in range(0, len(status_buttons), 2)]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_filter_all")])
        await query.edit_message_text(format_order(get_order(order_id)), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Отзывы
    elif data == "admin_reviews":
        rows = get_all_reviews()
        if not rows:
            await query.edit_message_text("Отзывов пока нет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        text = "⭐ *Отзывы клиентов:*\n\n"
        for r in rows:
            text += f"{'⭐' * r[4]} @{r[2]} (заказ №{r[3]})\n_{r[5]}_\n📅 {r[6]}\n\n"
        await query.edit_message_text(text[:4000], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    elif data == "admin_back":
        await query.edit_message_text("📊 *Админ-панель*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🆕 Новые", callback_data="admin_filter_new"),
                 InlineKeyboardButton("⚙️ В работе", callback_data="admin_filter_in_progress")],
                [InlineKeyboardButton("🔍 На проверке", callback_data="admin_filter_review"),
                 InlineKeyboardButton("✅ Готовые", callback_data="admin_filter_done")],
                [InlineKeyboardButton("📋 Все заказы", callback_data="admin_filter_all")],
                [InlineKeyboardButton("⭐ Отзывы", callback_data="admin_reviews")],
            ]))


# ─────────────────────────────────────────
#  ЗАПУСК
# ─────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Диалог заказа
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_order_start, pattern="^new_order$")],
        states={
            ASK_SERVICE:     [CallbackQueryHandler(ask_service, pattern="^svc_")],
            ASK_TRACK_COUNT: [CallbackQueryHandler(ask_track_count, pattern="^cnt_")],
            ASK_GENRE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_genre)],
            ASK_DRIVE_LINK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_drive_link)],
            ASK_COMMENT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_comment)],
            CONFIRM_ORDER:   [CallbackQueryHandler(confirm_order, pattern="^confirm_order$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_order, pattern="^cancel_order$")],
    )

    # Диалог отзыва
    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_review_start, pattern="^new_review$")],
        states={
            REVIEW_RATING: [CallbackQueryHandler(review_select_order, pattern="^review_order_"),
                            CallbackQueryHandler(review_rating, pattern="^rating_")],
            REVIEW_TEXT:   [CallbackQueryHandler(review_rating, pattern="^rating_"),
                            MessageHandler(filters.TEXT & ~filters.COMMAND, review_text)],
        },
        fallbacks=[CallbackQueryHandler(cancel_review, pattern="^cancel_review$")],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(order_conv)
    app.add_handler(review_conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|setstatus_)"))
    app.add_handler(CallbackQueryHandler(menu_callback))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
