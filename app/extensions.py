from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
try:
    from flask_bootstrap import Bootstrap5
except ImportError:
    from flask_bootstrap import Bootstrap as Bootstrap5

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
bootstrap = Bootstrap5()
