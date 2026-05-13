import os
from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Supabase Transaction Pooler (Explicit Project Option)
    # This solves the "tenant not found" error by explicitly passing the project ref
    SUPABASE_URL = "postgresql+psycopg2://postgres:sreedevkrishna030524@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?options=project%3Dadarimtvhsdpexrwrzii&sslmode=require"
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or SUPABASE_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,  # Recommended for serverless
    }
