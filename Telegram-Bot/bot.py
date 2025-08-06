from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import os
import matplotlib.pyplot as plt

TOKEN = "8300199486:AAEFQYSnY2V9pi_sm8ePN-omYcYb-pDu0rE"

def init_db():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            amount INTEGER,
            comment TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# /start

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ Добавить трату")],
        [KeyboardButton("📄 Последние"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📈 График"), KeyboardButton("📤 Экспорт")],
        [KeyboardButton("❌ Удалить трату")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Я бот для учёта расходов 💸\n\n"
        "Просто напиши в формате:\n"
        "`еда 25000 шаверма`\n"
        "И я всё запомню! 📒",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Добавить трату":
        await update.message.reply_text("Введите в формате: категория сумма комментарий\n\nПример: еда 12000 шаверма")
    elif text == "📄 Последние":
        await show_last(update, context)
    elif text == "📊 Статистика":
        await show_stats(update, context)
    elif text == "📈 График":
        await show_chart(update, context)
    elif text == "📤 Экспорт":
        await export_to_excel(update, context)
    elif text == "❌ Удалить трату":
        await update.message.reply_text("Напиши команду: /delete ID\nНапример: /delete 17")
    else:
        await add_expense(update, context)

def format_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    parts = text.strip().split()

    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text("Пожалуйста, используй формат: категория сумма [комментарий]")
        return

    category = parts[0]
    amount = int(parts[1])
    comment = ' '.join(parts[2:]) if len(parts) > 2 else ''
    user_id = update.message.from_user.id
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (user_id, category, amount, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, category, amount, comment, timestamp),
    )
    conn.commit()
    conn.close()

    formatted_amount = format_amount(amount)
    await update.message.reply_text(
        f"Добавлена трата: {category} — {formatted_amount} сум. Комментарий: {comment}"
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND timestamp >= ?", (user_id, today_start))
    today_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND timestamp >= ?", (user_id, week_start))
    week_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND timestamp >= ?", (user_id, month_start))
    month_total = cursor.fetchone()[0] or 0

    conn.close()

    await update.message.reply_text(
        f"📊 *Статистика трат:*\n"
        f"Сегодня: `{format_amount(today_total)}` сум\n"
        f"За 7 дней: `{format_amount(week_total)}` сум\n"
        f"За месяц: `{format_amount(month_total)}` сум",
        parse_mode="Markdown"
    )

async def export_to_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect("expenses.db")

    df = pd.read_sql_query(
        "SELECT category, amount, comment, timestamp FROM expenses WHERE user_id = ? ORDER BY timestamp DESC",
        conn, params=(user_id,)
    )
    conn.close()

    if df.empty:
        await update.message.reply_text("Нет данных для экспорта.")
        return

    filename = f"expenses_{user_id}.xlsx"
    df.to_excel(filename, index=False)

    with open(filename, "rb") as file:
        await update.message.reply_document(file)

    os.remove(filename)

async def show_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect("expenses.db")
    df = pd.read_sql_query(
        "SELECT category, amount FROM expenses WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()

    if df.empty:
        await update.message.reply_text("Нет данных для построения графика.")
        return

    category_sum = df.groupby("category")["amount"].sum()

    plt.figure(figsize=(6, 6))
    plt.pie(category_sum, labels=category_sum.index, autopct="%1.1f%%")
    plt.title("Расходы по категориям")
    filename = f"chart_{user_id}.png"
    plt.savefig(filename)
    plt.close()

    with open(filename, "rb") as photo:
        await update.message.reply_photo(photo)

    os.remove(filename)

async def show_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, category, amount, comment, timestamp FROM expenses WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Нет сохранённых трат.")
        return

    msg = "🧾 *Последние траты:*\n"
    for row in rows:
        id, category, amount, comment, timestamp = row
        msg += f"`#{id}` • {category} — {format_amount(amount)} сум • {comment} ({timestamp})\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text("Пожалуйста, укажи ID траты: /delete 123")
        return

    expense_id = int(args[0])
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    row = cursor.fetchone()

    if row is None:
        await update.message.reply_text(f"Запись с ID {expense_id} не найдена.")
    else:
        cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ Запись #{expense_id} успешно удалена.")

    conn.close()

async def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("export", export_to_excel))
    app.add_handler(CommandHandler("chart", show_chart))
    app.add_handler(CommandHandler("last", show_last))
    app.add_handler(CommandHandler("delete", delete_expense))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    import nest_asyncio

    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
