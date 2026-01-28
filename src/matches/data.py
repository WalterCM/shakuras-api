"""
Central registry for StarCraft: BroodWar unit statistics.
Values are approximations based on BroodWar data.
"""

UNIT_STATS = {
    'base': {
        'hp': 1500,
        'damage': 0,
        'range': 0,
        'cooldown': 0,
        'speed': 0,
        'cost': 400,
        'build_time': 120,
    },
    'worker': {
        'hp': 40,
        'damage': 5,
        'range': 1.5,
        'cooldown': 15,
        'speed': 1.8,
        'cost': 50,
        'build_time': 20,
    },
    'marine': {
        'hp': 40,
        'damage': 50, # Boosted for visible testing
        'range': 4,
        'cooldown': 15,
        'speed': 1.8,
        'cost': 50,
        'build_time': 24,
    },
    'zealot': {
        'hp': 160, # 100 HP + 60 Shields simplified
        'damage': 16,
        'range': 1.5,
        'cooldown': 22,
        'speed': 1.8,
        'cost': 100,
        'build_time': 40,
    },
    'zergling': {
        'hp': 35,
        'damage': 5,
        'range': 1.5,
        'cooldown': 8,
        'speed': 2.6,
        'cost': 25, # Per zergling (usually 50 per pair)
        'build_time': 28,
    },
}
