import re
from os import environ
from urllib.request import urlopen

import pymongo
import requests
from telegram import Update, File
from telegram.ext import Application, PicklePersistence, ContextTypes, CommandHandler, MessageHandler, filters, \
    ConversationHandler

'''Constants'''
myclient = pymongo.MongoClient('mongodb://localhost:27017/')
mydb = myclient['code_checker']
users_col = mydb['users']
challenges_col = mydb['challenges']
solvers_col = mydb['solvers']

DEVELOPER_CHAT_ID = environ['DEVELOPER_CHAT_ID']
GLOT_URL = environ['GLOT_URL']
DIVIDER = '----------------------------------------------------------------------'

headers = {
    'Authorization': environ['GLOT_AUTHORIZATION'],
    'Content-type': 'application/json'
}

CHALLENGE_DESCRIPTION = 11
CHALLENGE_SOLUTION = 12
CHALLENGE_TEST = 13

'''Handlers'''


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_found = users_col.find_one({"chat_id": update.effective_chat.id})
    if not user_found:
        user_dict = {
            'chat_id': update.effective_chat.id,
            'username': update.effective_user.username,
            'full_name': update.effective_user.full_name,
            'solved_challenges': [],
            'points': 0
        }
        users_col.insert_one(user_dict)

        if update.effective_user.username:
            context.chat_data['username'] = f'@{update.effective_user.username}'
        else:
            context.chat_data['username'] = update.effective_user.full_name

    await update.message.reply_text('Welcome to the code checker bot!')


async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print('code_handler', update)
    user_code_string: str = ''
    challenge_test_string: str = context.bot_data['tests']

    if update.message.text:
        user_code_string = update.message.text
    elif update.message.document:
        file_link: File = await context.bot.get_file(update.message.document.file_id)
        file = urlopen(file_link.file_path)
        for line in file:
            user_code_string += line.decode('utf-8')

    data = {
        'files': [
            {'name': 'tests.py', 'content': challenge_test_string},
            {'name': 'user_code.py', 'content': user_code_string}
        ]
    }

    req = requests.post(url=GLOT_URL, json=data, headers=headers)
    req_json = req.json()
    test_output = req_json['stderr']

    if DIVIDER in test_output:
        text: str = test_output[test_output.find(DIVIDER):]
        text = text.replace(DIVIDER, '---')
    else:
        text: str = test_output

    if text.endswith('OK\n'):
        username: str = context.chat_data['username']
        result: float = float(re.search(r"\d+\.\d+", text).group())
        solver_dict: dict = {
            'user': username,
            'result': result,
            'solution': user_code_string,
            'code_length': len(user_code_string)
        }

        solver_found = solvers_col.find_one({'challenge_id': context.bot_data['challenge_id'], 'user': username})
        if not solver_found:
            user = users_col.find_one({'chat_id': update.effective_chat.id})
            user['solved_challenges'].append(context.bot_data['challenge_id'])
            user['points'] += 1
            users_col.update_one({'_id': user['_id']},
                                 {'$set': user})

        solvers_col.update_one({'challenge_id': context.bot_data['challenge_id'], 'user': username},
                               {'$set': solver_dict},
                               upsert=True)
        await update.message.reply_text('✅')

    text = re.sub(r"<([^>]+)>", r'\1', text)

    await update.message.reply_html(text=f'<code>{text}</code>')


async def new_challenge_handler(update: Update, _) -> int:
    if str(update.message.chat_id) == DEVELOPER_CHAT_ID:
        await update.message.reply_text('Hello, Developer!\n\nSend description of new challenge')
        return CHALLENGE_DESCRIPTION
    else:
        return ConversationHandler.END


async def challenge_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    challenge_description: str = update.message.text
    context.user_data['current_challenge_description'] = challenge_description
    await update.message.reply_text('Send solution picture')
    return CHALLENGE_SOLUTION


async def challenge_solution_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    solution_photo_id: str = update.message.photo[0].file_id
    context.user_data['current_challenge_solution_photo_id'] = solution_photo_id
    await update.message.reply_text('Send test file')
    return CHALLENGE_TEST


async def challenge_tests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    challenge_test_string: str = ''
    test_file_link = await context.bot.get_file(update.message.document.file_id)
    test_file = urlopen(test_file_link.file_path)
    for line in test_file:
        challenge_test_string += line.decode('utf-8')

    challenge_dict = {
        'description': context.user_data['current_challenge_description'],
        'solution_photo_id': context.user_data['current_challenge_solution_photo_id'],
        'tests': challenge_test_string
    }

    challenge_id = challenges_col.insert_one(challenge_dict)
    challenge_dict['challenge_id'] = challenge_id.inserted_id

    context.bot_data.update(challenge_dict)

    await update.message.reply_text('New challenge added')
    return ConversationHandler.END


'''Main'''


def main() -> None:
    persistence = PicklePersistence(filepath='persistence.pickle')

    app = Application.builder().token(environ['TOKEN']).persistence(persistence).build()

    app.add_handler(CommandHandler('start', start_handler))

    new_challenge_conversation = ConversationHandler(
        entry_points=[CommandHandler('new_challenge', new_challenge_handler)],
        states={
            CHALLENGE_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_description_handler)
            ],
            CHALLENGE_SOLUTION: [
                MessageHandler(filters.PHOTO, challenge_solution_handler)
            ],
            CHALLENGE_TEST: [
                MessageHandler(filters.Document.PY, challenge_tests_handler)
            ]
        },
        allow_reentry=True,
        fallbacks=[],
        persistent=True,
        name='new_challenge_conversation'
    )

    app.add_handler(new_challenge_conversation)

    app.add_handler(MessageHandler((filters.TEXT | filters.Document.PY) & ~filters.COMMAND, code_handler))

    app.run_polling()


if __name__ == '__main__':
    main()
