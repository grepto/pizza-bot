import json
import os

import requests

from moltin import load_image, add_product, link_product_image, get_products, get_product_image_url
from database import get_menu_from_db, load_menu_to_db


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


def cashe_menu():
    menu = get_products()
    for menu_item in menu:
        menu_item['main_image_url'] = get_product_image_url(menu_item['relationships']['main_image']['data']['id'])
    load_menu_to_db(menu)
    return 'Menu has been cached'


def get_menu(category_id=None):
    if not category_id:
        menu = get_menu_from_db()
    else:
        menu = []
        for menu_item in get_menu_from_db():
            if [category for category in menu_item['relationships']['categories']['data'] if
                category['id'] == category_id]:
                menu.append(menu_item)
    return menu


def main():
    print(cashe_menu())


if __name__ == '__main__':
    main()
