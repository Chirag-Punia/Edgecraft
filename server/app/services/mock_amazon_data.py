"""Mock Amazon SP-API connector for demo/hackathon use.

Generates realistic Indian e-commerce data with deterministic seeding.
Same interface as AmazonConnector so the sync worker can swap freely.
All response shapes match the real SP-API JSON exactly.
"""
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

from app.enums import OrderStatus, FulfillmentChannel


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
    ("Mumbai", "Maharashtra"),
    ("Delhi", "Delhi"),
    ("Bangalore", "Karnataka"),
    ("Hyderabad", "Telangana"),
    ("Chennai", "Tamil Nadu"),
    ("Kolkata", "West Bengal"),
    ("Pune", "Maharashtra"),
    ("Ahmedabad", "Gujarat"),
    ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"),
    ("Surat", "Gujarat"),
    ("Nagpur", "Maharashtra"),
    ("Indore", "Madhya Pradesh"),
    ("Coimbatore", "Tamil Nadu"),
    ("Kochi", "Kerala"),
    ("Chandigarh", "Chandigarh"),
    ("Bhopal", "Madhya Pradesh"),
    ("Patna", "Bihar"),
    ("Visakhapatnam", "Andhra Pradesh"),
    ("Thiruvananthapuram", "Kerala"),
]

CITY_WEIGHTS = [
    14, 13, 12, 8, 7, 6, 6, 5, 4, 4,
    3, 3, 3, 2, 2, 2, 2, 1, 1, 1,
]

# Product popularity weights — top 6 products appear 2-3x more often
PRODUCT_WEIGHTS = [
    3, 3, 2, 2, 3, 2, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 3, 2, 1,
]

# Day-of-week seasonality multipliers (Monday=0 ... Sunday=6)
DAY_OF_WEEK_WEIGHTS = {
    0: 0.7,   # Monday
    1: 1.0,   # Tuesday
    2: 1.0,   # Wednesday
    3: 1.0,   # Thursday
    4: 1.2,   # Friday
    5: 1.4,   # Saturday
    6: 1.4,   # Sunday
}

EASYSHIP_STATUSES = [
    "PendingSchedule", "PendingPickUp", "PickedUp", "AtOriginFC",
    "AtDestinationFC", "OutForDelivery", "Delivered", None, None, None,
]

PAYMENT_METHODS = ["Other", "Other", "Other", "COD", "COD"]


def _money(amount, currency="INR") -> dict:
    """Create an SP-API Money object."""
    return {"CurrencyCode": currency, "Amount": str(round(amount, 2))}


def _weighted_order_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """Pick an order date with weekly seasonality and growth trend bias."""
    total_days = (end - start).days
    if total_days <= 0:
        return start

    candidates = []
    weights = []
    for d in range(total_days):
        day_dt = start + timedelta(days=d)
        dow_weight = DAY_OF_WEEK_WEIGHTS.get(day_dt.weekday(), 1.0)
        growth = 0.6 + 0.8 * (d / max(total_days - 1, 1))
        candidates.append(d)
        weights.append(dow_weight * growth)

    chosen_day = rng.choices(candidates, weights=weights, k=1)[0]
    hour_offset = rng.uniform(0, 24 * 3600)
    return start + timedelta(days=chosen_day, seconds=hour_offset)


class MockAmazonConnector:
    """Generates deterministic mock data matching the real SP-API response shape exactly."""

    def __init__(self, credentials: dict | None = None):
        self._rng = random.Random(42)

    def get_orders(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict]:
        if created_after is None:
            created_after = datetime.utcnow() - timedelta(days=180)
        if created_before is None:
            created_before = datetime.utcnow()

        orders = []
        num_orders = self._rng.randint(300, 380)

        # Target status distribution: ~10-12% Cancelled, ~5% Pending, ~5% Unshipped, rest Shipped/Delivered
        status_pool = (
            [OrderStatus.CANCELED] * 11
            + [OrderStatus.PENDING] * 5
            + [OrderStatus.UNSHIPPED] * 5
            + [OrderStatus.SHIPPED] * 30
            + [OrderStatus.DELIVERED] * 49
        )

        for i in range(num_orders):
            order_time = _weighted_order_date(self._rng, created_after, created_before)
            last_update = order_time + timedelta(hours=self._rng.uniform(1, 48))
            city, state = self._rng.choices(INDIAN_CITIES, weights=CITY_WEIGHTS, k=1)[0]
            num_items = self._rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
            items_for_order = self._rng.choices(PRODUCTS, weights=PRODUCT_WEIGHTS, k=num_items)
            # Deduplicate by ASIN (choices can repeat)
            seen_asins = set()
            unique_items = []
            for item in items_for_order:
                if item["asin"] not in seen_asins:
                    seen_asins.add(item["asin"])
                    unique_items.append(item)
            items_for_order = unique_items or [self._rng.choice(PRODUCTS)]

            total = sum(p["price"] * self._rng.randint(1, 3) for p in items_for_order)
            shipping = self._rng.choice([0, 0, 0, 40, 60, 99])
            status = self._rng.choice(status_pool)
            fulfillment = self._rng.choice([FulfillmentChannel.AFN, FulfillmentChannel.AFN, FulfillmentChannel.MFN])
            is_prime = self._rng.random() < 0.35
            payment_method = self._rng.choice(PAYMENT_METHODS)
            items_shipped = len(items_for_order) if status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED) else 0
            items_unshipped = len(items_for_order) - items_shipped

            earliest_delivery = order_time + timedelta(days=self._rng.randint(2, 4))
            latest_delivery = earliest_delivery + timedelta(days=self._rng.randint(1, 3))
            earliest_ship = order_time + timedelta(hours=self._rng.randint(4, 24))
            latest_ship = earliest_ship + timedelta(hours=self._rng.randint(12, 48))

            order = {
                "AmazonOrderId": f"408-{self._rng.randint(1000000, 9999999)}-{self._rng.randint(1000000, 9999999)}",
                "PurchaseDate": order_time.isoformat() + "Z",
                "LastUpdateDate": last_update.isoformat() + "Z",
                "OrderStatus": status,
                "FulfillmentChannel": fulfillment,
                "SalesChannel": "Amazon.in",
                "OrderType": "StandardOrder",
                "ShipServiceLevel": "Expedited" if is_prime else "Standard",
                "ShipmentServiceLevelCategory": "Expedited" if is_prime else "Standard",
                "OrderTotal": _money(total + shipping),
                "NumberOfItemsShipped": items_shipped,
                "NumberOfItemsUnshipped": items_unshipped,
                "PaymentMethod": payment_method,
                "PaymentMethodDetails": [payment_method],
                "MarketplaceId": "A21TJRUUN4KGV",
                "ShippingAddress": {
                    "City": city,
                    "StateOrRegion": state,
                    "CountryCode": "IN",
                    "PostalCode": str(self._rng.randint(100000, 999999)),
                },
                "IsBusinessOrder": self._rng.random() < 0.10,
                "IsPrime": is_prime,
                "IsGlobalExpressEnabled": False,
                "IsPremiumOrder": False,
                "IsSoldByAB": False,
                "IsISPU": False,
                "IsReplacementOrder": False,
                "EarliestShipDate": earliest_ship.isoformat() + "Z",
                "LatestShipDate": latest_ship.isoformat() + "Z",
                "EarliestDeliveryDate": earliest_delivery.isoformat() + "Z",
                "LatestDeliveryDate": latest_delivery.isoformat() + "Z",
                "ElectronicInvoiceStatus": "NotRequired",
                "_mock_items": items_for_order,
            }

            if fulfillment == FulfillmentChannel.MFN:
                easyship = self._rng.choice(EASYSHIP_STATUSES)
                if easyship:
                    order["EasyShipShipmentStatus"] = easyship

            orders.append(order)

        return orders

    def get_order_items(self, order_id: str, _mock_items: list[dict] | None = None) -> list[dict]:
        items = _mock_items or self._rng.sample(PRODUCTS, self._rng.randint(1, 3))
        result = []
        for idx, product in enumerate(items):
            qty = self._rng.randint(1, 3)
            price = product["price"] * (1 + self._rng.uniform(-0.1, 0.1))
            tax = round(price * 0.18, 2)  # 18% GST
            discount = round(price * self._rng.choice([0, 0, 0.05, 0.10, 0.15]), 2)
            shipping_price = self._rng.choice([0, 0, 0, 40, 60])
            shipping_tax = round(shipping_price * 0.18, 2)
            is_cod = self._rng.random() < 0.20
            qty_shipped = qty if self._rng.random() > 0.15 else 0

            item = {
                "OrderItemId": f"{order_id}-{idx + 1:02d}",
                "ASIN": product["asin"],
                "SellerSKU": product["sku"],
                "Title": product["name"],
                "QuantityOrdered": qty,
                "QuantityShipped": qty_shipped,
                "ItemPrice": _money(price * qty),
                "ItemTax": _money(tax * qty),
                "ShippingPrice": _money(shipping_price),
                "ShippingTax": _money(shipping_tax),
                "ShippingDiscount": _money(0),
                "ShippingDiscountTax": _money(0),
                "PromotionDiscount": _money(discount * qty),
                "PromotionDiscountTax": _money(round(discount * qty * 0.18, 2)),
                "PromotionIds": [],
                "ConditionId": "New",
                "ConditionSubtypeId": "New",
                "IsGift": False,
                "IsTransparency": False,
                "ProductInfo": {"NumberOfItems": str(qty)},
            }

            # COD fields — common in India
            if is_cod:
                cod_fee = self._rng.choice([20, 30, 50])
                item["CODFee"] = _money(cod_fee)
                item["CODFeeDiscount"] = _money(0)

            result.append(item)
        return result

    def get_inventory_summaries(self) -> list[dict]:
        summaries = []
        for product in PRODUCTS:
            fulfillable = self._rng.randint(0, 200)
            inbound_working = self._rng.randint(0, 30)
            inbound_shipped = self._rng.randint(0, 20)
            inbound_receiving = self._rng.randint(0, 10)
            pending_customer = self._rng.randint(0, 15)
            pending_transship = self._rng.randint(0, 5)
            fc_processing = self._rng.randint(0, 3)
            total_reserved = pending_customer + pending_transship + fc_processing
            customer_damaged = self._rng.randint(0, 2)
            warehouse_damaged = self._rng.randint(0, 1)
            defective = self._rng.randint(0, 2)
            expired = 0
            total_unfulfillable = customer_damaged + warehouse_damaged + defective + expired
            total = fulfillable + inbound_working + inbound_shipped + total_reserved + total_unfulfillable

            last_updated = datetime.utcnow() - timedelta(hours=self._rng.randint(1, 72))

            summaries.append({
                "asin": product["asin"],
                "fnSku": f"X00{product['asin'][3:]}",
                "sellerSku": product["sku"],
                "condition": "NewItem",
                "productName": product["name"],
                "totalQuantity": total,
                "lastUpdatedTime": last_updated.isoformat() + "Z",
                "stores": [],
                "inventoryDetails": {
                    "fulfillableQuantity": fulfillable,
                    "inboundWorkingQuantity": inbound_working,
                    "inboundShippedQuantity": inbound_shipped,
                    "inboundReceivingQuantity": inbound_receiving,
                    "reservedQuantity": {
                        "totalReservedQuantity": total_reserved,
                        "pendingCustomerOrderQuantity": pending_customer,
                        "pendingTransshipmentQuantity": pending_transship,
                        "fcProcessingQuantity": fc_processing,
                    },
                    "researchingQuantity": {
                        "totalResearchingQuantity": 0,
                        "researchingQuantityBreakdown": [],
                    },
                    "unfulfillableQuantity": {
                        "totalUnfulfillableQuantity": total_unfulfillable,
                        "customerDamagedQuantity": customer_damaged,
                        "warehouseDamagedQuantity": warehouse_damaged,
                        "distributorDamagedQuantity": 0,
                        "carrierDamagedQuantity": 0,
                        "defectiveQuantity": defective,
                        "expiredQuantity": expired,
                    },
                },
            })
        return summaries

    def get_competitive_pricing(self, asin_list: list[str] | None = None) -> list[dict]:
        """Returns flattened pricing — same shape as AmazonConnector output."""
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
