"""Body Overview: group scan markers into body systems with stress levels."""
import re
from html import escape

DEDUCTION_PER_MARKER = 3
BASE_SCORE = 100
MIN_SCORE = 20

STRESS_LEVELS = (
    (91, 'Minor Stress', 'stress-minor'),
    (71, 'Stress', 'stress-moderate'),
    (51, 'Chronic Stress', 'stress-chronic'),
    (31, 'Weakness', 'stress-weakness'),
    (0, 'Chronic Weakness', 'stress-severe'),
)

BODY_SYSTEMS = [
    {
        'id': 'dermal',
        'name': 'Dermal',
        'definition': (
            'Your skin, hair, and outer protective barriers. This system reflects '
            'how your body responds to topical stressors, hydration, and repair.'
        ),
        'keywords': [
            'integumentary', 'dermal', 'skin', 'scalp', 'hair', 'epiderm', 'collagen',
            'cutaneous', 'sweat', 'sebaceous',
        ],
    },
    {
        'id': 'nervous',
        'name': 'Nervous',
        'definition': (
            'Your brain, nerves, and communication pathways — including stress response, '
            'focus, sleep signals, and coordination between body systems.'
        ),
        'keywords': [
            'nervous', 'nerve', 'brain', 'neural', 'pituitary', 'pineal', 'governing vessel',
            'peripheral', 'central nervous', 'hypothalamus', 'orexin', 'autonomic',
            'cerebral', 'neurolog',
        ],
    },
    {
        'id': 'respiratory',
        'name': 'Respiratory',
        'definition': (
            'Your lungs and breathing pathways — oxygen exchange, airway health, '
            'and how well your body delivers oxygen to cells.'
        ),
        'keywords': [
            'respiratory', 'lung', 'bronch', 'breath', 'oxygen', 'airway', 'pulmonary',
            'sleep apnea', 'sinus',
        ],
    },
    {
        'id': 'digestive',
        'name': 'Digestive',
        'definition': (
            'Your stomach, intestines, and gut — breaking down food, absorbing nutrients, '
            'and maintaining a healthy digestive environment.'
        ),
        'keywords': [
            'digestive', 'stomach', 'gut', 'intestin', 'colon', 'bowel', 'esophag',
            'duodenum', 'ileum', 'digestion', 'gi tract', 'dysbiosis', 'galactosidase',
            'bloating', 'protease', 'lactase', 'bromelain',
        ],
    },
    {
        'id': 'pancreas',
        'name': 'Pancreas',
        'definition': (
            'Your pancreas — blood sugar balance, digestive enzyme production, '
            'and metabolic signaling.'
        ),
        'keywords': [
            'pancreas', 'pancreatic', 'insulin', 'glucagon', 'blood sugar', 'glucose',
        ],
    },
    {
        'id': 'liver_gallbladder',
        'name': 'Liver / Gallbladder',
        'definition': (
            'Your liver and gallbladder — detoxification, bile flow, fat processing, '
            'and filtering what enters your bloodstream.'
        ),
        'keywords': [
            'liver', 'gallbladder', 'gall bladder', 'bile', 'hepat', 'detox',
            'capillar', 'glucocerebrosidase', 'sluggish bile',
        ],
    },
    {
        'id': 'metabolism',
        'name': 'Metabolism',
        'definition': (
            'Your cellular energy engine — how efficiently your body creates and uses '
            'fuel at the mitochondrial and metabolic level.'
        ),
        'keywords': [
            'metabolism', 'metabolic', 'mitochondri', 'cellular metabolism', 'nadh',
            'krebs', 'keto', 'lactic acid', 'energy production', 'coq10', 'atp',
            'cellular energy',
        ],
    },
    {
        'id': 'reproductive',
        'name': 'Reproductive',
        'definition': (
            'Your reproductive and urinary pathways — hormones, organs, and balance '
            'related to fertility, elimination, and urogenital health.'
        ),
        'keywords': [
            'urogenital', 'reproductive', 'ovary', 'ovarian', 'prostate', 'uterus',
            'bladder', 'kidney', 'urinary', 'testosterone', 'estrogen', 'androstenedione',
            'progesterone', 'fertility',
        ],
    },
    {
        'id': 'hormones',
        'name': 'Hormones',
        'definition': (
            'Your endocrine signaling — glands and hormones that regulate mood, energy, '
            'weight, sleep, and overall hormonal rhythm.'
        ),
        'keywords': [
            'endocrine', 'hormone', 'hormonal', 'thyroid', 'adrenal', 'cortisol', 'acth',
            'tsh', 'parathyroid', 'dhea', 'hormone precursor',
        ],
    },
    {
        'id': 'muscles',
        'name': 'Muscles',
        'definition': (
            'Your muscles, joints, and structural support — movement, strength, '
            'recovery, and physical resilience.'
        ),
        'keywords': [
            'locomotor', 'muscle', 'muscular', 'joint', 'bone', 'skeletal', 'spine',
            'tendon', 'ligament', 'structural', 'movement', 'calcium balance',
        ],
    },
    {
        'id': 'blood',
        'name': 'Blood',
        'definition': (
            'Your blood and related markers — oxygen delivery, nutrient transport, '
            'and overall blood quality signals.'
        ),
        'keywords': [
            'blood', 'hemoglobin', 'hemat', 'anemia', 'platelet', 'clotting', 'erythro',
        ],
    },
    {
        'id': 'cardiovascular',
        'name': 'Cardiovascular',
        'definition': (
            'Your heart and circulation — blood flow, vessel health, and cardiovascular '
            'resilience under stress.'
        ),
        'keywords': [
            'cardiovascular', 'heart', 'circulat', 'vessel', 'arter', 'vein',
            'lipoprotein', 'cholesterol', 'lipid', 'cardiac',
        ],
    },
    {
        'id': 'lymph',
        'name': 'Lymph',
        'definition': (
            'Your lymphatic system — drainage, immune transport, and clearing waste '
            'from tissues.'
        ),
        'keywords': [
            'lymph', 'lymphatic', 'drainage', 'lymph node',
        ],
    },
    {
        'id': 'immune',
        'name': 'Immune',
        'definition': (
            'Your immune defenses — how your body identifies stressors, inflammation, '
            'and recovery from environmental or microbial challenges.'
        ),
        'keywords': [
            'immune', 'immunity', 'inflamm', 'pathogen', 'infection', 'candida',
            'autoimmune', 'antibod',
        ],
    },
]
