import logging
import os

import django
from django.utils import timezone
from dotenv import load_dotenv
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardRemove, Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          MessageHandler, Updater)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'python_meetup_bot.settings')
django.setup()

from telegram_meetup.models import Question, Report, User

ASKING_QUESTION = 1


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Расписание выступлений", callback_data='schedule')],
        [InlineKeyboardButton("Хочу познакомиться", callback_data='meetup')],
        [InlineKeyboardButton("Вопросы к докладчику", callback_data='speaker_questions')],
        [InlineKeyboardButton("Донат организатору", callback_data='donate')],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        update.message.reply_text('Главное меню:', reply_markup=reply_markup)
    else:
        update.callback_query.message.edit_text('Главное меню:', reply_markup=reply_markup)
    logger.info(update.message.from_user.username)


def get_speakers_schedule():
    schedule = []
    reports = Report.objects.filter(datetime__gte=timezone.now()).order_by('datetime')

    for report in reports:
        schedule.append({
            "id": report.id,
            "speaker": f"{report.speaker.firstname} {report.speaker.lastname}",
            "topic": report.title,
            "time": report.datetime.strftime("%H:%M"),
        })

    return schedule


def schedule(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    schedule = get_speakers_schedule()

    if schedule:
        text = 'Выберите доклад:'
        keyboard = [
            [InlineKeyboardButton(f"{s['time']}: {s['speaker']} - {s['topic']}", callback_data=f"report_{s['id']}")]
            for s in schedule
        ]
        keyboard.append([InlineKeyboardButton("Назад", callback_data='start')])
    else:
        text = "В ближайшее время выступлений не запланировано"
        keyboard = [[InlineKeyboardButton("Назад", callback_data='start')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    query.message.edit_text(text, reply_markup=reply_markup)


def report(update: Update, context: CallbackContext, report_id: int) -> None:
    query = update.callback_query
    report = Report.objects.get(id=report_id)

    text = f"Докладчик: {report.speaker.firstname} {report.speaker.lastname}\n" \
           f"Тема: {report.title}\n" \
           f"Время: {report.datetime.strftime('%H:%M')}\n" \
           f"Описание: {report.description}"

    keyboard = [
        [InlineKeyboardButton("Задать вопрос", callback_data=f"ask_{report_id}")],
        [InlineKeyboardButton("Назад", callback_data='schedule')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.message.edit_text(text, reply_markup=reply_markup)


def ask_question(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    report_id = int(query.data.split('_')[1])
    context.user_data['report_id'] = report_id
    query.message.reply_text('Пожалуйста, введите ваш вопрос:')
    return ASKING_QUESTION


def receive_question(update: Update, context: CallbackContext) -> None:
    report_id = context.user_data['report_id']
    report = Report.objects.get(id=report_id)

    user, created = User.objects.get_or_create(
        username=update.message.from_user.username
    )

    question = Question(user=user, question=update.message.text, report=report)
    question.save()

    update.message.reply_text(
        'Спасибо за ваш вопрос! Мы обязательно передадим его докладчику.'
    )
    return ConversationHandler.END


def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    query.answer()

    if query.data == 'schedule':
        schedule(update, context)
    elif query.data.startswith('report_'):
        report_id = int(query.data.split('_')[1])
        report(update, context, report_id)
    elif query.data.startswith('ask_'):
        report_id = int(query.data.split('_')[1])
        ask_question(update, context, report_id)
    elif query.data == 'meetup':
        # тут код встречи
        pass
    elif query.data == 'speaker_questions':
        # тут код вопросов к докладчику
        pass
    elif query.data == 'donate':
        # тут код для доната
        pass
    elif query.data == 'start':
        start(update, context)


def cancel(update: Update, context: CallbackContext) -> int:
    start(update, context)
    return ConversationHandler.END


conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_question, pattern='^ask_[0-9]+$')],
    states={
        ASKING_QUESTION: [
            MessageHandler(Filters.text & ~Filters.command, receive_question)
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)


def main() -> None:
    load_dotenv()
    tg_token = os.getenv("TG_TOKEN")
    updater = Updater(tg_token, use_context=True)
    logger.info("Starting the bot...")
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(conv_handler)
    updater.dispatcher.add_handler(CallbackQueryHandler(button))

    updater.start_polling()

    updater.idle()

    logger.info("Bot has been stopped")


if __name__ == '__main__':
    main()
