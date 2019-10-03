import os
import logging
from datetime import datetime

from dotenv import load_dotenv
import requests
from slugify import slugify

load_dotenv()
MOLTIN_CLIENT_ID = os.getenv('MOLTIN_CLIENT_ID')
MOLTIN_SECRET = os.getenv('MOLTIN_SECRET')
MOLTIN_ENDPOINT = 'https://api.moltin.com'
MOLTIN_API_VERSION = 'v2'

logger = logging.getLogger('moltin')

_token = None
_token_expires = None
TOKEN_EXPIRES_TIMESHIFT = 10


def get_token():
    global _token, _token_expires
    if not _token or _token_expires <= int(datetime.utcnow().timestamp()):
        data = {
            'client_id': MOLTIN_CLIENT_ID,
            'client_secret': MOLTIN_SECRET,
            'grant_type': 'client_credentials'
        }
        response = requests.post(f'{MOLTIN_ENDPOINT}/oauth/access_token', data=data)
        response.raise_for_status()
        _token = f'{response.json()["token_type"]} {response.json()["access_token"]}'
        _token_expires = response.json()['expires'] - TOKEN_EXPIRES_TIMESHIFT
    return _token


def add_product(product):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'product',
            'name': product['name'],
            'slug': slugify(product['name']),
            'sku': str(product['id']),
            'description': product['description'],
            'manage_stock': False,
            'price': [
                {
                    'amount': product['price'],
                    'currency': 'RUR',
                    'includes_tax': True
                }
            ],
            'status': 'live',
            'commodity_type': 'physical'
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/products'
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    product_id = response.json()['data']['id']

    return product_id


def load_image(image_path):
    headers = {
        'Authorization': get_token()
    }

    files = {
        'file': (image_path, open(image_path, 'rb')),
        'public': (None, 'true'),
    }
    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/files'

    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()

    file_id = response.json()['data']['id']

    return file_id


def link_product_image(product_id, image_id):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'main_image',
            'id': image_id,
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/products/{product_id}/relationships/main-image'
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    product_id = response.json()['data']['id']

    return product_id


def add_flow(name, description=None):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'flow',
            'name': name,
            'slug': slugify(name),
            'description': description,
            'enabled': True
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/flows'
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    flow_id = response.json()['data']['id']

    return flow_id


def add_flow_filed(flow_id, field):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'field',
            'name': field['name'],
            'slug': slugify(field['name']),
            'field_type': field['type'],
            'description': field['description'],
            'required': field['required'],
            'unique': field['unique'],
            'default': field['default'],
            'enabled': True,
            'omit_null': True,
            'relationships': {
                'flow': {
                    'data': {
                        'type': 'flow',
                        'id': flow_id
                    }
                }
            }
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/fields'
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    product_id = response.json()['data']['id']

    return product_id


def add_flow_entry(flow_slug, entry):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'entry',

        }
    }

    for field, value in entry.items():
        data['data'][field] = value

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/flows/{flow_slug}/entries'
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    flow_id = response.json()['data']['id']

    return flow_id


def get_flow_entries(flow_slug):
    headers = {
        'Authorization': get_token(),
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/flows/{flow_slug}/entries'
    response = requests.get(url, headers=headers)

    response.raise_for_status()

    return response.json()['data']


def get_flow_entry(flow_slug, entry_id):
    headers = {
        'Authorization': get_token(),
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/flows/{flow_slug}/entries/{entry_id}'
    response = requests.get(url, headers=headers)

    response.raise_for_status()

    return response.json()['data']


def get_products(category_id=None):
    headers = {
        'Authorization': get_token(),
    }
    params = {}
    if category_id:
        params['filter'] = f'eq(category.id,{category_id})'

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/products'

    response = requests.get(url, headers=headers, params=params)

    response.raise_for_status()

    return response.json()['data']


def get_product(product_id):
    headers = {
        'Authorization': get_token(),
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/products/{product_id}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()['data']

    product = {
        'id': data['id'],
        'name': data['name'],
        'description': data['description'],
        'price': data['price'][0]['amount'],
        'price_formatted': data['meta']['display_price']['with_tax']['formatted'],
        'image_id': data['relationships']['main_image']['data']['id'],
    }

    return product


def add_cart_item(customer_id, product_id, quantity=1):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': quantity
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/carts/:{customer_id}/items'
    response = requests.post(url, headers=headers, json=data)

    response.raise_for_status()


def add_cart_custom_item(customer_id, item_name, price, quantity=1):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'custom_item',
            'name': item_name,
            'sku': slugify(item_name),
            'quantity': quantity,
            'price': {
                'amount': price
            }
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/carts/:{customer_id}/items'
    response = requests.post(url, headers=headers, json=data)

    response.raise_for_status()


def remove_cart_item(customer_id, cart_item_id):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }
    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/carts/:{customer_id}/items/{cart_item_id}'
    response = requests.delete(url, headers=headers)

    response.raise_for_status()


def get_cart(customer_id):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }
    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/carts/:{customer_id}/items'
    response = requests.get(url, headers=headers)

    response.raise_for_status()

    products = []
    for product in response.json()['data']:
        product_info = {
            'id': product['id'],
            'product_id': product.get('product_id', 'id'),
            'sku': product.get('sku'),
            'name': product['name'],
            'description': product.get('description'),
            'quantity': product['quantity'],
            'unit_price': product['unit_price']['amount'],
            'unit_price_formatted': product['meta']['display_price']['with_tax']['unit']['formatted'],
            'total_price_formatted': product['meta']['display_price']['with_tax']['value']['formatted'],
            'image_url': product['image']['href']
        }
        products.append(product_info)
    total_price_formatted = response.json()['meta']['display_price']['with_tax']['formatted']
    total_price = response.json()['meta']['display_price']['with_tax']['amount']

    return {'products': products, 'total_price_formatted': total_price_formatted, 'total_price': total_price}


def delete_cart(customer_id):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }
    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/carts/:{customer_id}'
    response = requests.delete(url, headers=headers)

    response.raise_for_status()


def get_product_image_url(image_id):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }
    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/files/{image_id}'
    response = requests.get(url, headers=headers)

    response.raise_for_status()

    return response.json()['data']['link']['href']


def get_customer(customer_id=None, email=None):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }
    if customer_id:
        url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/customers/:{customer_id}'
    elif email:
        url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/customers?filter=eq(email,{email})'
    else:
        return
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()['data']


def add_customer(name, email):
    headers = {
        'Authorization': get_token(),
        'Content-Type': 'application/json',
    }

    data = {
        'data': {
            'type': 'customer',
            'name': name,
            'email': email,
        }
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/customers'

    response = requests.post(url, headers=headers, json=data)

    error = response.json().get('errors', [])

    customer_id = None

    if not error:
        customer_id = response.json()['data']['id']
    elif error[0].get('title') == 'Duplicate email':
        customer_id = get_customer(email=email)[0]['id']

    return customer_id


def get_categories():
    headers = {
        'Authorization': get_token(),
    }

    url = f'{MOLTIN_ENDPOINT}/{MOLTIN_API_VERSION}/categories'

    response = requests.get(url, headers=headers)

    response.raise_for_status()

    return response.json()['data']


def main():
    pass


if __name__ == '__main__':
    main()
