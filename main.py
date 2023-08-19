import html
import json
import logging
import re
import traceback
from os import environ
from typing import Optional, Tuple
from urllib.request import urlopen

import pymongo
import requests
from telegram import Update, File, ChatMemberUpdated, ChatMember, Chat
from telegram.constants import ParseMode
from telegram.ext import Application, PicklePersistence, ContextTypes, CommandHandler, MessageHandler, filters, \
    ConversationHandler, ChatMemberHandler

# todo check for errors
'''Constants'''

logging.basicConfig(
    filename='syccbot.log',
    format="[%(asctime)s %(levelname)s] %(message)s",
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

'''Helpers'''


def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
    the status didn't change.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member",
                                                                       (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


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
    if text.endswith('OK\n') and DEVELOPER_CHAT_ID != str(update.effective_chat.id):
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
    challenge_description: str = update.message.text_html
    logger.info('challenge_description\n{}'.format(challenge_description))
    context.user_data['current_challenge_description'] = challenge_description
    await update.message.reply_text('Send solution picture or text')
    return CHALLENGE_SOLUTION


async def challenge_solution_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    if update.message.photo:
        solution_photo_id: str = update.message.photo[0].file_id
        logger.info('solution_photo_id\n{}'.format(solution_photo_id))
        context.user_data['current_challenge_solution_photo_id'] = solution_photo_id
        context.user_data['current_challenge_solution_text'] = ''
    else:
        solution_text: str = update.message.text_html
        logger.info('solution_text\n{}'.format(solution_text))
        context.user_data['current_challenge_solution_text'] = solution_text
        context.user_data['current_challenge_solution_photo_id'] = ''
    await update.message.reply_text('Send test file')
    return CHALLENGE_TEST


async def challenge_tests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    challenge_test_string: str = ''

    if update.message.text:
        challenge_test_string = update.message.text_markdown_v2.replace('`', '')
    else:
        test_file_link = await context.bot.get_file(update.message.document.file_id)
        test_file = urlopen(test_file_link.file_path)
        for line in test_file:
            challenge_test_string += line.decode('utf-8')

    logger.info('challenge_test_string\n{}'.format(challenge_test_string))

    challenge_dict = {
        'description': context.user_data['current_challenge_description'],
        'solution_photo_id': context.user_data['current_challenge_solution_photo_id'],
        'solution_text': context.user_data['current_challenge_solution_text'],
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
    task_description = context.bot_data.get('description')
    if task_description:
        await update.message.reply_html(task_description)
    else:
        await update.message.reply_text('masala topilmadi')


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
        solution_photo_id = context.bot_data.get('solution_photo_id')
        solution_text = context.bot_data.get('solution_text')
        logger.info(solution_photo_id)
        if solution_photo_id:
            await update.message.reply_photo(solution_photo_id)
        elif solution_text:
            await update.message.reply_html(solution_text)
        else:
            await update.message.reply_text('no solution photo found')
    else:
        await update.message.reply_text("Ushbu masalaning yechimi @yangibaevs telegram kanalida ko'rsatiladi")


async def leaderboard_handler(update: Update, _) -> None:
    logger.info('/top from {}'.format(update.effective_chat.id))
    users = list(users_col.find({'points': {'$gt': 0}}).sort('points', pymongo.DESCENDING))

    text: str = ''

    if len(users):
        for i, user in enumerate(users[:10], 1):
            username = f"@{user.get('username')}" if user.get('username') else user.get('full_name')
            text += '{}. {} - {} ball\n'.format(i, username, user.get('points'))
    else:
        text = 'hali aniqlanmagan'
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )


async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks the chats the bot is in."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Let's check who is responsible for the change
    cause_name = update.effective_user.full_name

    # Handle chat types differently:
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            # This may not be really needed in practice because most clients will automatically
            # send a /start command after the user unblocks the bot, and start_private_chat()
            # will add the user to "user_ids".
            # We're including this here for the sake of the example.
            logger.info("%s unblocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s",
                        cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s",
                        cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
    elif not was_member and is_member:
        logger.info("%s added the bot to the channel %s",
                    cause_name, chat.title)
        context.bot_data.setdefault("channel_ids", set()).add(chat.id)
    elif was_member and not is_member:
        logger.info("%s removed the bot from the channel %s",
                    cause_name, chat.title)
        context.bot_data.setdefault("channel_ids", set()).discard(chat.id)


async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)

    if chat_id == DEVELOPER_CHAT_ID:
        """Shows which chats the bot is in"""
        user_ids = ", ".join(str(uid)
                             for uid in context.bot_data.setdefault("user_ids", set()))
        group_ids = ", ".join(str(gid)
                              for gid in context.bot_data.setdefault("group_ids", set()))
        channel_ids = ", ".join(
            str(cid) for cid in context.bot_data.setdefault("channel_ids", set()))
        text = (
            f"@{context.bot.username} is currently in a conversation with the user IDs {user_ids}."
            f" Moreover it is a member of the groups with IDs {group_ids} "
            f"and administrator in the channels with IDs {channel_ids}."
        )
        await update.effective_message.reply_text(text)

    else:
        await update.effective_message.reply_text('Sorry, I do not know this command')


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
                MessageHandler(filters.PHOTO, challenge_solution_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_solution_handler)
            ],
            CHALLENGE_TEST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_tests_handler),
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
    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CommandHandler('show_chats', show_chats))
    app.add_error_handler(error_handler)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
