"""Embedded 1200x630 JPEG for /static/og-food-scanner.png."""
try:
    from og_food_p1 import P1
    from og_food_p2 import P2
    from og_food_p3 import P3
    from og_food_p4 import P4
    OG_FOOD_JPG_B64 = "".join((P1, P2, P3, P4))
except Exception:
    OG_FOOD_JPG_B64 = ""
