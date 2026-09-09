"""Curated best/worst grocery lists. Personalized by scan flags."""
TOP_FOODS = [
    'Wild salmon','Sardines','Anchovies','Pasture eggs','Grass-fed beef','Chicken thighs','Turkey','Lamb','Liver (occasional)','Bone broth',
    'Blueberries','Raspberries','Blackberries','Strawberries','Lemons','Limes','Avocado','Olives','Extra-virgin olive oil','Avocado oil',
    'Coconut oil','Grass-fed ghee','Spinach','Kale','Arugula','Broccoli','Cauliflower','Brussels sprouts','Cabbage','Bok choy',
    'Asparagus','Zucchini','Cucumber','Celery','Romaine','Bell peppers','Tomatoes','Carrots','Beets','Sweet potato',
    'Winter squash','Garlic','Onion','Ginger','Turmeric root','Parsley','Cilantro','Basil','Rosemary','Thyme',
    'Sauerkraut (live)','Kimchi (if tolerated)','Coconut yogurt unsweetened','Almonds','Macadamia nuts','Walnuts','Pecans','Chia seeds','Flaxseed','Pumpkin seeds',
    'Hemp seeds','Olive tapenade','Sardines in olive oil','Cod','Halibut','Trout','Mussels','Oysters','Shrimp','Bone-in poultry',
    'White rice (if gut calm)','Quinoa','Buckwheat','Lentils','Chickpeas','Black beans','Green beans','Peas','Mushrooms','Seaweed',
    'Green tea','Ginger tea','Chamomile tea','Sparkling water','Mineral water','Dark chocolate 85%+','Apple','Pear','Kiwi','Grapefruit',
    'Pomegranate','Papaya','Cucumber salad','Olive oil vinaigrette','Guacamole','Salsa no sugar','Mustard','Herbs fresh','Fermented pickles unsweetened','Broth-based soup',
]
LOW_FOODS = [
    'Soda','Diet soda','Energy drinks','Sweet tea bottled','Fruit juice cocktail','Candy','Gummy candy','Milk chocolate','Frosted cereal','Corn Pops / sugary cereal',
    'Toaster pastry','Honey bun','Donut','Cinnamon roll icing','Cupcake','Cookie packaged','Snack cake','Ice cream pint sugary','Frozen dessert bar','Pudding cup',
    'Fast-food fries','Fast-food burger combo','Chicken nuggets processed','Hot dog','Bologna','Lunchables','Nacho cheese sauce','Instant ramen','Cup noodles','Boxed mac and cheese',
    'Canned pasta rings','Frozen pizza standard','White bread packaged','Hot dog buns','Crescent dough','Margarine sticks','Shortening','Corn syrup foods','Slushies','Sweetened coffee drinks',
    'Flavored latte syrup','Sweet creamers','Chocolate milk','Breakfast pastry','Candy-like granola bar','Kids yogurt tube sugar','Fruit snacks','Applesauce pouch sugary','Ketchup heavy sugar','BBQ sauce candy',
    'Ranch bottled','Cheese dip jar','Microwave popcorn extra butter','Cheese puffs','Flaming chip snacks','Iced honey buns','Chocolate cereal','Instant oatmeal maple brown sugar','Pancake syrup','Whipped topping tub',
    'Shelf-stable frosting','Cake mix standard','Sweet wine coolers','Hard soda','Cocktail mixer syrup','Bottled margarita mix','Corn dog','Processed American slices','Fish sticks standard','Chicken patty freezer',
    'Sausage biscuit freezer','Breakfast sandwich freezer','Taquito freezer','Bagel bite freezer','Deep-fried fair food','Imitation crab sticky','Malt liquor','Sugary protein shake','Candy coating protein bar','Ultra-processed pizza rolls',
    'Canned chili fillers','Refried beans additives','Pretzel packaged heavy','Crackers ultra-processed','Cereal marshmallow','Toaster strudel','Canned cheese spray','Brownie mix standard','Sweetened condensed milk dessert','Frozen honey bun',
]

def lists_for_flags(flags):
    flags = set(flags or [])
    top = list(TOP_FOODS)
    low = list(LOW_FOODS)
    if 'dairy' in flags:
        top = [x for x in top if 'ghee' not in x.lower()]
        low = ['Cow milk','Ice cream','Cheese sauce'] + low
    if 'gluten' in flags:
        low = ['Wheat bread','Pasta wheat','Beer'] + low
    if 'candida' in flags:
        top = [x for x in top if 'chocolate' not in x.lower()]
        low = ['Fruit juice','Dessert wine','Sweet yogurt'] + low
    def uniq(seq):
        seen=set(); out=[]
        for item in seq:
            if item not in seen:
                seen.add(item); out.append(item)
        return out
    return uniq(top)[:100], uniq(low)[:100]
