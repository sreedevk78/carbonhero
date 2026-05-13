import os
from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Supabase Production Connection (Session Mode Pooler)
    # This format is verified for Vercel/Python environments
    SUPABASE_URL = "postgresql+psycopg2://postgres.adarimtvhsdpexrwrzii:sreedevkrishna030524@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    
    SQLALCHEMY_DATABASE_URI = SUPABASE_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,  # Recommended for serverless
    }
