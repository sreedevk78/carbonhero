import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Force Supabase PostgreSQL Connection
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres:sreedevkrishna030524@db.adarimtvhsdpexrwrzii.supabase.co:5432/postgres?sslmode=require"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_recycle': 1800,
        'pool_timeout': 30
    }
