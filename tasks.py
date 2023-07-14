from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from constants import tasks_col, TASKS, TASK_SELECTED


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    tasks_list = tasks_col.find().limit(10)

    buttons = []
    for task in tasks_list:
        buttons.append(['{}. {}'.format(task['_id'], task['title'])])

    keyboard = ReplyKeyboardMarkup(buttons)

    await update.message.reply_text(text="choose task", reply_markup=keyboard)

    return TASKS


async def task_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    msg_text = update.message.text
    task_id = msg_text[:msg_text.index('.')]

    context.chat_data['task_id'] = task_id

    task = tasks_col.find_one({'_id': int(task_id)})

    text = 'task #{}\n{}\n{}\n\nPaste python code or send .py file'.format(
        task['_id'], task['title'], task['description'])

    buttons = [['Back']]
    keyboard = ReplyKeyboardMarkup(buttons)

    await update.message.reply_text(text=text, reply_markup=keyboard)

    return TASK_SELECTED
