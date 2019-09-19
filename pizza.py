import json
import os
import logging

import requests
from slugify import slugify
import yandex_geocoder
from geopy.distance import lonlat, distance

from moltin import load_image, add_product, link_product_image, add_flow_entry, get_flow_entries, get_flow_entry, \
    get_cart, add_cart_custom_item

MENU_FILE = 'menu.json'
ADDRESSES_FILE = 'addresses.json'
PIZZERIA_FLOW_SLUG = 'pizzeria'
CUSTOMER_LOCATION_FLOW_SLUG = 'customer_location'
DELIVERY_ITEM_NAME = 'Доставка'

logger = logging.getLogger('pizza')


def update_menu(menu_file):
    with open(menu_file, 'r') as file:
        menu = json.load(file)

    for pizza in menu:
        image_url = pizza['product_image']['url']
        image_name = f'{pizza["id"]}.jpg'
        response = requests.get(image_url)

        with open(image_name, 'wb') as image:
            image.write(response.content)

        product = {
            'id': pizza['id'],
            'name': pizza['name'],
            'description': pizza['description'],
            'price': pizza['price'],
        }

        moltin_product_id = add_product(product)
        moltin_image_id = load_image(image_name)
        link_product_image(moltin_product_id, moltin_image_id)

        os.remove(image_name)


def update_addresses(addresses_file):
    with open(addresses_file, 'r') as file:
        addresses = json.load(file)

    for address in addresses:
        pizzeria = {
            'address': address['address']['full'],
            'alias': address['alias'],
            'longitude': address['coordinates']['lon'],
            'latitude': address['coordinates']['lat'],
        }

        add_flow_entry(PIZZERIA_FLOW_SLUG, pizzeria)


def get_address_coordinates(address):
    try:
        coordinates = yandex_geocoder.Client.coordinates(address)
    except yandex_geocoder.exceptions.YandexGeocoderAddressNotFound:
        return None
    return coordinates


def get_nearest_pizzeria(coordinates):
    pizzerias = []
    for pizzeria in get_flow_entries(PIZZERIA_FLOW_SLUG):
        pizzeria_coodrinates = (pizzeria['latitude'], pizzeria['longitude'])
        pizzeria_distance = round(distance(pizzeria_coodrinates, lonlat(*coordinates)).km, 3)
        pizzerias.append((pizzeria['id'], pizzeria_distance))

    nearest_pizzeria = min(pizzerias, key=lambda x: x[1])

    return nearest_pizzeria


def get_pizzeria(pizzeria_id):
    return get_flow_entry(PIZZERIA_FLOW_SLUG, pizzeria_id)


def add_customer_location(customer_location):
    return add_flow_entry(CUSTOMER_LOCATION_FLOW_SLUG, customer_location)


def get_customer_location(customer_id):
    locations = [location for location in get_flow_entries(CUSTOMER_LOCATION_FLOW_SLUG) if
                 location['customer_id'] == customer_id]
    current_location = max(locations, key=lambda x: x['meta']['timestamps']['created_at'])
    return current_location['longitude'], current_location['latitude']


def is_delivery_in_cart(cart):
    return [product for product in cart['products'] if product['sku'] == slugify(DELIVERY_ITEM_NAME)] != []


def add_delivery_to_cart(cart_id, delivery_price):
    cart = get_cart(cart_id)
    if not is_delivery_in_cart(cart):
        add_cart_custom_item(cart_id, DELIVERY_ITEM_NAME, delivery_price)


def get_cart_items_text(cart):
    cart_items_text = None
    if cart['products']:
        text_rows = [
            '{0}\n{1}\n{3} шт. по цене {2} за штуку\nИтого {4}'.format(product['name'],
                                                                       product['description'],
                                                                       product['unit_price_formatted'],
                                                                       product['quantity'],
                                                                       product['total_price_formatted'])
            for product in cart['products'] if product['name'] != DELIVERY_ITEM_NAME]

        if is_delivery_in_cart(cart):
            delivery_item = next(item for item in cart['products'] if item['name'] == DELIVERY_ITEM_NAME)
            text_rows.append(f'Доставка {delivery_item["total_price_formatted"]}')

        text_rows.append(f'К оплате: {cart["total_price_formatted"]}')
        cart_items_text = '\n\n'.join(text_rows)

    return cart_items_text


def main():
    pass


if __name__ == '__main__':
    main()
