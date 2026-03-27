from flask import Blueprint, render_template, flash
from flask_login import current_user, login_required
from app.extensions import db
from app.models import User, CarbonLog, EnvironmentalNews
from datetime import datetime

bp = Blueprint('arena', __name__)

@bp.route('/boss')
@login_required
def boss_arena():
    recent_log = CarbonLog.query.filter_by(user_id=current_user.id).order_by(CarbonLog.date.desc()).first()
    return render_template('boss.html', 
                         carbon_score=current_user.carbon_score or 0,
                         total_points=current_user.total_points or 0,
                         streak=current_user.streak or 0,
                         recent_log=recent_log)

@bp.route('/leaderboard')
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

@bp.route('/news')
@login_required
def environmental_news():
    # Render the news framework instantly without blocking. Javascript will asynchronously load the data!
    return render_template('news.html')

@bp.route('/achievements')
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
