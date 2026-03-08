"""Mock customer review generator for demo purposes.

Generates realistic Indian e-commerce reviews with a mix of English and Hindi,
varied ratings, and authentic category-specific topics.
"""
import random
from datetime import datetime, timedelta

from app.services.mock_amazon_data import PRODUCTS

CATEGORY_REVIEWS = {
    "Kitchen": {
        "positive": [
            ("Excellent build quality!", "Build quality is top notch. Heat retention is amazing, keeps food warm for hours."),
            ("Non-stick coating works great", "Non-stick coating is superb. Easy to wash and food doesn't stick at all."),
            ("Bahut accha handle hai", "Handle ki grip bahut acchi hai. Non-stick coating bhi solid hai. Full paisa vasool."),
            ("Perfect for daily cooking", "Using daily for 3 months. Handle is sturdy and heat distribution is even."),
            ("Easy to wash, love it", "Cleaning is so easy. Just rinse and done. Build quality is premium feel."),
        ],
        "negative": [
            ("Non-stick coating peeled off", "Non-stick coating started peeling after 2 weeks. Handle feels loose. Very disappointing."),
            ("Heat retention is poor", "Flask doesn't keep water hot for more than 2 hours. Build quality is cheap."),
            ("Handle broke in a month", "Handle snapped while cooking. Very poor build quality. Not safe to use."),
            ("Bilkul bekar coating", "Non-stick coating ekdum kharab hai. Ek hafte mein nikal gayi. Paiso ki barbadi."),
        ],
        "neutral": [
            ("Theek hai, chalega", "Build quality is okay. Handle could be better. Easy to wash at least."),
            ("Average heat retention", "Heat retention is average. Non-stick coating works fine for now. Decent for the price."),
        ],
    },
    "Appliances": {
        "positive": [
            ("Excellent build quality!", "Build quality is very good. Works perfectly and heating is fast."),
            ("Energy efficient", "Power consumption is low and performance is great. Very happy with purchase."),
            ("Bahut accha product", "Performance ekdum first class hai. Silent operation. Recommended."),
            ("Worth every rupee", "Using for 2 months. No issues. Build quality is solid and performance is consistent."),
            ("Fast and efficient", "Heats up quickly. Build quality feels premium. Very satisfied."),
        ],
        "negative": [
            ("Stopped working after 1 week", "Was working fine but stopped suddenly. Build quality seems poor inside."),
            ("Very noisy operation", "Makes loud noise while running. Cannot use at night. Disappointed."),
            ("Kharab quality hai", "Ek hafte mein band ho gaya. Build quality bilkul cheap hai. Return karna padega."),
            ("Overheating problem", "Gets too hot after 10 minutes of use. Safety concern. Not recommended."),
        ],
        "neutral": [
            ("Decent performance", "Works as expected. Build quality is okay. Nothing extraordinary."),
            ("Average for the price", "Performance is average. Gets the job done but could be better."),
        ],
    },
    "Electronics": {
        "positive": [
            ("Amazing battery life!", "Battery life is outstanding. Lasts 2 full days with heavy use. Connectivity is seamless."),
            ("Sound quality is superb", "Sound quality blew my mind. Bass is deep and connectivity is instant."),
            ("Charging is super fast", "20W charging is actually fast. Battery goes from 0 to 100 in no time."),
            ("Bluetooth connectivity perfect", "Pairs instantly with my phone. Battery life is great. Sound quality is clear."),
            ("Bahut accha sound hai", "Sound quality ekdum zabardast. Battery life bhi 2 din chalti hai. Must buy."),
        ],
        "negative": [
            ("Battery drains fast", "Battery life is terrible. Barely lasts 4 hours. Connectivity drops frequently."),
            ("Charging cable broke", "Charging cable stopped working in 2 weeks. Cheap quality material."),
            ("Sound quality is tinny", "Sound quality is very poor. No bass at all. Connectivity issues with Android."),
            ("Bluetooth keeps disconnecting", "Connectivity is unreliable. Keeps disconnecting every 5 minutes. Waste of money."),
        ],
        "neutral": [
            ("Average battery", "Battery life is okay. Sound quality is decent. Connectivity works most of the time."),
            ("Charging speed is fine", "Charges at normal speed. Nothing special but does the job."),
        ],
    },
    "Home": {
        "positive": [
            ("Beautiful fabric quality", "Fabric quality is amazing. Color is exactly as shown. No shrinkage after washing."),
            ("Stitching is perfect", "Stitching is very neat. Fabric feels soft and premium. Color doesn't fade."),
            ("Bahut sundar hai", "Color bilkul picture jaisa hai. Fabric quality soft hai. Shrinkage nahi hua."),
            ("Great color, no fading", "Washed 5 times, color still vibrant. Stitching is strong. Very happy."),
            ("Soft and comfortable", "Fabric is very soft. Perfect color match. Stitching holds up well."),
        ],
        "negative": [
            ("Color faded after first wash", "Color completely faded after single wash. Fabric quality is very thin."),
            ("Shrinkage is terrible", "Shrunk by 2 inches after first wash. Stitching also came loose."),
            ("Stitching came apart", "Stitching is very poor. Came apart in 1 week. Fabric is scratchy."),
            ("Color bilkul alag hai", "Picture mein aur real mein bilkul alag color hai. Fabric bhi patla hai."),
        ],
        "neutral": [
            ("Color is okay", "Color is slightly different from picture. Fabric quality is average. Stitching is fine."),
            ("Decent for the price", "Fabric is okay. Some shrinkage after washing but manageable."),
        ],
    },
    "Personal Care": {
        "positive": [
            ("Amazing fragrance!", "Fragrance is long lasting and subtle. Feels great on skin. Packaging is neat."),
            ("Skin feels so smooth", "Skin feel after using is amazing. No irritation. Fragrance is pleasant."),
            ("Packaging is premium", "Loved the packaging. Fragrance is mild and nice. Skin feels fresh after use."),
            ("Bahut acchi fragrance", "Fragrance bahut acchi hai. Skin pe lagane ke baad soft feel hota hai. Must try."),
            ("Perfect grooming kit", "Everything you need in one pack. Fragrance is great and skin feel is smooth."),
        ],
        "negative": [
            ("Caused skin irritation", "After using, got rashes on skin. Fragrance is too strong. Packaging leaked."),
            ("Fragrance is chemical-like", "Fragrance smells artificial and chemical. Skin feels dry after use."),
            ("Packaging was broken", "Packaging was damaged. Product leaked inside the box. Very poor quality control."),
            ("Skin pe rash aa gaya", "Lagane ke baad skin pe rash ho gaya. Fragrance bhi bahut strong hai."),
        ],
        "neutral": [
            ("Average fragrance", "Fragrance is okay. Skin feel is average. Packaging could be better."),
            ("Theek hai product", "Fragrance is mild. Does the job but nothing special."),
        ],
    },
    "Bags": {
        "positive": [
            ("Zipper quality is great", "Zipper runs smooth. Waterproof in rain. Compartments are well designed."),
            ("Very comfortable straps", "Strap comfort is excellent. Carried for 8 hours, no back pain. Zipper is sturdy."),
            ("Waterproof and durable", "Tested in heavy Mumbai rain. Laptop was completely dry. Compartments are spacious."),
            ("Bahut accha bag hai", "Zipper quality solid hai. Waterproof bhi hai. Strap comfort ekdum best."),
            ("Perfect laptop bag", "Compartments fit everything neatly. Zipper quality is premium. Straps are padded."),
        ],
        "negative": [
            ("Zipper broke in 2 weeks", "Zipper quality is terrible. Broke while opening. Compartments are poorly stitched."),
            ("Not waterproof at all", "Claimed waterproof but my laptop got wet in light rain. Very risky."),
            ("Strap comfort is zero", "Straps dig into shoulders. No padding at all. Zipper is stiff."),
            ("Compartment stitching kharab", "Ek compartment ka stitching ek hafte mein nikal gaya. Zipper bhi tight hai."),
        ],
        "neutral": [
            ("Average bag", "Zipper quality is okay. Compartments are fine. Strap comfort could be better."),
            ("Does the job", "Waterproof coating seems thin. Compartments are decent. Zipper works."),
        ],
    },
}

DEFAULT_REVIEWS = {
    "positive": [
        ("Excellent quality!", "Product quality is very good. Packaging was also very neat. Value for money."),
        ("Very happy with purchase", "Delivery was on time and product works perfectly. Would recommend to everyone."),
        ("Best in this price range", "I compared many products before buying. This one is the best for the price."),
        ("Bahut accha product hai", "Maine bahut search kiya aur ye sabse accha mila. Quality ekdum first class hai."),
        ("Superb! Must buy", "Using it for 2 weeks now. No issues at all. Build quality is solid."),
    ],
    "negative": [
        ("Disappointed with quality", "Product looks different from pictures. Material quality is very poor."),
        ("Broke after 1 week", "Was working fine initially but stopped working after just one week. Waste of money."),
        ("Late delivery and damaged", "Delivery was 5 days late and packaging was damaged. Product had scratches."),
        ("Bilkul bekar product", "Paiso ki barbadi. Quality bahut kharab hai. Return kar raha hoon."),
    ],
    "neutral": [
        ("Okay product", "It's decent for the price. Nothing extraordinary but gets the job done."),
        ("Theek thaak hai", "Product theek hai. Na bahut accha na bahut bura. Chalega kaam se."),
    ],
}


def _get_category_pool(category: str) -> dict:
    """Get review templates for a category, falling back to defaults."""
    for key in CATEGORY_REVIEWS:
        if key.lower() in category.lower() or category.lower() in key.lower():
            return CATEGORY_REVIEWS[key]
    return DEFAULT_REVIEWS


def generate_mock_reviews(marketplace_account_id: int, seed: int = 42) -> list[dict]:
    """Generate mock reviews for all products.

    Returns list of dicts matching customer_reviews table schema.
    """
    rng = random.Random(seed)
    reviews = []
    review_counter = 0

    names = [
        "Rahul S.", "Priya M.", "Amit K.", "Sneha P.", "Rajesh G.",
        "Anjali T.", "Vikram D.", "Pooja R.", "Suresh B.", "Neha V.",
        "Arjun N.", "Divya L.", "Karan J.", "Meera H.", "Anil C.",
        "Swati F.", "Deepak W.", "Kavita A.", "Rohit E.", "Shruti I.",
    ]

    for product in PRODUCTS:
        num_reviews = rng.randint(6, 14)
        pool = _get_category_pool(product["category"])

        for _ in range(num_reviews):
            review_counter += 1

            rating = rng.choices([1, 2, 3, 4, 5], weights=[5, 8, 12, 35, 40])[0]

            if rating >= 4:
                title, body = rng.choice(pool["positive"])
            elif rating <= 2:
                title, body = rng.choice(pool["negative"])
            else:
                title, body = rng.choice(pool["neutral"])

            review_date = datetime.utcnow() - timedelta(days=rng.randint(1, 90))

            reviews.append({
                "marketplace_account_id": marketplace_account_id,
                "external_review_id": f"R{review_counter:06d}",
                "asin": product["asin"],
                "seller_sku": product["sku"],
                "rating": rating,
                "title": title,
                "body": body,
                "reviewer_name": rng.choice(names),
                "review_date": review_date,
                "verified_purchase": rng.random() < 0.75,
            })

    return reviews
