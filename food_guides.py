"""Best and worst foods for this client's medical / scan pattern."""

# Whole-food candidates. Ranked later by the client's flags.
CANDIDATES = [
    ('Wild salmon', ['antiinflam', 'omega', 'protein']),
    ('Sardines', ['antiinflam', 'omega', 'protein']),
    ('Anchovies', ['omega', 'protein']),
    ('Pasture eggs', ['protein', 'nutrient']),
    ('Grass-fed beef', ['protein', 'iron']),
    ('Chicken thighs', ['protein']),
    ('Turkey', ['protein']),
    ('Lamb', ['protein', 'iron']),
    ('Liver occasional', ['iron', 'nutrient']),
    ('Bone broth', ['gut', 'mineral']),
    ('Blueberries', ['polyphenol', 'lowsugar']),
    ('Raspberries', ['fiber', 'lowsugar']),
    ('Blackberries', ['fiber', 'lowsugar']),
    ('Strawberries', ['polyphenol']),
    ('Lemons', ['liver', 'lowsugar']),
    ('Limes', ['liver', 'lowsugar']),
    ('Avocado', ['fat', 'gut']),
    ('Olives', ['fat', 'antiinflam']),
    ('Extra-virgin olive oil', ['fat', 'antiinflam']),
    ('Avocado oil', ['fat']),
    ('Coconut oil', ['fat']),
    ('Grass-fed ghee', ['fat', 'dairy']),
    ('Spinach', ['green', 'mineral']),
    ('Kale', ['green']),
    ('Arugula', ['green']),
    ('Broccoli', ['green', 'liver']),
    ('Cauliflower', ['green', 'gut']),
    ('Brussels sprouts', ['green', 'liver']),
    ('Cabbage', ['gut', 'green']),
    ('Bok choy', ['green']),
    ('Asparagus', ['liver', 'green']),
    ('Zucchini', ['gut', 'lowsugar']),
    ('Cucumber', ['gut', 'lowsugar']),
    ('Celery', ['lowsugar']),
    ('Romaine', ['green']),
    ('Bell peppers', ['polyphenol']),
    ('Tomatoes', ['polyphenol']),
    ('Carrots', ['fiber']),
    ('Beets', ['liver']),
    ('Sweet potato', ['carb']),
    ('Winter squash', ['carb']),
    ('Garlic', ['immune', 'microbe']),
    ('Onion', ['immune']),
    ('Ginger', ['gut', 'antiinflam']),
    ('Turmeric root', ['antiinflam', 'liver']),
    ('Parsley', ['green']),
    ('Cilantro', ['detox']),
    ('Basil', ['herb']),
    ('Rosemary', ['herb']),
    ('Thyme', ['herb', 'microbe']),
    ('Sauerkraut live', ['gut', 'ferment']),
    ('Kimchi if tolerated', ['gut', 'ferment']),
    ('Coconut yogurt unsweetened', ['gut', 'dairyfree']),
    ('Almonds', ['fat', 'snack']),
    ('Macadamia nuts', ['fat']),
    ('Walnuts', ['omega']),
    ('Pecans', ['fat']),
    ('Chia seeds', ['fiber', 'omega']),
    ('Flaxseed', ['fiber', 'omega']),
    ('Pumpkin seeds', ['mineral']),
    ('Hemp seeds', ['protein']),
    ('Cod', ['protein']),
    ('Halibut', ['protein']),
    ('Trout', ['omega']),
    ('Mussels', ['mineral']),
    ('Oysters', ['mineral', 'zinc']),
    ('Shrimp', ['protein']),
    ('White rice if gut calm', ['carb', 'gutsoft']),
    ('Quinoa', ['carb']),
    ('Buckwheat', ['carb', 'glutenfree']),
    ('Lentils', ['fiber']),
    ('Chickpeas', ['fiber']),
    ('Black beans', ['fiber']),
    ('Green beans', ['green']),
    ('Peas', ['fiber']),
    ('Mushrooms', ['immune']),
    ('Seaweed', ['mineral']),
    ('Green tea', ['polyphenol']),
    ('Ginger tea', ['gut']),
    ('Chamomile tea', ['stress']),
    ('Sparkling water', ['drink']),
    ('Mineral water', ['drink']),
    ('Dark chocolate 85', ['polyphenol', 'sugar']),
    ('Apple', ['fiber']),
    ('Pear', ['fiber']),
    ('Kiwi', ['fiber']),
    ('Grapefruit', ['liver']),
    ('Pomegranate', ['polyphenol']),
    ('Guacamole', ['fat']),
    ('Salsa no sugar', ['lowsugar']),
    ('Mustard', ['condiment']),
    ('Broth-based soup', ['gut']),
    ('Cucumber salad', ['lowsugar']),
    ('Olive oil vinaigrette', ['fat']),
    ('Herbs fresh', ['herb']),
    ('Fermented pickles unsweetened', ['gut']),
    ('Plain meat + vegetables', ['protein', 'green']),
    ('Sardines in olive oil', ['omega']),
    ('Bone-in poultry', ['protein']),
]

WORST = [
    ('Soda', ['sugar', 'candida']),
    ('Diet soda', ['additive']),
    ('Energy drinks', ['sugar', 'additive']),
    ('Sweet tea bottled', ['sugar']),
    ('Fruit juice cocktail', ['sugar', 'candida']),
    ('Candy', ['sugar', 'candida']),
    ('Gummy candy', ['sugar']),
    ('Milk chocolate', ['sugar', 'dairy']),
    ('Frosted cereal', ['sugar', 'gluten']),
    ('Corn Pops sugary cereal', ['sugar', 'gluten']),
    ('Toaster pastry', ['sugar', 'gluten']),
    ('Honey bun', ['sugar', 'gluten']),
    ('Donut', ['sugar', 'gluten']),
    ('Cupcake', ['sugar', 'gluten']),
    ('Packaged cookie', ['sugar', 'gluten']),
    ('Snack cake', ['sugar']),
    ('Ice cream sugary', ['sugar', 'dairy']),
    ('Pudding cup', ['sugar', 'dairy']),
    ('Fast-food fries', ['processed', 'oil']),
    ('Fast-food burger combo', ['processed']),
    ('Chicken nuggets processed', ['processed']),
    ('Hot dog', ['processed']),
    ('Bologna', ['processed']),
    ('Lunchables', ['processed', 'dairy']),
    ('Nacho cheese sauce', ['dairy', 'processed']),
    ('Instant ramen', ['processed', 'gluten']),
    ('Cup noodles', ['processed']),
    ('Boxed mac and cheese', ['dairy', 'gluten']),
    ('Canned pasta rings', ['gluten', 'processed']),
    ('Frozen pizza standard', ['gluten', 'dairy']),
    ('White bread packaged', ['gluten']),
    ('Hot dog buns', ['gluten']),
    ('Crescent dough', ['gluten']),
    ('Margarine sticks', ['oil']),
    ('Shortening', ['oil']),
    ('Corn syrup foods', ['sugar', 'candida']),
    ('Slushies', ['sugar']),
    ('Sweetened coffee drinks', ['sugar', 'dairy']),
    ('Flavored latte syrup', ['sugar']),
    ('Sweet creamers', ['dairy', 'sugar']),
    ('Chocolate milk', ['dairy', 'sugar']),
    ('Breakfast pastry', ['gluten', 'sugar']),
    ('Candy-like granola bar', ['sugar']),
    ('Kids yogurt tube', ['dairy', 'sugar']),
    ('Fruit snacks', ['sugar']),
    ('Applesauce pouch sugary', ['sugar']),
    ('Ketchup heavy sugar', ['sugar']),
    ('BBQ sauce candy', ['sugar']),
    ('Ranch bottled', ['dairy', 'oil']),
    ('Cheese dip jar', ['dairy']),
    ('Microwave popcorn extra butter', ['oil', 'dairy']),
    ('Cheese puffs', ['processed']),
    ('Flaming chip snacks', ['processed']),
    ('Chocolate cereal', ['sugar', 'gluten']),
    ('Instant oatmeal maple brown sugar', ['sugar', 'gluten']),
    ('Pancake syrup', ['sugar']),
    ('Whipped topping tub', ['processed']),
    ('Cake mix', ['gluten', 'sugar']),
    ('Sweet wine coolers', ['sugar', 'alcohol', 'candida']),
    ('Hard soda', ['sugar', 'alcohol']),
    ('Cocktail mixer syrup', ['sugar']),
    ('Corn dog', ['gluten', 'processed']),
    ('Processed American slices', ['dairy', 'processed']),
    ('Fish sticks standard', ['processed']),
    ('Chicken patty freezer', ['processed']),
    ('Breakfast sandwich freezer', ['processed', 'gluten']),
    ('Taquito freezer', ['processed']),
    ('Bagel bite freezer', ['gluten', 'processed']),
    ('Beer', ['gluten', 'alcohol', 'candida']),
    ('Wheat pasta heavy sauce', ['gluten']),
    ('Cow milk sweetened', ['dairy']),
    ('Milkshake', ['dairy', 'sugar']),
    ('Cheese sauce nachos', ['dairy']),
    ('Fruit juice', ['sugar', 'candida']),
    ('Dessert wine', ['alcohol', 'sugar']),
    ('Sweet yogurt', ['dairy', 'sugar', 'candida']),
    ('Ultra-processed pizza rolls', ['processed']),
    ('Canned chili fillers', ['processed']),
    ('Pretzel packaged', ['gluten']),
    ('Crackers ultra-processed', ['gluten']),
    ('Cereal marshmallow', ['sugar']),
    ('Toaster strudel', ['gluten', 'sugar']),
    ('Canned cheese spray', ['dairy']),
    ('Brownie mix', ['gluten', 'sugar']),
    ('Frozen honey bun', ['gluten', 'sugar']),
    ('Malt liquor', ['alcohol']),
    ('Sugary protein shake', ['sugar']),
    ('Candy coating protein bar', ['sugar']),
    ('Imitation crab sticky', ['processed']),
    ('Deep-fried fair food', ['oil', 'processed']),
    ('Energy shot', ['additive']),
    ('Bottled margarita mix', ['sugar', 'alcohol']),
    ('Iced honey buns', ['sugar', 'gluten']),
    ('Shelf-stable frosting', ['sugar']),
    ('Sweetened condensed milk dessert', ['dairy', 'sugar']),
]


def _norm(text):
    return ''.join(ch for ch in (text or '').lower() if ch.isalnum() or ch.isspace())


def _scanned_set(names):
    out = set()
    for name in names or []:
        n = _norm(name)
        if n:
            out.add(n)
            out.update(n.split())
    return out


def _already_scanned(food_name, scanned):
    n = _norm(food_name)
    if not n or not scanned:
        return False
    if n in scanned:
        return True
    for token in n.split():
        if len(token) > 4 and token in scanned:
            return True
    return False


def _rank_best(item, flags, raw):
    name, tags = item
    score = 50
    raw = (raw or '').lower()
    flags = set(flags or [])
    if 'antiinflam' in tags or 'omega' in tags:
        score += 12
    if 'green' in tags or 'fiber' in tags:
        score += 8
    if 'gut' in tags and ('gut' in flags or 'digest' in raw or 'intestin' in raw):
        score += 16
    if 'liver' in tags and ('liver' in flags or 'detox' in raw or 'liver' in raw):
        score += 14
    if 'stress' in tags and ('stress' in flags or 'nervous' in raw):
        score += 10
    if 'microbe' in tags and ('candida' in flags or 'immune' in flags):
        score += 10
    if 'dairy' in tags and 'dairy' in flags:
        score -= 40
    if 'sugar' in tags and 'candida' in flags:
        score -= 30
    if 'ferment' in tags and 'candida' in flags:
        score -= 12
    if 'gluten' in ''.join(tags) and 'gluten' in flags:
        score -= 20
    return score


def _rank_worst(item, flags, raw):
    name, tags = item
    score = 40
    flags = set(flags or [])
    raw = (raw or '').lower()
    if 'sugar' in tags:
        score += 12
    if 'processed' in tags:
        score += 10
    if 'candida' in tags and 'candida' in flags:
        score += 22
    if 'dairy' in tags and 'dairy' in flags:
        score += 20
    if 'gluten' in tags and 'gluten' in flags:
        score += 20
    if 'alcohol' in tags and ('liver' in flags or 'liver' in raw):
        score += 16
    if 'gut' in flags and 'processed' in tags:
        score += 8
    return score


def lists_for_flags(flags, scanned_names=None, raw_text=''):
    scanned = _scanned_set(scanned_names)
    best = []
    for item in CANDIDATES:
        if _already_scanned(item[0], scanned):
            continue
        best.append(( _rank_best(item, flags, raw_text), item[0] ))
    worst = []
    for item in WORST:
        if _already_scanned(item[0], scanned):
            continue
        worst.append(( _rank_worst(item, flags, raw_text), item[0] ))
    best.sort(reverse=True)
    worst.sort(reverse=True)
    return [n for _, n in best[:100]], [n for _, n in worst[:100]]
