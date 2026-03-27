import os

# These defaults can be overridden via environment variables.
DEFAULT_COUNTRY = os.environ.get('CARBON_COUNTRY', 'IN').upper()
DEFAULT_MEAL_FRACTION = float(os.environ.get('CARBON_MEAL_FRACTION', '0.33'))

FACTOR_SOURCES = {
    'transport': 'DESNZ/DEFRA conversion factors (2024, distance-based passenger travel)',
    'fuel': 'US EPA fuel combustion factors (gasoline/diesel tailpipe CO2)',
    'electricity': 'OWID/Ember country intensity + EPA eGRID (regional US fallback)',
    'diet': 'Scarborough et al. dietary GHG estimates (UK cohort, category-level)',
    'aviation': 'ICAO methodology + UK DfT guidance (8% uplift, RF multiplier context)'
}

# kg CO2e per passenger-km (distance-based fallback factors)
TRANSPORT_FACTORS = {
    'car': 0.171,
    'bus': 0.104,
    'train': 0.035,
    'bike': 0.0,
    'walk': 0.0
}

# Tailpipe fuel combustion factors (kg CO2 per liter)
FUEL_FACTORS = {
    'petrol': 2.31,
    'gasoline': 2.31,
    'diesel': 2.68
}

# Country-level electricity intensity fallbacks (kg CO2e per kWh)
ELECTRICITY_FACTORS = {
    'IN': 0.708,
    'UK': 0.207,
    'US': 0.350,
    'EU': 0.250,
    'WORLD': 0.475
}

# Daily diet emissions (kg CO2e/day @ ~2000 kcal, category-level approximation)
DIET_FACTORS_DAILY = {
    'meat': 5.63,
    'mixed': 4.67,
    'vegetarian': 3.81,
    'vegan': 2.89
}

def get_electricity_factor(country_code=None):
    code = (country_code or DEFAULT_COUNTRY or 'WORLD').upper()
    return ELECTRICITY_FACTORS.get(code, ELECTRICITY_FACTORS['WORLD'])

def compute_emissions_from_activity(activity_data, country_code=None, meal_fraction=None):
    """Formula-first emission engine with source-backed factors and traceable breakdown."""
    data = activity_data or {}
    country = (country_code or DEFAULT_COUNTRY).upper()
    meal_fraction = DEFAULT_MEAL_FRACTION if meal_fraction is None else meal_fraction

    transport_type = data.get('transport_type')
    distance_km = data.get('distance_km') or 0.0
    energy_kwh = data.get('energy_kwh') or 0.0
    fuel_liters = data.get('fuel_liters') or 0.0
    fuel_type = (data.get('fuel_type') or '').lower()
    diet_type = data.get('diet_type')
    flight_distance_km = data.get('flight_distance_km') or 0.0

    breakdown = {
        'transport_kg': 0.0,
        'energy_kg': 0.0,
        'diet_kg': 0.0,
        'assumptions': [],
        'sources': FACTOR_SOURCES
    }

    if fuel_liters > 0:
        selected_fuel = fuel_type if fuel_type in FUEL_FACTORS else 'petrol'
        breakdown['transport_kg'] += fuel_liters * FUEL_FACTORS[selected_fuel]
    elif transport_type == 'flight':
        base_distance = flight_distance_km or distance_km or 300.0
        if (flight_distance_km or distance_km) == 0:
            breakdown['assumptions'].append('Assumed 300 km flight distance due to missing input.')
        flight_uplift = 1.08
        radiative_forcing = 1.9
        base_kg_per_pkm = 0.133
        breakdown['transport_kg'] += base_distance * flight_uplift * base_kg_per_pkm * radiative_forcing
    elif transport_type in TRANSPORT_FACTORS:
        if distance_km == 0 and transport_type not in ('bike', 'walk'):
            distance_km = 5.0
            breakdown['assumptions'].append(f'Assumed 5 km distance for {transport_type}.')
        breakdown['transport_kg'] += distance_km * TRANSPORT_FACTORS[transport_type]

    if energy_kwh > 0:
        elec_factor = get_electricity_factor(country)
        breakdown['energy_kg'] += energy_kwh * elec_factor

    if diet_type in DIET_FACTORS_DAILY:
        daily_factor = DIET_FACTORS_DAILY[diet_type]
        breakdown['diet_kg'] += daily_factor * meal_fraction

    # Identify if a valid activity was logged, even if it results in 0 kg CO2 (like walking)
    is_explicit_zero_emission = (transport_type in ('walk', 'bike') and distance_km > 0)
    total_traceable = breakdown['transport_kg'] + breakdown['energy_kg'] + breakdown['diet_kg']

    if total_traceable == 0 and not is_explicit_zero_emission:
        raise ValueError("Insufficient info: Could not trace emissions. Please specify a solid distance (e.g. '5 km') or fuel amount.")

    total = total_traceable
    # Only force minimum if it's NOT an explicit zero-emission activity
    if not is_explicit_zero_emission:
        total = max(0.1, min(1000.0, round(total, 2)))
    else:
        total = round(total, 2)

    breakdown['transport_kg'] = round(breakdown['transport_kg'], 2)
    breakdown['energy_kg'] = round(breakdown['energy_kg'], 2)
    breakdown['diet_kg'] = round(breakdown['diet_kg'], 2)

    return {
        'total_kg': total,
        'breakdown': breakdown
    }

def calculate_emissions(form_data):
    transport_type = form_data.get('transport_type')
    distance = float(form_data.get('distance') or 0)
    fuel_liters = float(form_data.get('fuel_liters') or 0)
    fuel_type = form_data.get('fuel_type') or None
    energy_kwh = float(form_data.get('energy_usage') or 0)
    diet_type = form_data.get('diet_type') or None

    activity_data = {
        'transport_type': transport_type,
        'distance_km': distance,
        'energy_kwh': energy_kwh,
        'fuel_liters': fuel_liters if fuel_liters > 0 else None,
        'fuel_type': fuel_type if fuel_liters > 0 else None,
        'diet_type': diet_type,
        'flight_distance_km': distance if transport_type == 'flight' else None
    }
    result = compute_emissions_from_activity(activity_data)
    transport = result['breakdown']['transport_kg']
    energy = result['breakdown']['energy_kg']
    diet = result['breakdown']['diet_kg']
    total = result['total_kg']
    return transport, energy, diet, total
