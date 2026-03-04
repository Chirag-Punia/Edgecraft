"""Real Amazon SP-API connector using python-amazon-sp-api library.

The library handles LWA token refresh and rate-limit retries automatically.
Marketplace: Amazon.in (India, EU region endpoint).
"""
from datetime import datetime
from sp_api.api import Orders, Inventories, Products
from sp_api.base import Marketplaces


class AmazonConnector:
    """Wraps SP-API calls with the same interface as MockAmazonConnector."""

    def __init__(self, credentials: dict):
        self._creds = {
            "refresh_token": credentials["refresh_token"],
            "lwa_app_id": credentials["lwa_app_id"],
            "lwa_client_secret": credentials["lwa_client_secret"],
            "aws_access_key": credentials.get("aws_access_key", ""),
            "aws_secret_key": credentials.get("aws_secret_key", ""),
            "role_arn": credentials.get("role_arn", ""),
        }
        self._marketplace = Marketplaces.IN

    def _api_kwargs(self) -> dict:
        return {"credentials": self._creds, "marketplace": self._marketplace}

    def get_orders(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict]:
        orders_api = Orders(**self._api_kwargs())
        all_orders = []
        kwargs = {"MarketplaceIds": [self._marketplace.marketplace_id]}
        if created_after:
            kwargs["CreatedAfter"] = created_after.isoformat()
        if created_before:
            kwargs["CreatedBefore"] = created_before.isoformat()

        response = orders_api.get_orders(**kwargs)
        all_orders.extend(response.payload.get("Orders", []))

        # Handle pagination
        while response.next_token:
            response = orders_api.get_orders(NextToken=response.next_token, **kwargs)
            all_orders.extend(response.payload.get("Orders", []))

        return all_orders

    def get_order_items(self, order_id: str, _mock_items: list[dict] | None = None) -> list[dict]:
        orders_api = Orders(**self._api_kwargs())
        response = orders_api.get_order_items(order_id)
        return response.payload.get("OrderItems", [])

    def get_inventory_summaries(self) -> list[dict]:
        inventory_api = Inventories(**self._api_kwargs())
        all_summaries = []
        response = inventory_api.get_inventory_summary_marketplace(
            granularityType="Marketplace",
            granularityId=self._marketplace.marketplace_id,
            marketplaceIds=[self._marketplace.marketplace_id],
        )
        all_summaries.extend(response.payload.get("inventorySummaries", []))

        while response.next_token:
            response = inventory_api.get_inventory_summary_marketplace(
                granularityType="Marketplace",
                granularityId=self._marketplace.marketplace_id,
                marketplaceIds=[self._marketplace.marketplace_id],
                nextToken=response.next_token,
            )
            all_summaries.extend(response.payload.get("inventorySummaries", []))

        return all_summaries

    def get_competitive_pricing(self, asin_list: list[str] | None = None) -> list[dict]:
        if not asin_list:
            return []
        products_api = Products(**self._api_kwargs())
        # SP-API accepts up to 20 ASINs per call
        results = []
        for i in range(0, len(asin_list), 20):
            batch = asin_list[i:i + 20]
            response = products_api.get_competitive_pricing_for_asins(batch)
            for item in response.payload:
                product = item.get("Product", {})
                offers = product.get("CompetitivePricing", {}).get("CompetitivePrices", [])
                your_price = None
                buybox_price = None
                for offer in offers:
                    price_obj = offer.get("Price", {})
                    landed = price_obj.get("LandedPrice", {}).get("Amount")
                    if offer.get("belongsToRequester"):
                        your_price = landed
                    if offer.get("CompetitivePriceId") == "1":  # Buy Box
                        buybox_price = landed
                results.append({
                    "ASIN": item.get("ASIN"),
                    "SellerSKU": item.get("SellerSKU", ""),
                    "YourPrice": your_price,
                    "LandedPrice": your_price,
                    "BuyBoxPrice": buybox_price,
                    "LowestPrice": None,
                    "IsBuyBoxWinner": your_price == buybox_price if your_price and buybox_price else False,
                })
        return results
