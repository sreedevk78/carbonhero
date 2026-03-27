from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.models import CarbonLog
from app.utils.ai import CarbonPredictor

bp = Blueprint('main', __name__)
carbon_ai = CarbonPredictor()

@bp.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/dashboard')
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
