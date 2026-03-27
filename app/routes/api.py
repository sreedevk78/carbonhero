import re as _re
import random as _random
from flask import Blueprint, request
from flask_login import current_user, login_required
from app.models import CarbonLog, EnvironmentalNews
from app.utils.ai import generate_gemini_text, fetch_environmental_news
from app.extensions import db
from datetime import datetime

bp = Blueprint('api', __name__, url_prefix='/api')


def _has_word(text, words):
    """Check if any of the given words appear as whole words in text (not substrings)."""
    for w in words:
        if _re.search(r'\b' + _re.escape(w) + r'\b', text):
            return True
    return False


@bp.route('/insights')
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
            raise Exception("AI failed")
    except:
        text = _get_fallback_insight(current_user, boss_hp)
        
    parts = text.split('\n')
    valid_parts = [p.strip() for p in parts if p.strip()]
    
    tip = valid_parts[0] if len(valid_parts) > 0 else "Keep logging activities!"
    taunt = valid_parts[-1] if len(valid_parts) > 1 else "I am the Smog Boss!"
    
    return {'tip': tip, 'taunt': taunt, 'boss_hp': boss_hp, 'boss_level': boss_level}

@bp.route('/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get('message', '')).strip()
    if not user_message:
        return {'reply': 'Please type a message to chat with me!'}

    boss_hp = max(0, 1000 - (current_user.total_points * 20) + (current_user.carbon_score * 5))
    logs = CarbonLog.query.filter_by(user_id=current_user.id).order_by(CarbonLog.date.desc()).limit(5).all()
    log_summary = ', '.join([f"{l.transport_type or l.activity_type}: {l.total_emissions}kg" for l in logs]) if logs else 'No logs yet'

    prompt = f"""You are CarbonHero AI, a friendly and knowledgeable eco-gaming companion inside a gamified carbon tracker RPG.
The user has {current_user.total_points} points, a {current_user.streak}-day streak, and total carbon score of {current_user.carbon_score:.1f} kg.
Their recent logs: {log_summary}. The Smog Boss has {boss_hp}/1000 HP.

APP KNOWLEDGE & NAVIGATION BRIEFING:
- PAGES: Dashboard (/dashboard), Log Activity (/log-entry), Boss Arena (/boss), Leaderboard (/leaderboard), News (/news), Achievements (/achievements).
- LOGGING: Users can log via Standard Form (context-aware Transport, Food, Energy fields), Voice Tracking (speech-to-text), or Custom Text (AI extraction).
- BADGES: First Steps (1st log), Low Carbon Hero (avg < 3kg), Streak Master (3-day streak), Eco Warrior (50 pts), Top Tier (100 pts).
- BOSS FIGHT: Green actions (Walk, Bike, Vegan, Vegetarian) deal massive damage. Carbon-heavy actions (Car, Flight, Meat-heavy diet) HEAL the Smog Boss!

SCOPE & GUARDRAILS:
1. ONLY answer questions related to CarbonHero, carbon footprints, sustainability, climate change, or the RPG game mechanics (boss/badges).
2. If a user asks about unrelated topics (e.g., math, general history, programming, casual chat like 'who are you'), politely decline and explain you are a specialized Green AI assistant.
3. Keep responses to 1-3 sentences. Do not use markdown.

The user says: "{user_message}"
"""

    try:
        reply = generate_gemini_text(prompt)
        if not reply:
            raise Exception("Quota Exception")
    except:
        reply = _smart_fallback(user_message, boss_hp, current_user)

    return {'reply': reply}


def _smart_fallback(user_message, boss_hp, user):
    """Intelligent keyword-based fallback with strict 'Green AI' specialization."""
    msg = user_message.lower()

    # --- Topic Validation (Scope Guard) ---
    all_keywords = [
        'hello', 'hi', 'hey', 'yo', 'sup', 'howdy', 'hola', 'who',
        'boss', 'fight', 'smog', 'monster', 'battle', 'attack', 'damage', 'hp',
        'streak', 'points', 'score', 'rank', 'leaderboard', 'progress', 'stats', 'level',
        'car', 'drive', 'driving', 'uber', 'taxi', 'cab', 'bike', 'bicycle', 'cycling', 'cycle', 'biking',
        'walk', 'walking', 'walked', 'run', 'running', 'jog', 'bus', 'train', 'metro', 'transit', 'subway', 'tram',
        'flight', 'fly', 'flying', 'plane', 'airplane', 'airport', 'transport', 'travel', 'trip',
        'meat', 'beef', 'chicken', 'lamb', 'pork', 'vegan', 'vegetarian', 'diet', 'food', 'meal', 'eat', 'eating',
        'energy', 'electricity', 'power', 'solar', 'renewable', 'kwh', 'light', 'lights',
        'help', 'how', 'what', 'guide', 'tutorial', 'explain', 'use', 'work', 'which', 'where',
        'badge', 'badges', 'achievement', 'achievements', 'unlock', 'reward', 'first', 'steps', 'warrior', 'hero', 'top',
        'environment', 'sustainability', 'eco', 'green', 'carbon', 'footprint', 'co2', 'emission', 'emissions', 'planet', 'earth'
    ]
    
    if not _has_word(msg, all_keywords):
        return "I'm sorry, but I'm a specialized CarbonHero AI assistant. I can only answer questions related to your carbon footprint, the environment, or our game mechanics!"

    # --- Transport ---
    if _has_word(msg, ['transport', 'travel', 'trip', 'way', 'mode']):
        if _has_word(msg, ['greenest', 'best', 'eco', 'least', 'zero']):
            return "The greenest modes of transport are Walking and Cycling! They produce zero emissions and deal critical damage to the Smog Boss."
        return "For the lowest footprint, choose walking or biking. Public transit like buses and trains are also much better than solo driving!"

    if _has_word(msg, ['car', 'drive', 'driving', 'uber', 'taxi', 'cab']):
        return "Cars generate high CO2 and heal the Smog Boss. Try carpooling or public transit to deal damage instead!"
    
    if _has_word(msg, ['bike', 'bicycle', 'cycling', 'cycle', 'biking', 'walk', 'walking', 'walked']):
        return "Walking and cycling are pure green power! They deal massive critical damage to the Smog Boss."

    # --- Greeting ---
    if _has_word(msg, ['hello', 'hi', 'hey', 'yo', 'sup', 'howdy', 'hola']):
        return _random.choice([
            f"Hey there, Hero! Ready to deal more damage to the Smog Boss? You've got {user.total_points} points so far!",
            f"Welcome back! I'm here to help you track your footprint and defeat the Smog Monster. What's on your mind?",
            "Hey! I'm your CarbonHero AI. Ask me about your stats, the boss fight, or tips to reduce your CO2 emissions!"
        ])

    # --- Badges / Achievements (PRIORITY) ---
    if _has_word(msg, ['badge', 'badges', 'achievement', 'achievements', 'unlock', 'reward', 'steps', 'warrior', 'hero', 'top']):
        return _random.choice([
            "Earn badges like 'First Steps' for your first log, or 'Streak Master' for a 3-day streak! Check them all out at /achievements.",
            "Want to be an 'Eco Warrior'? Reach 50 points! For 'Top Tier', you'll need 100 points and to defeat Boss Level 1.",
            "There are 5 badges to earn: First Steps, Low Carbon Hero, Streak Master, Eco Warrior, and Top Tier. See your progress at /achievements!"
        ])

    # --- Boss / Combat (PRIORITY) ---
    if _has_word(msg, ['boss', 'fight', 'smog', 'monster', 'battle', 'attack', 'damage', 'hp']):
        return _random.choice([
            f"The Smog Boss currently has {boss_hp} HP! Every green activity you log deals direct damage. Keep fighting!",
            f"You're in an epic battle! The Boss sits at {boss_hp} HP. Log a bike ride or plant-based meal to strike hard!",
            f"The Smog Monster has {boss_hp} HP remaining. Your streak multiplier makes each log even more powerful!"
        ])

    # --- Help / How to use ---
    if _has_word(msg, ['help', 'how', 'what', 'guide', 'tutorial', 'explain', 'use', 'work']):
        return _random.choice([
            f"I'm your CarbonHero companion! Log activities via 'Log Activity' (/log-entry) using Standard, Voice, or Custom Text. Defeat the Smog Boss ({boss_hp} HP) by logging green actions like walking!",
            "To fight the boss, log low-carbon actions. Dashboard (/dashboard) shows your progress, and the Boss Arena (/boss) is where the battle happens!",
            "You can log transport, diet, or energy. Check the Leaderboard (/leaderboard) to see other heroes, or Achievements (/achievements) for your earned badges!"
        ])

    # --- General / Catch-all (much better than before) ---
    return _random.choice([
        f"Great question! As your eco-companion, I can help with transport tips, diet advice, or boss fight strategy. You currently have {user.total_points} points and the Boss has {boss_hp} HP!",
        f"I appreciate you reaching out! Try logging a green activity like cycling or a plant-based meal — your {user.streak}-day streak makes each one count even more!",
        f"The Smog Boss is at {boss_hp} HP and your streak is {user.streak} days strong! Ask me about transport, diet, energy, or your progress — I'm here to help!",
        "Every action counts in the fight against the Smog Boss! Log transport, energy, or diet activities to deal damage and earn points. What would you like to know more about?"
    ])


def _get_fallback_insight(user, boss_hp):
    """Provides randomized, contextual tips and taunts when AI is offline."""
    tips = [
        "Try logging a walk or bike ride instead of a car trip to deal massive critical damage!",
        "Every plant-based meal you log helps heal the planet and weakens the Smog Boss.",
        "Reducing your home energy usage kills the Boss's primary power source!",
        "Logging activities daily keeps your streak alive and multiplies your damage.",
        "Check your dashboard to see which activities are your biggest emission sources.",
        "The Smog Boss hates it when you choose public transit over solo driving!",
        "Conserving water and switching off lights are small steps that deal steady damage."
    ]
    
    taunts = [
        f"Foolish Hero! My smog clouds already cover the horizon. I still have {boss_hp} HP!",
        f"You think a few green logs can stop me? I have {boss_hp} HP and a world to pollute!",
        "Your efforts are pathetic! I shall reign supreme as long as cars roam the streets!",
        f"Mwahaha! Your carbon footprint is my energy source. {boss_hp} HP and growing!",
        "I thrive on your convenience! Keep driving, keep wasting, keep feeding me!"
    ]
    
    return f"Tip: {_random.choice(tips)}\nSmog Boss: {_random.choice(taunts)}"

@bp.route('/news')
@login_required
def api_news():
    try:
        news_items = fetch_environmental_news()
        if news_items:
            # Purge old cache to prevent DB bloat
            EnvironmentalNews.query.delete()
            for item in news_items:
                news_entry = EnvironmentalNews(
                    title=item['title'],
                    description=item['description'],
                    source=item.get('source', ''),
                    date_added=datetime.utcnow()
                )
                db.session.add(news_entry)
            db.session.commit()
    except Exception as e:
        print("News Fetch Error:", e)
        db.session.rollback()
        
    latest_news = EnvironmentalNews.query.order_by(EnvironmentalNews.date_added.desc()).limit(5).all()
    
    out = []
    for n in latest_news:
        out.append({
            'title': n.title,
            'description': n.description,
            'source': n.source
        })
        
    time_str = latest_news[0].date_added.strftime('%H:%M') if latest_news else datetime.utcnow().strftime('%H:%M')
    return {'news': out, 'fetch_time': time_str}
