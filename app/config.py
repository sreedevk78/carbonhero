import os
from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Supabase Production Connection (pg8000 Pure-Python Driver)
    # This avoids binary compatibility issues on Vercel
    SUPABASE_URL = "postgresql+pg8000://postgres:sreedevkrishna030524.adarimtvhsdpexrwrzii@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    
    SQLALCHEMY_DATABASE_URI = SUPABASE_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,
        'connect_args': {
            'ssl_context': True
        }
    }
