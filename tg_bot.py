from ast import literal_eval as make_tuple
import os
import logging
import redis

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, PreCheckoutQueryHandler

from moltin import get_products, get_product, get_product_image_url, add_cart_item, get_cart, remove_cart_item

from pizza import get_address_coordinates, get_nearest_pizzeria, get_pizzeria, add_customer_location, \
    get_cart_items_text, add_delivery_to_cart, get_customer_location, DELIVERY_ITEM_NAME

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_PAYMENT_TOKEN = os.getenv('TELEGRAM_PAYMENT_TOKEN')
TELEGRAM_PAYMENT_PARAMETER = os.getenv('TELEGRAM_PAYMENT_PARAMETER')
TELEGRAM_PROXY = os.getenv('TG_PROXY')

REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = os.getenv('REDIS_PORT')
REDIS_PASWORD = os.getenv('REDIS_PASWORD')

REQUEST_KWARGS = {
    'proxy_url': TELEGRAM_PROXY,
}

PRODUCT_SLICE_OFFSET = 8

DELIVERY_OPTIONS = {
    0.5: 0,
    5: 100,
    20: 300,
}

MESAGE_AFTER_DELIVERY_OFFSET_TIME = 5

INVOICE_PRICE_MULTIPLIER = 100

_database = None
logger = logging.getLogger('tg_bot')


def get_database_connection():
    global _database
    if _database is None:
        database_password = REDIS_PASWORD
        database_host = REDIS_HOST
        database_port = REDIS_PORT
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


def send_menu(bot, update, menu_slice=''):
    products = [product['name'] for product in get_products()]
    if menu_slice:
        start, stop = map(lambda x: int(x), menu_slice.split(','))
    else:
        start, stop = 0, PRODUCT_SLICE_OFFSET

    keyboard = [[InlineKeyboardButton(product['name'], callback_data=product['id'])] for product in
                get_products()[slice(start, stop)]]
    slice_keys = []
    if start > 0:
        slice_keys.extend([InlineKeyboardButton('⬅ Назад',
                                                callback_data=f'slice_{start - PRODUCT_SLICE_OFFSET},{stop - PRODUCT_SLICE_OFFSET}')])
    if stop < len(products):
        slice_keys.extend([InlineKeyboardButton('Вперед ➡',
                                                callback_data=f'slice_{start + PRODUCT_SLICE_OFFSET},{stop + PRODUCT_SLICE_OFFSET}')])

    keyboard.append(slice_keys)
    keyboard.append([InlineKeyboardButton('🛒 Корзина', callback_data='cart')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query:
        query = update.callback_query
        chat_id = update.callback_query.message.chat_id
        bot.delete_message(chat_id=chat_id,
                           message_id=query.message.message_id)

    bot.send_message(chat_id=chat_id, text='Меню:', reply_markup=reply_markup)

    return 'HANDLE_MENU'


def handle_menu(bot, update):
    query = update.callback_query
    button = query.data

    if button.startswith('slice_'):
        _, menu_slice = button.split('_')
        return send_menu(bot, update, menu_slice)
    if button == 'cart':
        return send_cart(bot, update)
    else:
        return send_product_detail(bot, update)


def send_product_detail(bot, update):
    query = update.callback_query
    product_id = query.data
    product = get_product(product_id)

    name = product['name']
    price = product['price_formatted']
    description = product['description']
    image_id = product['image_id']

    message = f'{name}\nСтоимость {price}\n\n{description}'
    product_image_url = get_product_image_url(image_id)

    keyboard = [[InlineKeyboardButton('Положить в корзину', callback_data=product_id)],
                [InlineKeyboardButton('Назад', callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot.delete_message(chat_id=query.message.chat_id,
                       message_id=query.message.message_id)

    bot.send_photo(
        chat_id=query.message.chat_id,
        photo=product_image_url,
        caption=message,
        reply_markup=reply_markup)

    return 'HANDLE_PRODUCT_DETAIL'


def handle_product_detail(bot, update):
    query = update.callback_query
    button = query.data
    if button == 'menu':
        return send_menu(bot, update)
    else:
        chat_id = update.callback_query.message.chat_id
        product_id = button
        add_cart_item(chat_id, product_id)
        bot.answer_callback_query(query.id, text=f'Пицца добавлена в корзину', show_alert=False)
        return 'HANDLE_PRODUCT_DETAIL'


def send_cart(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    cart = get_cart(chat_id)
    text = get_cart_items_text(cart)
    keyboard = [[InlineKeyboardButton('В меню', callback_data='menu')]]

    if text:
        keyboard.extend(
            [[InlineKeyboardButton(f' Убрать {product["name"]}', callback_data=product['id'])] for product in
             cart['products']])
        keyboard.append([InlineKeyboardButton('Оформить заказ', callback_data='checkout')])

    else:
        text = 'Ваша корзина пуста'

    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.edit_message_text(text=text, chat_id=chat_id, message_id=query.message.message_id, reply_markup=reply_markup)
    return 'HANDLE_CART'


def handle_cart(bot, update):
    query = update.callback_query
    button = query.data
    if button == 'menu':
        return send_menu(bot, update)
    elif button == 'checkout':
        return send_location_request(bot, update)
    else:
        chat_id = update.callback_query.message.chat_id
        cart_item_id = button
        remove_cart_item(chat_id, cart_item_id)
        bot.answer_callback_query(query.id, text=f'Пица удалена из корзины', show_alert=False)
        return send_cart(bot, update)


def send_location_request(bot, update):
    query = update.callback_query
    bot.edit_message_text(text='Пришлите ваш адрес или геолокацию', chat_id=query.message.chat_id,
                          message_id=query.message.message_id)
    return 'HANDLE_LOCATION_REQUEST'


def handle_location_request(bot, update):
    message = update.message
    if message.location:
        user_location = (message.location.longitude, message.location.latitude)
    else:
        user_location = get_address_coordinates(message.text)

    if not user_location:
        message.reply_text('Не могу распознать этот адрес')
        return 'HANDLE_LOCATION_REQUEST'

    return send_delivery_options(bot, update, user_location)


def send_delivery_options(bot, update, user_location):
    chat_id = update.message.chat_id

    nearest_pizzeria = get_nearest_pizzeria(user_location)
    pizzeria_id, distance = nearest_pizzeria
    pizzeria_address = get_pizzeria(pizzeria_id)['address']
    delivery_price = None
    text = None

    keyboard = [[InlineKeyboardButton('Самовывоз', callback_data=f'pickup_{pizzeria_id}')],
                [InlineKeyboardButton('Другой адрес', callback_data='change_address')]
                ]

    for distance_limit, price in DELIVERY_OPTIONS.items():
        if distance <= distance_limit:
            delivery_price = price
            break

    if delivery_price is None:
        text = f'''Простите, но так далеко мы пицу не повезем. Ближайшая пицерия в {round(distance)} км. от вас.

Самостоятельно пиццу можно забрать из пиццерии по адресу {pizzeria_address}'''

    elif delivery_price == 0:
        text = f'''Может, заберете пиццу из нашей пицерии неподалеку? Она всего в {int(distance * 1000)} метрах от вас!
Вот ее адрес {pizzeria_address}

А можем и бесплатно доставить, нам не сложно c:'''
        keyboard.insert(0, [InlineKeyboardButton('Бесплатная доставка', callback_data=f'delivery_0_{user_location}')])

    elif delivery_price > 0:
        text = f'''Похоже, придется ехать до вас на самокате. Доставка будет стоить {delivery_price} руб.

Самостоятельно пиццу можно забрать из пиццерии по адресу {pizzeria_address}

Доставляем или самовывоз?'''
        keyboard.insert(0, [InlineKeyboardButton(f'Доставка за {delivery_price} руб.',
                                                 callback_data=f'delivery_{delivery_price}_{user_location}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    return 'HANDLE_DELIVERY_OPTIONS'


def handle_delivery_options(bot, update):
    query = update.callback_query
    button = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if button.startswith('delivery'):
        _, delivery_price, user_location = button.split('_')
        user_location = make_tuple(user_location)
        delivery_price = int(delivery_price)
        return add_delivery_order(bot, update, delivery_price, user_location)

    elif button.startswith('pickup'):
        _, pizzeria_id = button.split('_')
        pizzeria_address = get_pizzeria(pizzeria_id)['address']
        bot.edit_message_text(text=f'Вы можете забрать вашу пицу по адресу {pizzeria_address}\nСпасибо за заказ!',
                              chat_id=chat_id, message_id=message_id)
        return 'FINISH'
    elif button == 'change_address':
        return send_location_request(bot, update)


def add_delivery_order(bot, update, delivery_price, customer_location):
    query = update.callback_query
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    longitude, latitude = customer_location
    customer_location = {
        'longitude': longitude,
        'latitude': latitude,
        'delivery-price': delivery_price,
        'customer_id': chat_id,
    }
    add_customer_location(customer_location)
    add_delivery_to_cart(chat_id, delivery_price)

    cart = get_cart(chat_id)
    cart_text = get_cart_items_text(cart)

    customer_text = f'Доставим пицу в течении часа после оплаты.\n\n{cart_text}'
    keyboard = [[InlineKeyboardButton('💳 Оплатить', callback_data='payment')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.edit_message_text(text=customer_text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)

    return 'WAITING PAYMENT'


def send_order_to_courier(bot, update):
    customer_id = update.message.chat_id
    customer_location = get_customer_location(str(customer_id))
    pizzeria_id, _ = get_nearest_pizzeria(customer_location)
    courier_id = get_pizzeria(pizzeria_id)['courier-id']
    cart = get_cart(customer_id)
    cart_text = get_cart_items_text(cart)
    courier_text = f'Заказ {customer_id}\n\n{cart_text}\n\nЗАКАЗ ОПЛАЧЕН'
    bot.send_message(chat_id=courier_id, text=courier_text)
    longitude, latitude = customer_location
    bot.send_location(chat_id=courier_id, latitude=latitude, longitude=longitude)


def handle_payment(bot, update):
    query = update.callback_query
    button = query.data
    if button == 'payment':
        return send_invoice(bot, update)


def send_invoice(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    cart = get_cart(chat_id)
    title = f'Заказ {chat_id}'
    description = 'Пицца'
    payload = 'Pizza_payment'
    provider_token = TELEGRAM_PAYMENT_TOKEN
    start_parameter = TELEGRAM_PAYMENT_PARAMETER
    currency = 'RUB'
    prices = [LabeledPrice(f'{pizza["name"]}, {pizza["quantity"]} шт.', pizza['unit_price'] * INVOICE_PRICE_MULTIPLIER)
              for pizza in cart['products'] if pizza["name"] != DELIVERY_ITEM_NAME]
    delivery = next(item for item in cart['products'] if item['name'] == DELIVERY_ITEM_NAME)
    prices.append(LabeledPrice(delivery['name'], delivery['unit_price'] * INVOICE_PRICE_MULTIPLIER))

    bot.sendInvoice(chat_id, title, description, payload,
                    provider_token, start_parameter, currency, prices)

    return 'WAITING PAYMENT'


def process_precheckout(bot, update):
    query = update.pre_checkout_query
    if query.invoice_payload != 'Pizza_payment':
        bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=False,
                                      error_message='Что-то пошло не так. Попробуйте повторить оплату.')
    else:
        bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)


def process_successful_payment(bot, update, job_queue):
    chat_id = update.message.chat_id
    send_order_to_courier(bot, update)
    update.message.reply_text('Мы получили платеж и начали готовить пиццу. Курьер доставит ваш заказ в течении часа')
    job_queue.run_once(send_message_after_delivery, MESAGE_AFTER_DELIVERY_OFFSET_TIME, context=chat_id)


def send_message_after_delivery(bot, job):
    bot.send_message(chat_id=job.context,
                     text='Приятного аппетита! *место для рекламы*\n\n*сообщение что делать если пицца не пришла*')


def handle_users_reply(bot, update):
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': send_menu,
        'FINISH': send_menu,
        'HANDLE_MENU': handle_menu,
        'HANDLE_PRODUCT_DETAIL': handle_product_detail,
        'HANDLE_CART': handle_cart,
        'HANDLE_LOCATION_REQUEST': handle_location_request,
        'HANDLE_DELIVERY_OPTIONS': handle_delivery_options,
        'WAITING PAYMENT': handle_payment,
    }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(bot, update)
        db.set(chat_id, next_state)
    except Exception as err:
        logger.error(err)


def start_bot():
    logger.info(f'TG bot started')
    updater = Updater(TELEGRAM_TOKEN, request_kwargs=REQUEST_KWARGS)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.location, handle_users_reply, edited_updates=True))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    dispatcher.add_handler(PreCheckoutQueryHandler(process_precheckout))
    dispatcher.add_handler(MessageHandler(Filters.successful_payment, process_successful_payment, pass_job_queue=True))
    updater.start_polling()


if __name__ == '__main__':
    start_bot()
