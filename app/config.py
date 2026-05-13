import os
from sqlalchemy.pool import NullPool

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-12345'
    
    # Supabase Production Connection (pg8000 Pure-Python Driver)
    # This avoids binary compatibility issues on Vercel
    SUPABASE_URL = "postgresql+pg8000://postgres:sreedevkrishna030524.adarimtvhsdpexrwrzii@52.74.252.201:5432/postgres"
    
    SQLALCHEMY_DATABASE_URI = SUPABASE_URL
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,
        'connect_args': {
            'ssl_context': True
        }
    }
