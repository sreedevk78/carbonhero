"""
CarbonHero - Gamified Carbon Footprint Tracker
Author: AI Assistant
Date: 2025-02-04
Description: Single-file Flask application with SQLite database, 
             ML-powered insights, and Duolingo-style gamification
"""

import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
try:
    from flask_bootstrap import Bootstrap5
except ImportError:
    # Compatibility fallback for older flask_bootstrap versions.
    from flask_bootstrap import Bootstrap as Bootstrap5
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, ValidationError
import numpy as np
from sklearn.linear_model import LinearRegression
import google.generativeai as genai
import speech_recognition as sr
import json
import re

# Initialize Flask app
app = Flask(__name__, 
    static_folder='static',
    template_folder='templates',
    instance_relative_config=True)

# Configuration
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_key_123'),
    SQLALCHEMY_DATABASE_URI='sqlite:///carbonhero.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    BOOTSTRAP_BOOTSWATCH_THEME='minty'
)

# Initialize extensions
bootstrap = Bootstrap5(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Gemini AI Configuration
GOOGLE_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

def build_gemini_model():
    candidates = []

    explicit_model = os.environ.get('GEMINI_MODEL', '').strip()
    if explicit_model:
        candidates.append(explicit_model)

    # Preferred modern model names first.
    candidates.extend([
        'gemini-2.0-flash',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro'
    ])

    # Discover available models from API and append names that support generateContent.
    try:
        for discovered in genai.list_models():
            methods = getattr(discovered, 'supported_generation_methods', []) or []
            if 'generateContent' in methods:
                name = getattr(discovered, 'name', '')
                if name.startswith('models/'):
                    name = name.split('/', 1)[1]
                if name:
                    candidates.append(name)
    except Exception as e:
        print(f"Gemini model discovery error: {str(e)}")

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return genai.GenerativeModel(candidate)
        except Exception:
            continue
    return None

model = build_gemini_model()

def get_gemini_model():
    """Lazy access to a configured Gemini model."""
    global model
    if model is None:
        model = build_gemini_model()
    return model

def generate_gemini_text(prompt):
    """Generate text with retry across candidate models and bounded request time."""
    global model
    active_model = get_gemini_model()
    if active_model is not None:
        try:
            response = active_model.generate_content(
                prompt,
                request_options={"timeout": 20}
            )
            return response.text.strip() if getattr(response, 'text', None) else None
        except Exception as e:
            print(f"Gemini generation error: {str(e)}")

    # Retry with fresh candidates in case model availability changed.
    retry_candidates = [
        'gemini-2.0-flash',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro'
    ]
    try:
        for discovered in genai.list_models():
            methods = getattr(discovered, 'supported_generation_methods', []) or []
            if 'generateContent' in methods:
                name = getattr(discovered, 'name', '')
                if name.startswith('models/'):
                    name = name.split('/', 1)[1]
                if name:
                    retry_candidates.append(name)
    except Exception:
        pass

    seen = set()
    for candidate in retry_candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            retry_model = genai.GenerativeModel(candidate)
            response = retry_model.generate_content(
                prompt,
                request_options={"timeout": 20}
            )
            if getattr(response, 'text', None):
                model = retry_model
                return response.text.strip()
        except Exception:
            continue
    return None

# --------------------
# 0. FACTOR SOURCES / CONFIG
# --------------------
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
    'car': 0.171,   # average passenger car fallback
    'bus': 0.104,   # local bus / average passenger bus
    'train': 0.035, # national rail typical order of magnitude
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
    'IN': 0.708,  # India grid intensity, typical recent range
    'UK': 0.207,  # UK low-carbon grid
    'US': 0.350,  # US average (eGRID-like magnitude)
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

# --------------------
# 1. DATABASE MODELS
# --------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    streak = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime)
    total_points = db.Column(db.Integer, default=0)
    carbon_score = db.Column(db.Float, default=0)
    achievements = db.relationship('Achievement', backref='user', lazy=True)
    carbon_logs = db.relationship('CarbonLog', backref='user', lazy=True)

class CarbonLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    activity_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    transport_type = db.Column(db.String(50))
    distance = db.Column(db.Float)
    energy_usage = db.Column(db.Float)
    diet_type = db.Column(db.String(50))
    transport_emissions = db.Column(db.Float)
    energy_emissions = db.Column(db.Float)
    diet_emissions = db.Column(db.Float)
    custom_activity = db.Column(db.Text)
    ai_calculated_emissions = db.Column(db.Float)
    total_emissions = db.Column(db.Float)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    badge_type = db.Column(db.String(50))
    date_earned = db.Column(db.DateTime, default=datetime.utcnow)

class EnvironmentalNews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
# --------------------
# 2. FORMS
# --------------------
class SignupForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters"),
    ])
    submit = SubmitField('Sign Up')

    def validate_password(self, field):
        if not any(c.isupper() for c in field.data):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in field.data):
            raise ValidationError('Password must contain at least one number')
        if not any(c in '!@#$%^&*' for c in field.data):
            raise ValidationError('Password must contain at least one special character (!@#$%^&*)')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class CarbonEntryForm(FlaskForm):
    transport_type = SelectField('Transport Type', choices=[
        ('car', 'Car'), 
        ('bus', 'Bus'), 
        ('train', 'Train'),
        ('bike', 'Bicycle'),
        ('walk', 'Walking')
    ])
    distance = FloatField('Distance (km)', validators=[DataRequired()])
    energy_usage = FloatField('Energy Usage (kWh)', validators=[DataRequired()])
    diet_type = SelectField('Diet Type', choices=[
        ('meat', 'Meat Heavy'),
        ('mixed', 'Mixed Diet'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan')
    ])
    custom_activity = TextAreaField('Custom Activity Description')
    submit = SubmitField('Log Activity')

# --------------------
# 3. AI/ML COMPONENTS
# --------------------
class CarbonPredictor:
    def __init__(self):
        self.model = LinearRegression()
        # Mock training data (would use real data in production)
        X = np.array([[1, 2], [2, 3], [3, 4], [4, 5]])
        y = np.array([10, 20, 30, 40])
        self.model.fit(X, y)
    
    def predict_reduction(self, features):
        return self.model.predict([features])[0]

def get_electricity_factor(country_code=None):
    code = (country_code or DEFAULT_COUNTRY or 'WORLD').upper()
    return ELECTRICITY_FACTORS.get(code, ELECTRICITY_FACTORS['WORLD'])

def extract_activity_data_local(activity_description):
    """Parse free text into structured activity fields (deterministic parser)."""
    text = (activity_description or "").lower().strip()
    data = {
        'transport_type': None,
        'distance_km': None,
        'energy_kwh': None,
        'fuel_liters': None,
        'fuel_type': None,
        'diet_type': None,
        'flight_distance_km': None
    }

    # Transport mode hints
    if any(w in text for w in ['flight', 'plane', 'airplane', 'aeroplane']):
        data['transport_type'] = 'flight'
    elif any(w in text for w in ['car', 'taxi', 'uber', 'cab']):
        data['transport_type'] = 'car'
    elif 'bus' in text:
        data['transport_type'] = 'bus'
    elif 'train' in text or 'metro' in text:
        data['transport_type'] = 'train'
    elif 'bike' in text or 'bicycle' in text:
        data['transport_type'] = 'bike'
    elif 'walk' in text or 'walking' in text:
        data['transport_type'] = 'walk'

    # Distance extraction
    distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(km|kilometer|kilometre|miles?|mi)\b", text)
    if distance_match:
        value = float(distance_match.group(1))
        unit = distance_match.group(2)
        km_value = value * 1.60934 if unit.startswith('mi') else value
        data['distance_km'] = km_value
        if data['transport_type'] == 'flight':
            data['flight_distance_km'] = km_value

    # Fuel quantity
    liters_match = re.search(r"(\d+(?:\.\d+)?)\s*(l|liters?|litres?)\b", text)
    if liters_match:
        data['fuel_liters'] = float(liters_match.group(1))
        data['fuel_type'] = 'diesel' if 'diesel' in text else 'petrol'

    # Electricity usage
    kwh_match = re.search(r"(\d+(?:\.\d+)?)\s*(kwh|kilowatt[- ]?hours?)\b", text)
    if kwh_match:
        data['energy_kwh'] = float(kwh_match.group(1))

    # Diet hints
    if any(w in text for w in ['beef', 'lamb', 'meat', 'chicken', 'mutton']):
        data['diet_type'] = 'meat'
    elif 'vegetarian' in text:
        data['diet_type'] = 'vegetarian'
    elif 'vegan' in text:
        data['diet_type'] = 'vegan'
    elif any(w in text for w in ['fish', 'egg', 'eggs', 'dairy']):
        data['diet_type'] = 'mixed'

    return data

def extract_activity_data_with_ai(activity_description):
    """
    Use Gemini to extract structured fields only.
    Emissions are always computed by formula engine, not by LLM-generated numbers.
    """
    prompt = f"""
    Extract structured activity data from this text and return strict JSON only.
    Activity text: "{activity_description}"

    Return JSON with keys:
    - transport_type: one of [car,bus,train,bike,walk,flight,null]
    - distance_km: number or null
    - energy_kwh: number or null
    - fuel_liters: number or null
    - fuel_type: one of [petrol,diesel,null]
    - diet_type: one of [meat,mixed,vegetarian,vegan,null]
    - flight_distance_km: number or null

    Rules:
    - If uncertain, use null.
    - Do not include explanations.
    """
    try:
        text = generate_gemini_text(prompt)
        if not text:
            return None
        json_blob = re.search(r"\{[\s\S]*\}", text)
        if not json_blob:
            return None
        parsed = json.loads(json_blob.group(0))
        return {
            'transport_type': parsed.get('transport_type'),
            'distance_km': parsed.get('distance_km'),
            'energy_kwh': parsed.get('energy_kwh'),
            'fuel_liters': parsed.get('fuel_liters'),
            'fuel_type': parsed.get('fuel_type'),
            'diet_type': parsed.get('diet_type'),
            'flight_distance_km': parsed.get('flight_distance_km')
        }
    except Exception as e:
        print(f"AI extraction error: {str(e)}")
        return None

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

    # Transport calculation hierarchy:
    # 1) fuel liters if available (most direct for combustion)
    # 2) flight-specific formula
    # 3) distance x mode factor fallback
    if fuel_liters > 0:
        selected_fuel = fuel_type if fuel_type in FUEL_FACTORS else 'petrol'
        breakdown['transport_kg'] += fuel_liters * FUEL_FACTORS[selected_fuel]
    elif transport_type == 'flight':
        base_distance = flight_distance_km or distance_km or 300.0
        if (flight_distance_km or distance_km) == 0:
            breakdown['assumptions'].append('Assumed 300 km flight distance due to missing input.')
        flight_uplift = 1.08  # non-direct routing/taxiing uplift
        radiative_forcing = 1.9  # conservative UK-practice multiplier context
        economy_kg_per_pkm = 0.133
        breakdown['transport_kg'] += base_distance * flight_uplift * economy_kg_per_pkm * radiative_forcing
    elif transport_type in TRANSPORT_FACTORS:
        if distance_km == 0 and transport_type not in ('bike', 'walk'):
            distance_km = 5.0
            breakdown['assumptions'].append(f'Assumed 5 km distance for {transport_type}.')
        breakdown['transport_kg'] += distance_km * TRANSPORT_FACTORS[transport_type]

    # Electricity emissions
    if energy_kwh > 0:
        elec_factor = get_electricity_factor(country)
        breakdown['energy_kg'] += energy_kwh * elec_factor

    # Diet emissions
    if diet_type in DIET_FACTORS_DAILY:
        daily_factor = DIET_FACTORS_DAILY[diet_type]
        breakdown['diet_kg'] += daily_factor * meal_fraction

    # Raise error if no activity could be confidently parsed
    if (breakdown['transport_kg'] + breakdown['energy_kg'] + breakdown['diet_kg']) == 0:
        raise ValueError("Insufficient info: Could not trace emissions. Please specify a solid distance (e.g. '5 km') or fuel amount.")

    total = breakdown['transport_kg'] + breakdown['energy_kg'] + breakdown['diet_kg']
    total = max(0.1, min(1000.0, round(total, 2)))
    breakdown['transport_kg'] = round(breakdown['transport_kg'], 2)
    breakdown['energy_kg'] = round(breakdown['energy_kg'], 2)
    breakdown['diet_kg'] = round(breakdown['diet_kg'], 2)

    return {
        'total_kg': total,
        'breakdown': breakdown
    }

def estimate_emissions_from_text(activity_description):
    local_data = extract_activity_data_local(activity_description)
    result = compute_emissions_from_activity(local_data)
    return result['total_kg']

def calculate_ai_emissions(activity_description):
    # Formula-first: extract structure (AI + local parser), then calculate via deterministic formulas.
    try:
        local_data = extract_activity_data_local(activity_description)
        ai_data = extract_activity_data_with_ai(activity_description)

        merged_data = dict(local_data)
        if ai_data:
            for key, value in ai_data.items():
                if value is not None and (merged_data.get(key) is None):
                    merged_data[key] = value

        result = compute_emissions_from_activity(merged_data)
        return result['total_kg']
    except Exception as e:
        print(f"AI Calculation Error: {str(e)}")
        return estimate_emissions_from_text(activity_description)

def speech_to_text():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening...")
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio)
            return text
    except Exception as e:
        print(f"Speech Recognition Error: {str(e)}")
        return None

def fetch_environmental_news():
    prompt = """
    Provide exactly 5 recent and significant environmental news stories.
    Return strict JSON only in this exact format:
    {
      "items": [
        {"title": "...", "description": "...", "source": "https://..."},
        {"title": "...", "description": "...", "source": "https://..."}
      ]
    }

    Requirements:
    - Keep each title under 120 characters.
    - Keep each description 2-3 sentences, factual and concise.
    - Focus on climate policy, renewables, conservation, and sustainable innovation.
    - For "source", provide a real URL to a credible news outlet (Reuters, BBC, Guardian, AP News, etc.) where the story can be found. If unsure, provide a Google News search URL for the headline.
    """
    
    try:
        news_text = generate_gemini_text(prompt)
        if not news_text:
            return None

        # Parse JSON-first
        news_items = []
        json_blob = re.search(r"\{[\s\S]*\}", news_text)
        if json_blob:
            parsed = json.loads(json_blob.group(0))
            items = parsed.get('items', [])
            for item in items:
                title = str(item.get('title', '')).strip()
                description = str(item.get('description', '')).strip()
                source = str(item.get('source', '')).strip()
                if not source or not source.startswith('http'):
                    source = 'https://www.google.com/search?q=' + '+'.join(title.split()[:8])
                if title and description:
                    news_items.append({'title': title, 'description': description, 'source': source})

        # Legacy text parsing fallback
        if not news_items:
            current_stories = news_text.split('\n\n')
            for story in current_stories:
                if 'TITLE:' in story and 'DESCRIPTION:' in story:
                    title = story.split('TITLE:')[1].split('DESCRIPTION:')[0].strip()
                    description = story.split('DESCRIPTION:')[1].strip()
                    if title and description:
                        news_items.append({'title': title, 'description': description})

        return news_items[:5] if news_items else None
    except Exception as e:
        print(f"News Fetch Error: {str(e)}")
        return None
# --------------------
# 4. HELPER FUNCTIONS
# --------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def update_streak(user):
    now = datetime.utcnow().date()
    # Ensure streak tracks unique calendar days of activity
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
    # db.session.commit() will happen in the calling log_entry commit

EMISSION_FACTORS = {
    # Maintained for compatibility in other code paths.
    'transport': TRANSPORT_FACTORS,
    'diet_daily': DIET_FACTORS_DAILY,
    'energy_country_default': get_electricity_factor(DEFAULT_COUNTRY)
}

def calculate_emissions(form_data):
    activity_data = {
        'transport_type': form_data['transport_type'],
        'distance_km': float(form_data.get('distance') or 0),
        'energy_kwh': float(form_data.get('energy_usage') or 0),
        'fuel_liters': None,
        'fuel_type': None,
        'diet_type': form_data['diet_type'],
        'flight_distance_km': None
    }
    result = compute_emissions_from_activity(activity_data)
    transport = result['breakdown']['transport_kg']
    energy = result['breakdown']['energy_kg']
    diet = result['breakdown']['diet_kg']
    total = result['total_kg']
    return transport, energy, diet, total

# --------------------
# 4b. BOSS DAMAGE & GREEN LOG SYSTEM
# --------------------
BOSS_DAMAGE_TABLE = {
    'walk': 40,
    'bike': 35,
    'bus': 20,
    'train': 20,
    'car': 10,
    'flight': 5,
}
DIET_DAMAGE_TABLE = {
    'vegan': 30,
    'vegetarian': 20,
    'mixed': 5,
    'meat': 0,
}
GREEN_TRANSPORT = {'walk', 'bike'}
GREEN_DIETS = {'vegan', 'vegetarian'}

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

def calculate_boss_damage(transport_type=None, diet_type=None, total_emissions=0, streak=0):
    """Calculate HP damage dealt to the Smog Boss for a given log entry."""
    base_damage = BOSS_DAMAGE_TABLE.get(transport_type, 10)
    diet_damage = DIET_DAMAGE_TABLE.get(diet_type, 0)
    # Low emissions bonus
    emission_bonus = 0
    if total_emissions < 1.0:
        emission_bonus = 20
    elif total_emissions < 2.0:
        emission_bonus = 10
    # Green transport bonus
    green_bonus = 20 if transport_type in GREEN_TRANSPORT else 0
    raw_damage = base_damage + diet_damage + emission_bonus + green_bonus
    # Streak multiplier (minimum 1x)
    multiplier = max(1, streak)
    total_damage = raw_damage * multiplier
    return {
        'base': base_damage,
        'diet': diet_damage,
        'emission_bonus': emission_bonus,
        'green_bonus': green_bonus,
        'multiplier': multiplier,
        'total': total_damage
    }

# --------------------
# 5. ROUTES
# --------------------
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = SignupForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        
        hashed_pw = generate_password_hash(form.password.data)
        new_user = User(email=form.email.data, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    carbon_logs = CarbonLog.query.filter_by(user_id=current_user.id)\
        .order_by(CarbonLog.date.desc()).limit(10).all()
    
    total_emissions = sum(log.total_emissions for log in carbon_logs) if carbon_logs else 0
    average_emissions = total_emissions / len(carbon_logs) if carbon_logs else 0
    
    features = [average_emissions, current_user.streak]
    predicted_reduction = carbon_ai.predict_reduction(features)
    
    # Dynamic Gamification Badges
    achievements = []
    if carbon_logs:
        achievements.append({'id': 'first', 'image': 'badge_first.png', 'title': 'First Steps'})
    if total_emissions > 0 and average_emissions < 3.0:
        achievements.append({'id': 'low', 'image': 'badge_low.png', 'title': 'Low Carbon Hero'})
    if current_user.streak >= 3:
        achievements.append({'id': 'streak', 'image': 'badge_streak.png', 'title': 'Streak Master'})
    if current_user.total_points >= 50:
        achievements.append({'id': 'eco', 'image': 'badge_eco.png', 'title': 'Eco Warrior'})
    if current_user.total_points >= 100:
        achievements.append({'id': 'top', 'image': 'badge_top.png', 'title': 'Top Tier'})
    
    if not achievements:
        achievements.append({'id': 'none', 'image': 'logo.png', 'title': 'Log to Unlock!'})
    
    return render_template('dashboard.html',
                         carbon_logs=carbon_logs,
                         total_emissions=total_emissions,
                         average_emissions=average_emissions,
                         predicted_reduction=predicted_reduction,
                         carbon_score=current_user.carbon_score or 0,
                         streak=current_user.streak or 0,
                         points=current_user.total_points or 0,
                         achievements=achievements)

@app.route('/boss')
@login_required
def boss_arena():
    recent_log = CarbonLog.query.filter_by(user_id=current_user.id).order_by(CarbonLog.date.desc()).first()
    return render_template('boss.html', 
                         carbon_score=current_user.carbon_score or 0,
                         total_points=current_user.total_points or 0,
                         streak=current_user.streak or 0,
                         recent_log=recent_log)

@app.route('/log-entry', methods=['GET', 'POST'])
@login_required
def log_entry():
    form = CarbonEntryForm()
    if request.method == 'POST':
        try:
            if 'voice_input' in request.form:
                activity_text = request.form.get('voice_transcript')  # Get the transcript from the form
                if activity_text:
                    try:
                        # Calculate emissions using AI
                        ai_emissions = calculate_ai_emissions(activity_text)
                        
                        # Create new log entry
                        new_log = CarbonLog(
                            user_id=current_user.id,
                            activity_type='voice_input',
                            description=activity_text,
                            ai_calculated_emissions=ai_emissions,
                            total_emissions=ai_emissions
                        )
                        
                        # Add to database and update user stats
                        db.session.add(new_log)
                        current_user.total_points += 10
                        current_user.carbon_score += ai_emissions
                        # Green log bonus for voice input
                        green = classify_green_log(total_emissions=ai_emissions)
                        if green['is_green']:
                            current_user.total_points += green['bonus']
                        update_streak(current_user)
                        db.session.commit()
                        # Boss damage
                        dmg = calculate_boss_damage(total_emissions=ai_emissions, streak=current_user.streak or 0)
                        flash(f'Voice activity logged! Emissions: {ai_emissions:.2f} kg CO₂', 'success')
                        flash(f'⚔️ You dealt {dmg["total"]} HP damage to the Smog Boss!', 'success')
                        if green['is_green']:
                            flash(f'🌿 GREEN LOG! +{green["bonus"]} bonus points', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error processing voice input: {str(e)}', 'danger')
                else:
                    flash('No voice input received. Please try again.', 'warning')


            elif request.form.get('custom_activity'):
                activity_text = request.form.get('custom_activity', '').strip()
                if activity_text:
                    ai_emissions = calculate_ai_emissions(activity_text)
                    new_log = CarbonLog(
                        user_id=current_user.id,
                        activity_type='custom',
                        description=activity_text,
                        ai_calculated_emissions=ai_emissions,
                        total_emissions=ai_emissions
                    )
                    db.session.add(new_log)
                    current_user.total_points += 10
                    current_user.carbon_score += ai_emissions
                    # Green log bonus for custom
                    green = classify_green_log(total_emissions=ai_emissions)
                    if green['is_green']:
                        current_user.total_points += green['bonus']
                    update_streak(current_user)
                    db.session.commit()
                    dmg = calculate_boss_damage(total_emissions=ai_emissions, streak=current_user.streak or 0)
                    flash(f'Custom activity logged! Emissions: {ai_emissions:.2f} kg CO₂', 'success')
                    flash(f'⚔️ You dealt {dmg["total"]} HP damage to the Smog Boss!', 'success')
                    if green['is_green']:
                        flash(f'🌿 GREEN LOG! +{green["bonus"]} bonus points', 'success')
                else:
                    flash('Please provide a description of your activity.', 'warning')

            else:
                if not form.validate_on_submit():
                    flash('Please fill all required fields for the standard log.', 'warning')
                    return render_template('log_entry.html', form=form)
                transport_emissions, energy_emissions, diet_emissions, total = calculate_emissions(form.data)
                new_log = CarbonLog(
                    user_id=current_user.id,
                    transport_type=form.transport_type.data,
                    distance=form.distance.data,
                    energy_usage=form.energy_usage.data,
                    diet_type=form.diet_type.data,
                    transport_emissions=transport_emissions,
                    energy_emissions=energy_emissions,
                    diet_emissions=diet_emissions,
                    total_emissions=total
                )
                db.session.add(new_log)
                current_user.total_points += 10
                current_user.carbon_score += total
                # Green log bonus
                green = classify_green_log(form.transport_type.data, form.diet_type.data, total)
                if green['is_green']:
                    current_user.total_points += green['bonus']
                update_streak(current_user)
                db.session.commit()
                # Boss damage flash
                dmg = calculate_boss_damage(form.transport_type.data, form.diet_type.data, total, current_user.streak or 0)
                flash(f'Activity logged! Emissions: {total:.2f} kg CO₂', 'success')
                flash(f'⚔️ You dealt {dmg["total"]} HP damage to the Smog Boss! (Base:{dmg["base"]} + Diet:{dmg["diet"]} + Bonus:{dmg["emission_bonus"]+dmg["green_bonus"]}) × {dmg["multiplier"]}x Streak', 'success')
                if green['is_green']:
                    flash(f'🌿 GREEN LOG! +{green["bonus"]} bonus points — {", ".join(green["reasons"])}', 'success')
            
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error logging activity: {str(e)}', 'danger')
    
    return render_template('log_entry.html', form=form)
@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.order_by(User.total_points.desc()).limit(10).all()
    current_user_rank = db.session.query(User).filter(User.total_points > current_user.total_points).count() + 1
    next_rank_user = User.query.filter(User.total_points > current_user.total_points)\
        .order_by(User.total_points.asc()).first()
    points_to_next_rank = next_rank_user.total_points - current_user.total_points if next_rank_user else 0
    weekly_progress = min(100, (current_user.total_points % 100))
    
    return render_template('leaderboard.html',
                         users=users,
                         current_user_rank=current_user_rank,
                         points_to_next_rank=points_to_next_rank,
                         weekly_progress=weekly_progress)

@app.route('/news')
@login_required
def environmental_news():
    try:
        news_items = fetch_environmental_news()
        if not news_items:
            raise Exception("No news items retrieved")
        
        # Store news items in database
        for item in news_items:
            news_entry = EnvironmentalNews(
                title=item['title'],
                description=item['description'],
                date_added=datetime.utcnow()
            )
            db.session.add(news_entry)
        db.session.commit()
        
        # Get the latest news from database
        latest_news = EnvironmentalNews.query.order_by(
            EnvironmentalNews.date_added.desc()
        ).limit(5).all()
        
        return render_template(
            'news.html',
            news_items=latest_news,
            fetch_time=datetime.utcnow()
        )
    except Exception as e:
        print(f"News Error: {str(e)}")
        # Fallback to database if API fails
        latest_news = EnvironmentalNews.query.order_by(
            EnvironmentalNews.date_added.desc()
        ).limit(5).all()
        
        if latest_news:
            return render_template(
                'news.html',
                news_items=latest_news,
                fetch_time=latest_news[0].date_added if latest_news else datetime.utcnow()
            )
        else:
            flash('Unable to fetch news at this time. Please try again later.', 'warning')
            return render_template('news.html', news_items=[], fetch_time=None)

@app.route('/achievements')
@login_required
def achievements():
    boss_hp = max(0, 1000 - (current_user.total_points * 20) + (current_user.carbon_score * 5))
    boss_level = (current_user.total_points // 100) + 1
    
    carbon_logs = CarbonLog.query.filter_by(user_id=current_user.id).all()
    total_emissions = sum(log.total_emissions for log in carbon_logs) if carbon_logs else 0
    average_emissions = total_emissions / len(carbon_logs) if carbon_logs else 0

    all_badges = [
        {'id': 'first', 'image': 'badge_first.png', 'title': 'First Steps', 'desc': 'Log your very first carbon activity.', 'unlocked': len(carbon_logs) > 0},
        {'id': 'low', 'image': 'badge_low.png', 'title': 'Low Carbon Hero', 'desc': 'Maintain an average emission below 3.0 kg per log.', 'unlocked': (total_emissions > 0 and average_emissions < 3.0)},
        {'id': 'streak', 'image': 'badge_streak.png', 'title': 'Streak Master', 'desc': 'Log activities for 3 consecutive days.', 'unlocked': current_user.streak >= 3},
        {'id': 'eco', 'image': 'badge_eco.png', 'title': 'Eco Warrior', 'desc': 'Accumulate 50 total game points.', 'unlocked': current_user.total_points >= 50},
        {'id': 'top', 'image': 'badge_top.png', 'title': 'Top Tier', 'desc': 'Reach 100 total game points and defeat the Boss Level 1.', 'unlocked': current_user.total_points >= 100}
    ]

    return render_template('achievements.html', badges=all_badges, boss_hp=boss_hp, boss_level=boss_level)

@app.route('/api/insights')
@login_required
def api_insights():
    logs = CarbonLog.query.filter_by(user_id=current_user.id).order_by(CarbonLog.date.desc()).limit(3).all()
    log_texts = [f"{l.activity_type}: {l.description or l.transport_type} ({l.total_emissions}kg)" for l in logs]
    
    boss_hp = max(0, 1000 - (current_user.total_points * 20) + (current_user.carbon_score * 5))
    boss_level = (current_user.total_points // 100) + 1

    prompt = f"""
    The user is fighting an RPG boss ("The Smog Monster").
    Boss HP: {boss_hp}/1000 (Level {boss_level}).
    User's recent activities: {', '.join(log_texts) if log_texts else 'None yet'}.
    
    Provide exactly two lines separated by a newline (no markdown, no quotes):
    1. A highly-personalized tip to intelligently reduce emissions specifically based on their recent logged activities.
    2. A taunt from the Smog Monster aggressively reacting to their recent CO2 emissions or praising their failure.
    """
    try:
        text = generate_gemini_text(prompt)
        if not text:
            text = "Tip: Log more activities to unlock AI insights!\nSmog Boss: I hunger for your carbon footprint!"
    except:
        text = "Tip: Log more activities to unlock AI insights!\nSmog Boss: I hunger for your carbon footprint!"
        
    parts = text.split('\n')
    valid_parts = [p.strip() for p in parts if p.strip()]
    
    tip = valid_parts[0] if len(valid_parts) > 0 else "Keep logging activities!"
    taunt = valid_parts[-1] if len(valid_parts) > 1 else "I am the Smog Boss!"
    
    return {'tip': tip, 'taunt': taunt, 'boss_hp': boss_hp, 'boss_level': boss_level}

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get('message', '')).strip()
    if not user_message:
        return {'reply': 'Please type a message to chat with me!'}

    logs = CarbonLog.query.filter_by(user_id=current_user.id).order_by(CarbonLog.date.desc()).limit(5).all()
    log_summary = ', '.join([f"{l.transport_type or l.activity_type}: {l.total_emissions}kg" for l in logs]) if logs else 'No logs yet'
    boss_hp = max(0, 1000 - (current_user.total_points * 20) + (current_user.carbon_score * 5))

    prompt = f"""You are CarbonHero AI, a friendly and knowledgeable eco-gaming companion inside a gamified carbon tracker RPG.
The user has {current_user.total_points} points, a {current_user.streak}-day streak, and total carbon score of {current_user.carbon_score:.1f} kg.
Their recent logs: {log_summary}. The Smog Boss has {boss_hp}/1000 HP.

The user says: \"{user_message}\"

Reply in 1-3 sentences. Be helpful, fun, encouraging, and relate everything to their carbon footprint journey and the boss fight.
Do not use markdown formatting. Keep it conversational."""

    try:
        reply = generate_gemini_text(prompt)
        if not reply:
            reply = "I'm having trouble connecting right now. Keep fighting the Smog Boss!"
    except:
        reply = "I'm having trouble connecting right now. Keep fighting the Smog Boss!"

    return {'reply': reply}

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# --------------------
# 6. ERROR HANDLERS
# --------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# --------------------
# 7. APP INITIALIZATION
# --------------------
carbon_ai = CarbonPredictor()

def initialize_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Add initial news entries if none exist
        if not EnvironmentalNews.query.first():
            try:
                news_items = fetch_environmental_news()
                if news_items:
                    for item in news_items:
                        news_entry = EnvironmentalNews(
                            title=item['title'],
                            description=item['description']
                        )
                        db.session.add(news_entry)
                    db.session.commit()
            except Exception as e:
                print(f"Initial news fetch error: {str(e)}")

def create_app():
    # Create instance directory if it doesn't exist
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    # Initialize database
    initialize_database()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
