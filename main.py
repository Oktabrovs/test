import logging
import re
from os import environ
from urllib.request import urlopen

import pymongo
import requests
from telegram import Update, File
from telegram.ext import Application, PicklePersistence, ContextTypes, CommandHandler, MessageHandler, filters, \
    ConversationHandler

'''Constants'''

# TODO add error handler
# TODO chat member handler
# TODO add yechim to bot settings

logging.basicConfig(
    # filename='syccbot.log', TODO uncomment
    # format="[%(asctime)s %(levelname)s] %(message)s",
    format="[%(levelname)s] %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

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
    logger.info('/start from {}'.format(update.effective_chat.id))
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

    await update.message.reply_text(
        "Kodni tekshiruvchi botga xush kelibsiz!\n\n"
        "Bugungi masalani tasvirlash uchun /bugungi_masala buyrug'ini yuboring.\n"
        "Botdan foydalanishda yordam so'rash uchun /yordam buyrug'ini yuboring.\n\n"
        "Kodingizni matn yoki .py fayl sifatida yuborishingiz mumkin.")


async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_code_string: str = ''
    if not context.bot_data.get('tests'):
        return
    challenge_test_string: str = context.bot_data.get('tests')

    if update.message.text:
        user_code_string = update.message.text
    elif update.message.document:
        file_link: File = await context.bot.get_file(update.message.document.file_id)
        file = urlopen(file_link.file_path)
        for line in file:
            user_code_string += line.decode('utf-8')

    logger.info('received code\n{}\nfrom {}'.format(user_code_string, update.effective_chat.id))

    data = {
        'files': [
            {'name': 'tests.py', 'content': challenge_test_string},
            {'name': 'user_code.py', 'content': user_code_string}
        ]
    }

    req = requests.post(url=GLOT_URL, json=data, headers=headers)
    req_json = req.json()
    test_output = req_json.get('stderr')

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
    logger.info('/yangi_masala from user: {}'.format(update.message.chat_id))
    if str(update.message.chat_id) == DEVELOPER_CHAT_ID:
        await update.message.reply_text('Hello, Developer!\n\nSend description of new challenge')
        return CHALLENGE_DESCRIPTION
    else:
        return ConversationHandler.END


async def challenge_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    challenge_description: str = update.message.text
    logger.info('challenge_description\n{}'.format(challenge_description))
    context.user_data['current_challenge_description'] = challenge_description
    await update.message.reply_text('Send solution picture')
    return CHALLENGE_SOLUTION


async def challenge_solution_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    solution_photo_id: str = update.message.photo[0].file_id
    logger.info('solution_photo_id\n{}'.format(solution_photo_id))
    context.user_data['current_challenge_solution_photo_id'] = solution_photo_id
    await update.message.reply_text('Send test file')
    return CHALLENGE_TEST


async def challenge_tests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    challenge_test_string: str = ''
    test_file_link = await context.bot.get_file(update.message.document.file_id)
    test_file = urlopen(test_file_link.file_path)
    for line in test_file:
        challenge_test_string += line.decode('utf-8')

    logger.info('challenge_test_string\n{}'.format(challenge_test_string))

    challenge_dict = {
        'description': context.user_data['current_challenge_description'],
        'solution_photo_id': context.user_data['current_challenge_solution_photo_id'],
        'tests': challenge_test_string
    }

    challenge_id = challenges_col.insert_one(challenge_dict)
    challenge_dict['challenge_id'] = challenge_id.inserted_id

    context.bot_data.update(challenge_dict)

    logger.info('added new challenge')

    await update.message.reply_text('New challenge added')
    return ConversationHandler.END


async def challenge_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('/bugungi_masala from {}'.format(update.effective_chat.id))

    await update.message.reply_text(context.bot_data.get('description'))


async def help_handler(update: Update, _) -> None:
    logger.info('/yordam from {}'.format(update.effective_chat.id))
    text: str = "Kodingizni matn yoki .py fayl sifatida yuborishingiz mumkin.\n\n" \
                "Bugungi masalani tasvirlash uchun /bugungi_masala buyrug'ini yuboring.\n" \
                "Peshqadamlar ro'yxatini ko'rsatish uchun /top buyrug'ini yuboring.\n" \
                "Bugungi masala bo'yicha peshqadamlar ro'yxatini ko'rsatish uchun /bugungi_top buyrug'ini yuboring.\n"

    await update.message.reply_text(text)


async def solution_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('/yechim from {}'.format(update.effective_chat.id))
    if str(update.message.chat_id) == DEVELOPER_CHAT_ID:
        await update.message.reply_photo(context.bot_data.get('solution_photo_id'))
    else:
        await update.message.reply_text("Ushbu masalaning yechimi @yangibaevs telegram kanalida ko'rsatiladi")


async def leaderboard_handler(update: Update, _) -> None:
    logger.info('/top from {}'.format(update.effective_chat.id))
    users = users_col.find({'points': {'$gt': 0}}).sort('points', pymongo.DESCENDING)

    text: str = ''
    for i, user in enumerate(users[:10], 1):
        username = f"@{user.get('username')}" if user.get('username') else user.get('full_name')
        text += '{}. {} - {} ball\n'.format(i, username, user.get('points'))
    await update.message.reply_text(text)


async def todays_leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('/bugungi_top from {}'.format(update.effective_chat.id))
    text: str = 'Tezlik:\n'
    solvers = solvers_col.find({'challenge_id': context.bot_data.get('challenge_id')}).sort('result')
    for i, solver in enumerate(solvers[:10], 1):
        text += '{}. {} - {}s\n'.format(i, solver.get('user'), solver.get('result'))

    text += '\n---\n\nQisqalik:\n'
    solvers = solvers_col.find({'challenge_id': context.bot_data.get('challenge_id')}).sort('code_length')
    for i, solver in enumerate(solvers[:10], 1):
        text += '{}. {} - {} belgi\n'.format(i, solver.get('user'), solver.get('code_length'))

    await update.message.reply_text(text)


'''Main'''


def main() -> None:
    persistence = PicklePersistence(filepath='persistence.pickle')

    app = Application.builder().token(environ['TOKEN']).persistence(persistence).build()

    app.add_handler(CommandHandler('start', start_handler))

    app.add_handler(CommandHandler('bugungi_masala', challenge_info_handler))

    app.add_handler(CommandHandler('yechim', solution_handler))

    app.add_handler(CommandHandler('yordam', help_handler))

    app.add_handler(CommandHandler('top', leaderboard_handler))

    app.add_handler(CommandHandler('bugungi_top', todays_leaderboard_handler))

    new_challenge_conversation = ConversationHandler(
        entry_points=[CommandHandler('yangi_masala', new_challenge_handler)],
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
