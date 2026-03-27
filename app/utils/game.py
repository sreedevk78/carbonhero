from datetime import datetime

# DAMAGE table: positive = deals damage to boss, negative = heals boss
BOSS_IMPACT_TABLE = {
    'walk': 40,      # Zero emissions — Critical Hit
    'bike': 35,      # Zero emissions — Critical Hit
    'train': 15,     # Very low per-km emissions
    'bus': 10,       # Low per-km emissions
    'car': -15,      # High emissions — HEALS boss
    'flight': -30,   # Very high emissions — HEALS boss a lot
}

DIET_IMPACT_TABLE = {
    'vegan': 25,        # Lowest diet emissions — strong damage
    'vegetarian': 15,   # Low diet emissions — moderate damage
    'mixed': 5,         # Borderline — tiny damage
    'meat': -20,        # High emissions — HEALS boss
}

GREEN_TRANSPORT = {'walk', 'bike'}
GREEN_DIETS = {'vegan', 'vegetarian'}

def update_streak(user):
    now = datetime.utcnow().date()
    if user.last_login:
        last_date = user.last_login.date()
        diff = (now - last_date).days
        if diff == 1:
            user.streak += 1
        elif diff > 1:
            user.streak = 1
    else:
        user.streak = 1
    user.last_login = datetime.utcnow()

def classify_green_log(transport_type=None, diet_type=None, total_emissions=0):
    """Classify whether a log is 'green' and compute bonus points."""
    is_green = False
    bonus = 0
    reasons = []
    if transport_type in GREEN_TRANSPORT:
        is_green = True
        bonus += 15
        reasons.append(f'{transport_type.title()} is zero-emission transport')
    if diet_type in GREEN_DIETS:
        is_green = True
        bonus += 10
        reasons.append(f'{diet_type.title()} diet is low-carbon')
    if total_emissions < 1.0 and total_emissions > 0:
        is_green = True
        bonus += 5
        reasons.append('Ultra-low total emissions')
    return {'is_green': is_green, 'bonus': bonus, 'reasons': reasons}

def calculate_boss_impact(transport_type=None, diet_type=None, total_emissions=0, streak=0):
    """Calculate HP impact on the Smog Boss.
    
    Returns a dict where 'total' is:
      positive → damage dealt TO the boss (green actions)
      negative → boss HEALS (polluting actions)
    """
    base_impact = BOSS_IMPACT_TABLE.get(transport_type, 0)
    diet_impact = DIET_IMPACT_TABLE.get(diet_type, 0)

    # Emission-based bonus/penalty
    emission_modifier = 0
    if total_emissions < 1.0:
        emission_modifier = 20       # Ultra-low: bonus damage
    elif total_emissions < 2.0:
        emission_modifier = 10       # Low: small bonus
    elif total_emissions > 10.0:
        emission_modifier = -15      # Very high: boss heals extra
    elif total_emissions > 5.0:
        emission_modifier = -10      # High: boss heals some

    # Green transport critical hit bonus
    green_bonus = 20 if transport_type in GREEN_TRANSPORT else 0

    raw_impact = base_impact + diet_impact + emission_modifier + green_bonus

    # Streak multiplier — amplifies BOTH damage and healing
    multiplier = max(1, streak)
    total_impact = raw_impact * multiplier

    return {
        'base': base_impact,
        'diet': diet_impact,
        'emission_modifier': emission_modifier,
        'green_bonus': green_bonus,
        'multiplier': multiplier,
        'total': total_impact,
        'is_heal': total_impact < 0
    }
