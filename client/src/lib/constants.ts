export const BUSINESS_TYPES = [
  "Manufacturer",
  "Distributor",
  "Retailer",
  "D2C Brand",
  "Wholesaler",
  "Other",
] as const;

export const CATEGORIES = [
  "Electronics",
  "Fashion & Apparel",
  "Home & Kitchen",
  "Beauty & Personal Care",
  "Food & Beverages",
  "Health & Wellness",
  "Sports & Fitness",
  "Books & Stationery",
  "Toys & Games",
  "Automotive",
  "Other",
] as const;

export const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
  "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
  "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
  "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
  "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Delhi", "Jammu & Kashmir", "Ladakh", "Puducherry",
  "Chandigarh", "Andaman & Nicobar Islands", "Dadra & Nagar Haveli",
  "Daman & Diu", "Lakshadweep",
] as const;

export const MARKETPLACES = [
  { id: "amazon", name: "Amazon.in", description: "Connect your Amazon Seller Central account", color: "#FF9900" },
  { id: "flipkart", name: "Flipkart", description: "Connect your Flipkart Seller Hub", color: "#2874F0" },
  { id: "shopify", name: "Shopify", description: "Connect your Shopify store", color: "#96BF48" },
  { id: "facebook", name: "Facebook Marketplace", description: "Connect your Facebook Commerce account", color: "#1877F2" },
] as const;
