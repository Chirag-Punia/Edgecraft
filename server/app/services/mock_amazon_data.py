"""Mock Amazon SP-API connector for demo/hackathon use.

Generates realistic Indian e-commerce data with deterministic seeding.
Same interface as AmazonConnector so the sync worker can swap freely.
"""
import random
from datetime import datetime, timedelta, date
from decimal import Decimal


# Indian product catalog for realistic demo data
PRODUCTS = [
    {"name": "Borosil Stainless Steel Flask 1L", "brand": "Borosil", "category": "Kitchen", "asin": "B08X1GKZP1", "sku": "BOR-FLASK-1L", "price": 899},
    {"name": "Prestige Omega Deluxe Induction Base Fry Pan", "brand": "Prestige", "category": "Kitchen", "asin": "B07HGKR2ZN", "sku": "PRE-FRY-DLX", "price": 1299},
    {"name": "Cello Opalware Dazzle Dinner Set 35pcs", "brand": "Cello", "category": "Kitchen", "asin": "B09KXYZ123", "sku": "CEL-DIN-35", "price": 2499},
    {"name": "Bajaj Majesty New SWX 3 Sandwich Maker", "brand": "Bajaj", "category": "Appliances", "asin": "B01N5KURZ5", "sku": "BAJ-SWX3", "price": 1449},
    {"name": "Milton Thermosteel Flip Lid Flask 500ml", "brand": "Milton", "category": "Kitchen", "asin": "B072KXYZ45", "sku": "MIL-FLIP-500", "price": 649},
    {"name": "Pigeon by Stovekraft Amaze Plus Kettle 1.5L", "brand": "Pigeon", "category": "Appliances", "asin": "B07PQRST67", "sku": "PIG-KET-15", "price": 599},
    {"name": "Wonderchef Nutri-Blend Mixer Grinder", "brand": "Wonderchef", "category": "Appliances", "asin": "B08MNOP890", "sku": "WON-NB-MIX", "price": 2199},
    {"name": "Kuber Industries Cotton Bedsheet King Size", "brand": "Kuber", "category": "Home", "asin": "B09ABCDE12", "sku": "KUB-BED-KNG", "price": 799},
    {"name": "Story@Home Polyester Door Curtains Set of 2", "brand": "Story@Home", "category": "Home", "asin": "B07FGHIJ34", "sku": "STR-CUR-2PK", "price": 499},
    {"name": "Asian Paints Royale Glitz Paint 1L", "brand": "Asian Paints", "category": "Home Improvement", "asin": "B08KLMNO56", "sku": "ASP-GLZ-1L", "price": 450},
    {"name": "Havells Adonia LED Bulb 15W Pack of 4", "brand": "Havells", "category": "Lighting", "asin": "B09PQRST78", "sku": "HAV-LED-4PK", "price": 699},
    {"name": "Crompton Aura Prime Anti Dust Ceiling Fan", "brand": "Crompton", "category": "Appliances", "asin": "B08UVWXY90", "sku": "CRM-FAN-AUR", "price": 2899},
    {"name": "Park Avenue Good Morning Grooming Kit", "brand": "Park Avenue", "category": "Personal Care", "asin": "B07ZABCD12", "sku": "PAR-GRM-KIT", "price": 599},
    {"name": "Himalaya Herbals Face Wash Combo Pack", "brand": "Himalaya", "category": "Personal Care", "asin": "B08EFGHI34", "sku": "HIM-FACE-CB", "price": 350},
    {"name": "Wildcraft Unisex Laptop Backpack 35L", "brand": "Wildcraft", "category": "Bags", "asin": "B09JKLMN56", "sku": "WLD-BAG-35L", "price": 1599},
    {"name": "Noise ColorFit Pro 4 Smartwatch", "brand": "Noise", "category": "Electronics", "asin": "B0AOPQRS78", "sku": "NOI-CFP4", "price": 3499},
    {"name": "boAt Airdopes 141 TWS Earbuds", "brand": "boAt", "category": "Electronics", "asin": "B0BTUVWX90", "sku": "BOT-AD141", "price": 1299},
    {"name": "Portronics Adapto 62 USB-C Charger 20W", "brand": "Portronics", "category": "Electronics", "asin": "B09YZABCD1", "sku": "POR-CHG-20W", "price": 699},
]

INDIAN_CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Bangalore", "Karnataka"),
    ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"), ("Kolkata", "West Bengal"),
    ("Pune", "Maharashtra"), ("Ahmedabad", "Gujarat"), ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"), ("Surat", "Gujarat"), ("Nagpur", "Maharashtra"),
    ("Indore", "Madhya Pradesh"), ("Coimbatore", "Tamil Nadu"), ("Kochi", "Kerala"),
]

ORDER_STATUSES = ["Shipped", "Shipped", "Shipped", "Delivered", "Delivered", "Delivered",
                  "Delivered", "Pending", "Cancelled"]


class MockAmazonConnector:
    """Generates deterministic mock data matching the real SP-API response shape."""

    def __init__(self, credentials: dict | None = None):
        self._rng = random.Random(42)

    def get_orders(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict]:
        if created_after is None:
            created_after = datetime.utcnow() - timedelta(days=30)
        if created_before is None:
            created_before = datetime.utcnow()

        orders = []
        num_orders = self._rng.randint(60, 90)
        time_span = (created_before - created_after).total_seconds()

        for i in range(num_orders):
            order_time = created_after + timedelta(seconds=self._rng.uniform(0, time_span))
            city, state = self._rng.choice(INDIAN_CITIES)
            num_items = self._rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
            items_for_order = self._rng.sample(PRODUCTS, min(num_items, len(PRODUCTS)))
            total = sum(p["price"] * self._rng.randint(1, 3) for p in items_for_order)
            shipping = self._rng.choice([0, 0, 0, 40, 60, 99])

            orders.append({
                "AmazonOrderId": f"408-{self._rng.randint(1000000, 9999999)}-{self._rng.randint(1000000, 9999999)}",
                "PurchaseDate": order_time.isoformat() + "Z",
                "OrderStatus": self._rng.choice(ORDER_STATUSES),
                "FulfillmentChannel": self._rng.choice(["AFN", "AFN", "MFN"]),
                "OrderTotal": {"CurrencyCode": "INR", "Amount": str(total + shipping)},
                "ShippingAddress": {"City": city, "StateOrRegion": state},
                "NumberOfItemsShipped": num_items if self._rng.random() > 0.2 else 0,
                "ShippingPrice": str(shipping),
                "_mock_items": items_for_order,
            })

        return orders

    def get_order_items(self, order_id: str, _mock_items: list[dict] | None = None) -> list[dict]:
        items = _mock_items or self._rng.sample(PRODUCTS, self._rng.randint(1, 3))
        result = []
        for idx, product in enumerate(items):
            qty = self._rng.randint(1, 3)
            price = product["price"] * (1 + self._rng.uniform(-0.1, 0.1))
            tax = round(price * 0.18, 2)  # 18% GST
            discount = round(price * self._rng.choice([0, 0, 0.05, 0.10, 0.15]), 2)
            result.append({
                "OrderItemId": f"{order_id}-{idx + 1:02d}",
                "ASIN": product["asin"],
                "SellerSKU": product["sku"],
                "Title": product["name"],
                "QuantityOrdered": qty,
                "QuantityShipped": qty if self._rng.random() > 0.15 else 0,
                "ItemPrice": {"CurrencyCode": "INR", "Amount": str(round(price * qty, 2))},
                "ItemTax": {"CurrencyCode": "INR", "Amount": str(round(tax * qty, 2))},
                "PromotionDiscount": {"CurrencyCode": "INR", "Amount": str(round(discount * qty, 2))},
            })
        return result

    def get_inventory_summaries(self) -> list[dict]:
        summaries = []
        for product in PRODUCTS:
            fulfillable = self._rng.randint(0, 200)
            inbound = self._rng.randint(0, 50)
            reserved = self._rng.randint(0, 20)
            unfulfillable = self._rng.randint(0, 5)
            summaries.append({
                "sellerSku": product["sku"],
                "asin": product["asin"],
                "fnSku": f"X00{product['asin'][3:]}",
                "productName": product["name"],
                "inventoryDetails": {
                    "fulfillableQuantity": fulfillable,
                    "inboundWorkingQuantity": inbound,
                    "inboundShippedQuantity": 0,
                    "reservedQuantity": {"totalReservedQuantity": reserved},
                    "unfulfillableQuantity": {"totalUnfulfillableQuantity": unfulfillable},
                },
                "totalQuantity": fulfillable + inbound + reserved + unfulfillable,
            })
        return summaries

    def get_competitive_pricing(self, asin_list: list[str] | None = None) -> list[dict]:
        targets = [p for p in PRODUCTS if asin_list is None or p["asin"] in asin_list]
        results = []
        for product in targets:
            base_price = product["price"]
            your_price = base_price
            buybox_price = round(base_price * self._rng.uniform(0.95, 1.05), 2)
            lowest_price = round(base_price * self._rng.uniform(0.85, 1.0), 2)
            landed_price = round(your_price + self._rng.choice([0, 40, 60]), 2)
            results.append({
                "ASIN": product["asin"],
                "SellerSKU": product["sku"],
                "YourPrice": your_price,
                "LandedPrice": landed_price,
                "BuyBoxPrice": buybox_price,
                "LowestPrice": lowest_price,
                "IsBuyBoxWinner": your_price <= buybox_price,
            })
        return results
