import os
from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Supabase Session Pooler (Better for table creation)
    POOLER_URL = "postgresql+psycopg2://postgres.adarimtvhsdpexrwrzii:sreedevkrishna030524@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or POOLER_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,  # Recommended for serverless
    }
