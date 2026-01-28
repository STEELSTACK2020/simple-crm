"""
Add Steelstack products to the product catalog.
"""

from database import add_product, get_all_products

# Steelstack Product Catalog
steelstack_products = [
    # STACK MAX Products (5' x 10' Sheet Capacity)
    {
        "name": "6FT 5' x 10' STACK MAX - (ASSEMBLED)",
        "sku": "SMAX-6FT-5X10-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 142.125", Depth: 72.25", and Height: 81.375"
Weight Capacity: 5,000 lbs. per cassette.
Dry Weight: 5'x10' CASSETTE = 780 lbs. | STACK = ~2,000 lbs.
Accepted Sheet Sizes: Any Sheet Size up to 5' x 10'.
Configuration: Nine Cassettes: Total Capacity 45,000 lbs.""",
        "price": 16995.00
    },
    {
        "name": "8FT 5' x 10' STACK MAX - (ASSEMBLED)",
        "sku": "SMAX-8FT-5X10-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 142.125", Depth: 72.25", and Height: 97.375"
Weight Capacity: 5,000 lbs. per cassette.
Dry Weight: 5'x10' CASSETTE = 780 lbs. | STACK = ~2,400 lbs.
Accepted Sheet Sizes: Any Sheet Size up to 5' x 10'.
Configuration: Eleven Cassettes: Total Capacity 55,000 lbs.""",
        "price": 19995.00
    },
    {
        "name": "10FT 5' x 10' STACK MAX - (ASSEMBLED)",
        "sku": "SMAX-10FT-5X10-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 142.125", Depth: 72.25", and Height: 113.375"
Weight Capacity: 5,000 lbs. per cassette.
Dry Weight: 5'x10' CASSETTE = 780 lbs. | STACK = ~2,800 lbs.
Accepted Sheet Sizes: Any Sheet Size up to 5' x 10'.
Configuration: Thirteen Cassettes: Total Capacity 65,000 lbs.""",
        "price": 22995.00
    },

    # STACK MAX Products (4' x 8' Sheet Capacity)
    {
        "name": "6FT 4' x 8' STACK MAX - (ASSEMBLED)",
        "sku": "SMAX-6FT-4X8-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 114.125", Depth: 60.25", and Height: 81.375"
Weight Capacity: 5,000 lbs. per cassette.
Dry Weight: 4'x8' CASSETTE = 580 lbs. | STACK = ~1,600 lbs.
Accepted Sheet Sizes: Any Sheet Size up to 4' x 8'.
Configuration: Nine Cassettes: Total Capacity 45,000 lbs.""",
        "price": 13995.00
    },
    {
        "name": "8FT 4' x 8' STACK MAX - (ASSEMBLED)",
        "sku": "SMAX-8FT-4X8-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 114.125", Depth: 60.25", and Height: 97.375"
Weight Capacity: 5,000 lbs. per cassette.
Dry Weight: 4'x8' CASSETTE = 580 lbs. | STACK = ~2,000 lbs.
Accepted Sheet Sizes: Any Sheet Size up to 4' x 8'.
Configuration: Eleven Cassettes: Total Capacity 55,000 lbs.""",
        "price": 16995.00
    },
    {
        "name": "10FT 4' x 8' STACK MAX - (ASSEMBLED)",
        "sku": "SMAX-10FT-4X8-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 114.125", Depth: 60.25", and Height: 113.375"
Weight Capacity: 5,000 lbs. per cassette.
Dry Weight: 4'x8' CASSETTE = 580 lbs. | STACK = ~2,400 lbs.
Accepted Sheet Sizes: Any Sheet Size up to 4' x 8'.
Configuration: Thirteen Cassettes: Total Capacity 65,000 lbs.""",
        "price": 19995.00
    },

    # STACK PRO Products (5' x 10' Sheet Capacity)
    {
        "name": "6FT 5' x 10' STACK PRO - (ASSEMBLED)",
        "sku": "SPRO-6FT-5X10-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 142.125", Depth: 72.25", and Height: 81.375"
Weight Capacity: 3,000 lbs. per cassette.
Accepted Sheet Sizes: Any Sheet Size up to 5' x 10'.
Configuration: Nine Cassettes: Total Capacity 27,000 lbs.""",
        "price": 12995.00
    },
    {
        "name": "8FT 5' x 10' STACK PRO - (ASSEMBLED)",
        "sku": "SPRO-8FT-5X10-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 142.125", Depth: 72.25", and Height: 97.375"
Weight Capacity: 3,000 lbs. per cassette.
Accepted Sheet Sizes: Any Sheet Size up to 5' x 10'.
Configuration: Eleven Cassettes: Total Capacity 33,000 lbs.""",
        "price": 15995.00
    },
    {
        "name": "10FT 5' x 10' STACK PRO - (ASSEMBLED)",
        "sku": "SPRO-10FT-5X10-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 142.125", Depth: 72.25", and Height: 113.375"
Weight Capacity: 3,000 lbs. per cassette.
Accepted Sheet Sizes: Any Sheet Size up to 5' x 10'.
Configuration: Thirteen Cassettes: Total Capacity 39,000 lbs.""",
        "price": 18995.00
    },

    # STACK PRO Products (4' x 8' Sheet Capacity)
    {
        "name": "6FT 4' x 8' STACK PRO - (ASSEMBLED)",
        "sku": "SPRO-6FT-4X8-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 114.125", Depth: 60.25", and Height: 81.375"
Weight Capacity: 3,000 lbs. per cassette.
Accepted Sheet Sizes: Any Sheet Size up to 4' x 8'.
Configuration: Nine Cassettes: Total Capacity 27,000 lbs.""",
        "price": 9995.00
    },
    {
        "name": "8FT 4' x 8' STACK PRO - (ASSEMBLED)",
        "sku": "SPRO-8FT-4X8-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 114.125", Depth: 60.25", and Height: 97.375"
Weight Capacity: 3,000 lbs. per cassette.
Accepted Sheet Sizes: Any Sheet Size up to 4' x 8'.
Configuration: Eleven Cassettes: Total Capacity 33,000 lbs.""",
        "price": 12995.00
    },
    {
        "name": "10FT 4' x 8' STACK PRO - (ASSEMBLED)",
        "sku": "SPRO-10FT-4X8-A",
        "description": """Absolute Dimensions (Single Unit):
Width: 114.125", Depth: 60.25", and Height: 113.375"
Weight Capacity: 3,000 lbs. per cassette.
Accepted Sheet Sizes: Any Sheet Size up to 4' x 8'.
Configuration: Thirteen Cassettes: Total Capacity 39,000 lbs.""",
        "price": 15995.00
    },

    # Additional Cassettes (Add-ons)
    {
        "name": "Additional 5' x 10' Cassette",
        "sku": "CASS-5X10",
        "description": "Additional cassette for 5' x 10' STACK systems. Weight Capacity: 5,000 lbs. Dry Weight: 780 lbs.",
        "price": 1995.00
    },
    {
        "name": "Additional 4' x 8' Cassette",
        "sku": "CASS-4X8",
        "description": "Additional cassette for 4' x 8' STACK systems. Weight Capacity: 5,000 lbs. Dry Weight: 580 lbs.",
        "price": 1595.00
    },

    # Accessories
    {
        "name": "Forklift Loading Platform",
        "sku": "ACC-FLP",
        "description": "Forklift loading platform for easy cassette loading/unloading.",
        "price": 2495.00
    },
    {
        "name": "Sheet Separator Kit",
        "sku": "ACC-SSK",
        "description": "Sheet separator kit for organizing materials within cassettes.",
        "price": 495.00
    },
]


def add_steelstack_products():
    """Add all Steelstack products to the database."""
    existing = get_all_products()
    existing_skus = {p.get('sku') for p in existing if p.get('sku')}

    added = 0
    skipped = 0

    for product in steelstack_products:
        if product['sku'] in existing_skus:
            print(f"  Skipped (exists): {product['name']}")
            skipped += 1
            continue

        result = add_product(
            name=product['name'],
            sku=product['sku'],
            description=product['description'],
            price=product['price']
        )

        if result.get('success'):
            print(f"  Added: {product['name']} - ${product['price']:,.2f}")
            added += 1
        else:
            print(f"  Failed: {product['name']} - {result.get('error')}")

    print(f"\nSummary: {added} added, {skipped} skipped")
    return added


if __name__ == "__main__":
    print("Adding Steelstack products to catalog...\n")
    add_steelstack_products()

    print("\nAll products in catalog:")
    for p in get_all_products():
        print(f"  - {p['name']} (${p.get('price', 0):,.2f})")
