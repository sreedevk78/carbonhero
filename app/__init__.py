import os
from flask import Flask, render_template
from app.config import Config
from app.extensions import db, login_manager, bootstrap

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    login_manager.init_app(app)
    bootstrap.init_app(app)

    # Register blueprints
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.logger import bp as logger_bp
    app.register_blueprint(logger_bp)

    from app.routes.arena import bp as arena_bp
    app.register_blueprint(arena_bp)

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500

    # Ensure instance folder exists for DB
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Database Initialization Hook inside app context
    with app.app_context():
        db.create_all()

    return app
