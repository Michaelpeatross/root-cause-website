"""Whole-food-v2 scoring tests. Run: python -m pytest tests/test_food_score_v2.py -q"""
import json, os, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from food_scanner import score_product, product_from_label_extract, normalize_off_product  # noqa: E402
from food_score_v2 import split_ingredients, detect_markers  # noqa: E402
from meal_photo import build_plate_product  # noqa: E402


def P(name, ingredients='', nova=None, additives=(), **nutrients):
    return {'name': name, 'ingredients': ingredients, 'nova': nova, 'additives': list(additives),
            'labels': [], 'categories': '', 'nutrients': nutrients}


# name, product, (min, max)
TABLE = [
    ('Fresh apple (photo, no label)', P('Apple'), (100, 100)),
    ('Banana (sugar 12 g, whole fruit)', P('Bananas', sugars=12.2, fiber=2.6), (100, 100)),
    ('Large eggs', P('Large brown eggs', 'eggs', nova=1, sat_fat=3.1, protein=12.6), (100, 100)),
    ('Wild salmon fillet', P('Wild Alaskan salmon', 'wild salmon', protein=20), (100, 100)),
    ('Raw almonds (sat fat 3.8, fat 50)', P('Raw almonds', 'almonds', fat=50, sat_fat=3.8, protein=21, fiber=12), (100, 100)),
    ('Old-fashioned rolled oats', P('Old fashioned oats', '100% whole grain rolled oats'), (100, 100)),
    ('Dry black beans', P('Black beans', 'black beans'), (100, 100)),
    ('Frozen broccoli', P('Frozen broccoli florets', 'broccoli'), (100, 100)),
    ('Plain Greek yogurt (milk + cultures)', P('Plain Greek yogurt', 'cultured pasteurized nonfat milk, live active cultures'), (90, 100)),
    ('Canned beans: beans, water, salt', P('Black beans', 'black beans, water, sea salt', salt=0.6), (85, 96)),
    ('Roasted salted almonds', P('Roasted salted almonds', 'almonds, sea salt', salt=0.9), (85, 96)),
    ('Extra virgin olive oil', P('Extra virgin olive oil', 'extra virgin olive oil', nova=2), (70, 80)),
    ('Raw honey', P('Raw honey', 'raw honey', nova=2, sugars=82), (55, 70)),
    ('Sourdough: flour, water, salt', P('Sourdough bread', 'unbleached wheat flour, water, salt'), (55, 75)),
    ('Kettle chips: potatoes, sunflower oil, salt', P('Kettle potato chips', 'potatoes, sunflower oil, salt', nova=3, salt=1.2, sat_fat=3), (40, 55)),
    ('Granola w/ cane sugar + canola oil', P('Granola', 'whole grain oats, cane sugar, canola oil, honey, rice flour, salt', sugars=24), (40, 45)),
    ('Coca-Cola', P('Coca-Cola', 'carbonated water, high fructose corn syrup, caramel color, phosphoric acid, natural flavors, caffeine', nova=4, sugars=10.6), (1, 20)),
    ('Pringles-style crisps', P('Original potato crisps', 'dehydrated potatoes, vegetable oil (corn, cottonseed, high oleic soybean oil), rice flour, wheat starch, maltodextrin, mono- and diglycerides, salt, dextrose', nova=4, salt=1.3), (1, 25)),
    ('Diet soda (sweeteners, colors)', P('Diet cola', 'carbonated water, caramel color, aspartame, phosphoric acid, potassium benzoate, natural flavors, citric acid, caffeine', nova=4), (1, 20)),
    ('High-protein bar (isolates, sucralose)', P('Protein bar', 'milk protein isolate, soluble corn fiber, almonds, erythritol, natural flavors, sucralose, sunflower lecithin', nova=4, protein=30, fiber=10, sugars=1), (1, 35)),
    ('Cheddar: milk, cultures, salt, enzymes', P('Cheddar cheese', 'pasteurized milk, cheese cultures, salt, enzymes'), (60, 79)),
    ('Hot dog (nitrite)', P('Beef franks', 'beef, water, salt, corn syrup, sodium lactate, natural flavors, sodium nitrite', nova=4, salt=2.3), (1, 15)),
]


@pytest.mark.parametrize('label,product,rng', TABLE, ids=[t[0] for t in TABLE])
def test_example_table(label, product, rng):
    r = score_product(product)
    assert rng[0] <= r['score'] <= rng[1], (label, r['score'], r['processing_tier'], r['reasons'])


def test_whole_foods_beat_ultra_processed_even_with_better_macros():
    bar = score_product(P('Protein bar', 'milk protein isolate, almonds, sucralose, natural flavors', protein=30, fiber=12, sugars=1))
    dates = score_product(P('Medjool dates', 'dates', sugars=66))
    assert dates['score'] >= 90 and bar['score'] <= 39


def test_natural_sugar_and_fat_not_penalized_for_whole_foods():
    assert score_product(P('Dates', 'dates', sugars=66))['score'] == 100
    assert score_product(P('Walnuts', 'walnuts', fat=65, sat_fat=6.1))['score'] == 100


def test_ultra_processed_capped_below_40_regardless_of_macros():
    r = score_product(P('Fortified cereal', 'whole grain oats, sugar, modified corn starch, natural flavor, tocopherols', nova=4, fiber=10, protein=12, sugars=4))
    assert r['score'] <= 39 and r['processing_tier'] == '4'


def test_benign_additives_do_not_trigger_ultra():
    r = score_product(P('Diced tomatoes', 'tomatoes, tomato juice, citric acid, calcium chloride'))
    assert r['processing_tier'] != '4'


def test_sugar_snap_peas_not_added_sugar():
    r = score_product(P('Sugar snap peas', 'sugar snap peas'))
    assert r['added_sugar'] is False


def test_personal_filter_lowers_score_and_explains():
    r = score_product(P('Whole milk', 'milk', nova=1), personal_flags=['dairy'])
    assert r['score'] < 100 and r['personal_notes'] and 'filter' in r['personal_notes'][0]


def test_unknown_product_is_mid_and_says_so():
    r = score_product(P('Mystery snack'))
    assert r['processing_tier'] == 'unknown' and 30 <= r['score'] <= 75


def test_off_nova_4_respected_when_no_markers_found():
    r = score_product(P('Cheese crackers', 'enriched flour, cheese, oil, salt, paprika', nova=4))
    assert r['score'] <= 39


def test_legacy_keys_present():
    r = score_product(P('Apple'))
    for k in ('score', 'band', 'label', 'color', 'nutrition_score', 'additive_score', 'personal_score', 'additive_hits', 'personal_notes', 'nova'):
        assert k in r


def test_split_ingredients_keeps_sub_lists():
    items = split_ingredients('Ingredients: chocolate (sugar, cocoa butter, soy lecithin), almonds, salt.')
    assert items == ['chocolate (sugar, cocoa butter, soy lecithin)', 'almonds', 'salt']
    assert 'emulsifier (lecithin)' in detect_markers(', '.join(items))


def test_label_photo_of_unpackaged_whole_food():
    prod = product_from_label_extract({'name': 'Avocado', 'ingredients': '', 'whole_food': True, 'has_label': False, 'food_type': 'produce', 'nova_estimate': 1})
    assert score_product(prod)['score'] >= 90


def test_label_photo_with_only_citric_acid_is_not_forced_nova4():
    prod = product_from_label_extract({'name': 'Canned chickpeas', 'ingredients': 'chickpeas, water, salt, calcium chloride', 'additives': ['E509']})
    assert prod['nova'] is None
    assert score_product(prod)['score'] >= 85


def test_plate_whole_food_meal_high_and_fast_food_low():
    good = build_plate_product({'name': 'Salmon plate', 'calories': 550, 'components': [
        {'name': 'grilled salmon', 'processing': 'minimal', 'share': 0.4},
        {'name': 'steamed broccoli', 'processing': 'whole', 'share': 0.3},
        {'name': 'brown rice', 'processing': 'whole', 'share': 0.3}]})
    bad = build_plate_product({'name': 'Burger and fries', 'calories': 1100, 'components': [
        {'name': 'cheeseburger', 'processing': 'ultra', 'share': 0.6},
        {'name': 'french fries', 'processing': 'ultra', 'share': 0.4, 'fried': True}]})
    assert score_product(good)['score'] >= 90
    assert score_product(bad)['score'] <= 25


def test_plate_fallback_without_components():
    prod = build_plate_product({'name': 'Pizza', 'calories': 800, 'ultra_processed': True})
    assert score_product(prod)['score'] <= 30


FIX = os.path.join(HERE, 'fixtures', 'off_products.json')


@pytest.mark.skipif(not os.path.isfile(FIX), reason='no Open Food Facts fixtures')
def test_real_open_food_facts_products():
    data = json.load(open(FIX))
    expect = {'3017620422003': (1, 30), '0038000138416': (1, 25), '5449000000996': (1, 20),
              '0850015600111': (95, 100), '5000306004240': (90, 100)}
    for code, rng in expect.items():
        if code in data:
            r = score_product(normalize_off_product(data[code], code))
            assert rng[0] <= r['score'] <= rng[1], (code, r)


def test_french_banana_variety_line_is_whole_food_not_processed():
    """OFF 3192340348960: one French food plus grade/size words, and nova_group is empty."""
    ingredient = 'Bananes variété Cavendish Cat 1 calibre 14cm mini'
    named = score_product(P('Bananes', ingredient, sugars=11.9, fiber=2.6))
    assert named['processing_tier'] == '1', named
    assert 90 <= named['score'] <= 100, named
    # The ingredient phrase itself is enough, even if the product name is not a food.
    phrase_only = score_product(P('Product', ingredient))
    assert phrase_only['processing_tier'] == '1' and phrase_only['score'] >= 90
    # Grade/origin text with no second ingredient, when the name is the food.
    grade_only = score_product(P('Bananes', 'Cavendish Cat 1 calibre 14cm mini'))
    assert grade_only['processing_tier'] == '1' and grade_only['score'] >= 90


def test_spanish_produce_variety_line_is_whole_food():
    r = score_product(P('Manzanas', 'Manzanas variedad Fuji categoría extra calibre 80'))
    assert r['processing_tier'] == '1' and 90 <= r['score'] <= 100


def test_short_unknown_ingredient_is_not_scored_as_whole_food():
    mystery = score_product(P('Snack bits', 'xqzblend'))
    assert mystery['processing_tier'] != '1' and mystery['score'] < 90
    # A known whole-food name does not rescue a non-food ingredient blob.
    assert score_product(P('Bananes', 'xqzblend'))['processing_tier'] != '1'
    # Descriptor-only text is not a whole food unless the name is one.
    assert score_product(P('Snack', 'mini'))['processing_tier'] != '1'
    # A second ingredient still keeps it out of tier 1.
    assert score_product(P('Bananes', 'bananes, sucre'))['processing_tier'] != '1'
    assert score_product(P('Bananas', 'banana chips'))['score'] < 90
