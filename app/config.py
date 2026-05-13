import os
from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Direct Supabase Connection (Standard)
    SUPABASE_URL = "postgresql+psycopg2://postgres:sreedevkrishna030524@db.adarimtvhsdpexrwrzii.supabase.co:5432/postgres?sslmode=require"
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or SUPABASE_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,  # Recommended for serverless
    }
