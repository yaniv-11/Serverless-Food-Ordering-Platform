"""One-time seed job: run this once via the Lambda console's Test button to
populate the Restaurants and MenuItems DynamoDB tables. Safe to run more than
once - it skips seeding if data already exists."""

import os

import boto3

RESTAURANTS_TABLE = os.environ["RESTAURANTS_TABLE"]
MENU_ITEMS_TABLE = os.environ["MENU_ITEMS_TABLE"]

dynamodb = boto3.resource("dynamodb")
restaurants_table = dynamodb.Table(RESTAURANTS_TABLE)
menu_items_table = dynamodb.Table(MENU_ITEMS_TABLE)

SAMPLE_RESTAURANTS = [
    {
        "id": "1",
        "name": "Spice Villa",
        "cuisine": "North Indian, Mughlai",
        "rating": 4.3,
        "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=600",
        "address": "12 MG Road, Bengaluru",
        "menu": [
            {"name": "Butter Chicken", "description": "Creamy tomato curry with tender chicken", "price": 320, "category": "Main Course", "is_veg": False, "image_url": "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=400"},
            {"name": "Paneer Tikka", "description": "Grilled cottage cheese with spices", "price": 260, "category": "Starters", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=400"},
            {"name": "Garlic Naan", "description": "Tandoor baked flatbread with garlic", "price": 60, "category": "Breads", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1626074353765-517a681e40be?w=400"},
            {"name": "Dal Makhani", "description": "Slow cooked black lentils in butter and cream", "price": 220, "category": "Main Course", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1626777553635-be379dd3277a?w=400"},
        ],
    },
    {
        "id": "2",
        "name": "Pizza Piazza",
        "cuisine": "Italian, Pizza",
        "rating": 4.5,
        "image_url": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600",
        "address": "45 Brigade Road, Bengaluru",
        "menu": [
            {"name": "Margherita Pizza", "description": "Classic tomato, mozzarella and basil", "price": 280, "category": "Pizza", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400"},
            {"name": "Pepperoni Pizza", "description": "Loaded with pepperoni and cheese", "price": 350, "category": "Pizza", "is_veg": False, "image_url": "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=400"},
            {"name": "Garlic Bread", "description": "Toasted bread with garlic butter and herbs", "price": 150, "category": "Starters", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1573140401552-3fab0b24427f?w=400"},
            {"name": "Pasta Alfredo", "description": "Creamy white sauce pasta", "price": 260, "category": "Pasta", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1645112411341-6c4fd023714a?w=400"},
        ],
    },
    {
        "id": "3",
        "name": "Dragon Wok",
        "cuisine": "Chinese, Asian",
        "rating": 4.1,
        "image_url": "https://images.unsplash.com/photo-1552566626-52f8b828add9?w=600",
        "address": "8 Indiranagar, Bengaluru",
        "menu": [
            {"name": "Veg Hakka Noodles", "description": "Stir fried noodles with vegetables", "price": 200, "category": "Noodles", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1585032226651-759b368d7246?w=400"},
            {"name": "Chilli Chicken", "description": "Spicy Indo-Chinese chicken starter", "price": 280, "category": "Starters", "is_veg": False, "image_url": "https://images.unsplash.com/photo-1626200926749-011a68b1b0a7?w=400"},
            {"name": "Manchurian", "description": "Fried vegetable balls in tangy sauce", "price": 220, "category": "Starters", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1625944230945-1b7dd3b949ab?w=400"},
            {"name": "Fried Rice", "description": "Wok tossed rice with vegetables and egg", "price": 210, "category": "Rice", "is_veg": False, "image_url": "https://images.unsplash.com/photo-1603133872878-684f208fb84b?w=400"},
        ],
    },
    {
        "id": "4",
        "name": "Burger Barn",
        "cuisine": "American, Fast Food",
        "rating": 4.0,
        "image_url": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=600",
        "address": "21 Koramangala, Bengaluru",
        "menu": [
            {"name": "Classic Cheeseburger", "description": "Beef patty with cheese, lettuce and tomato", "price": 240, "category": "Burgers", "is_veg": False, "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400"},
            {"name": "Veggie Burger", "description": "Grilled veggie patty with special sauce", "price": 200, "category": "Burgers", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1520072959219-c595dc870360?w=400"},
            {"name": "French Fries", "description": "Crispy golden fries with seasoning", "price": 120, "category": "Sides", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=400"},
            {"name": "Chocolate Shake", "description": "Thick chocolate milkshake", "price": 150, "category": "Beverages", "is_veg": True, "image_url": "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=400"},
        ],
    },
]


def lambda_handler(event, context):
    existing = restaurants_table.scan(Select="COUNT")
    if existing["Count"] > 0:
        print("Restaurants table already has data, skipping seed.")
        return

    for r in SAMPLE_RESTAURANTS:
        restaurants_table.put_item(
            Item={
                "id": r["id"],
                "name": r["name"],
                "cuisine": r["cuisine"],
                "rating": str(r["rating"]),
                "image_url": r["image_url"],
                "address": r["address"],
            }
        )
        for i, item in enumerate(r["menu"]):
            menu_items_table.put_item(
                Item={
                    "restaurant_id": r["id"],
                    "menu_item_id": f"{r['id']}-{i + 1}",
                    "name": item["name"],
                    "description": item["description"],
                    "price": str(item["price"]),
                    "category": item["category"],
                    "is_veg": item["is_veg"],
                    "image_url": item["image_url"],
                }
            )

    print(f"Seeded {len(SAMPLE_RESTAURANTS)} restaurants successfully.")
