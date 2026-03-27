from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
    source = db.Column(db.String(500))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
