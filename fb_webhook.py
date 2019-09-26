import os

import requests
from flask import Flask, request
from dotenv import load_dotenv

from moltin import get_products, get_product_image_url, get_categories

load_dotenv()

app = Flask(__name__)
FACEBOOK_TOKEN = os.getenv('FACEBOOK_APP_KEY')
COMMON_CATEGORY_ID = '4531e739-3554-4042-9dfe-1972a860e6fe'


@app.route('/', methods=['GET'])
def verify():
    '''
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    '''
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        if not request.args.get('hub.verify_token') == os.getenv('FACEBOOK_VERIFY_TOKEN'):
            return 'Verification token mismatch', 403
        return request.args['hub.challenge'], 200

    return 'Hello world', 200


@app.route('/', methods=['POST'])
def webhook():
    '''
    Основной вебхук, на который будут приходить сообщения от Facebook.
    '''
    data = request.get_json()
    print(data)
    if data['object'] == 'page':
        for entry in data['entry']:
            if entry.get('messaging'):
                for messaging_event in entry['messaging']:
                    if messaging_event.get('message'):
                        sender_id = messaging_event['sender']['id']
                        recipient_id = messaging_event['recipient']['id']
                        message_text = messaging_event['message']['text']
                        try:
                            send_message(sender_id, message_text)
                            send_menu(sender_id)
                        except:
                            print('error')
    return 'ok', 200


def send_message(recipient_id, message_text):
    params = {'access_token': FACEBOOK_TOKEN}
    headers = {'Content-Type': 'application/json'}
    request_content = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': message_text
        }
    }
    response = requests.post(
        'https://graph.facebook.com/v2.6/me/messages',
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def _send_test(recipient_id):
    params = {'access_token': FACEBOOK_TOKEN}
    headers = {'Content-Type': 'application/json'}
    request_content = {
        'recipient': {
            'id': recipient_id
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


def send_menu(recipient_id, category_id=COMMON_CATEGORY_ID):
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
                'payload': f'add_to_card_{product["id"]}'
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
                'payload': f'change_category_{category["id"]}'
            }
            for category in get_categories() if category['id'] != category_id]
    }

    menu.insert(0, menu_action_card)
    menu.append(menu_other_category)
    print(*menu, sep='\n\n')
    params = {'access_token': FACEBOOK_TOKEN}
    headers = {'Content-Type': 'application/json'}
    request_content = {
        'recipient': {
            'id': recipient_id
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
    print(response.content)
    response.raise_for_status()


if __name__ == '__main__':
    app.run(debug=True)
