import os

import requests
from flask import Flask, request
from dotenv import load_dotenv

from moltin import get_products, get_product_image_url, get_categories, add_cart_item
from database import get_user_state, set_user_state

load_dotenv()

app = Flask(__name__)

FACEBOOK_TOKEN = os.getenv('FACEBOOK_APP_KEY')
COMMON_CATEGORY_ID = '4531e739-3554-4042-9dfe-1972a860e6fe'
USER_DATABASE_PREFIX = 'facebook_'


@app.route('/', methods=['GET'])
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        if not request.args.get('hub.verify_token') == os.getenv('FACEBOOK_VERIFY_TOKEN'):
            return 'Verification token mismatch', 403
        return request.args['hub.challenge'], 200

    return 'Hello world', 200


@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    print(data)
    if data['object'] == 'page':
        for entry in data['entry']:
            if entry.get('messaging'):
                for messaging_event in entry['messaging']:
                    user_id = messaging_event['sender']['id']
                    recipient_id = messaging_event['recipient']['id']
                    if messaging_event.get('message'):
                        message = messaging_event['message']['text']
                    elif messaging_event.get('postback'):
                        message = messaging_event['postback']['payload']
                    else:
                        message = None
                    print('webhook')
                    print(message)
                    try:
                        handle_users_reply(user_id, message)
                    except:
                        print('error')
    return 'ok', 200


def handle_start(user_id, message):
    return send_menu(user_id)


def handle_users_reply(user_id, message):
    print(f'handle_users_reply({user_id}, {message})')
    states_functions = {
        'START': handle_start,
        'HANDLE_MENU': handle_menu,
    }
    user_state = get_user_state(USER_DATABASE_PREFIX+user_id)
    print('user_state get_user_state', user_state)
    if not user_state or user_state not in states_functions.keys():
        user_state = 'START'
    if message == '/start':
        user_state = 'START'
    print('user_state if if if', user_state)
    state_handler = states_functions[user_state]
    print('state_handler', state_handler)
    next_state = state_handler(user_id, message)
    set_user_state(USER_DATABASE_PREFIX + user_id, next_state)
    print('next_state', next_state)


def send_message(user_id, message):
    params = {'access_token': FACEBOOK_TOKEN}
    headers = {'Content-Type': 'application/json'}
    request_content = {
        'recipient': {
            'id': user_id
        },
        'message': {
            'text': message
        }
    }
    response = requests.post(
        'https://graph.facebook.com/v2.6/me/messages',
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def _send_test(user_id):
    params = {'access_token': FACEBOOK_TOKEN}
    headers = {'Content-Type': 'application/json'}
    request_content = {
        'recipient': {
            'id': user_id
        },
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'button',
                    'text': 'Try the postback button!',
                    'buttons': [
                        {
                            'type': 'postback',
                            'title': 'Postback Button',
                            'payload': 'DEVELOPER_DEFINED_PAYLOAD'
                        }
                    ]
                }
            }
        }
    }
    response = requests.post(
        'https://graph.facebook.com/v2.6/me/messages',
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def send_menu(user_id, category_id=COMMON_CATEGORY_ID):
    menu_action_card = {
        'title': 'Меню',
        'image_url': 'https://seeklogo.com/images/P/pizza-logo-9092058631-seeklogo.com.png',
        'subtitle': 'Здесь вы можете выбрать один из вариантов',
        'buttons': [
            {
                'type': 'postback',
                'title': 'Корзина',
                'payload': 'show_card'
            },
            {
                'type': 'postback',
                'title': 'Акции',
                'payload': 'offers'
            },
            {
                'type': 'postback',
                'title': 'Оформить заказ',
                'payload': 'checkout'
            },
        ]
    }
    menu = [{
        'title': f'{product["name"]} - {product["meta"]["display_price"]["with_tax"]["formatted"]}',
        'image_url': get_product_image_url(product['relationships']['main_image']['data']['id']),
        'subtitle': product['description'],
        'buttons': [
            {
                'type': 'postback',
                'title': 'Добавить в корзину',
                'payload': f'add_to_card~{product["id"]}'
            }
        ]
    }
        for product in get_products(category_id=category_id)]
    menu_other_category = {

        'title': 'Не нашли нужную пицу?',
        'image_url': 'https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg',
        'subtitle': 'Остальные пицы можно посмотреть в других категориях',
        'buttons': [
            {
                'type': 'postback',
                'title': category['name'],
                'payload': 'change_category~' + category['id']
            }
            for category in get_categories() if category['id'] != category_id]
    }

    menu.insert(0, menu_action_card)
    menu.append(menu_other_category)
    params = {'access_token': FACEBOOK_TOKEN}
    headers = {'Content-Type': 'application/json'}
    request_content = {
        'recipient': {
            'id': user_id
        },
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'generic',
                    'image_aspect_ratio': 'square',
                    'elements': menu
                }
            }
        }
    }
    response = requests.post(
        'https://graph.facebook.com/v2.6/me/messages',
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()

    return 'HANDLE_MENU'


def handle_menu(user_id, message):
    print(f'handle_menu({user_id}, {message})')
    if message.startswith('add_to_card'):
        _, product_id = message.split('~')
        add_cart_item(USER_DATABASE_PREFIX + user_id, product_id)
    if message.startswith('change_category'):
        _, category_id = message.split('~')
        return send_menu(user_id, category_id=category_id)

    return 'HANDLE_MENU'


if __name__ == '__main__':
    app.run(debug=True)
