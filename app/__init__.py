from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Init extensions with app
    db.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    from app.blueprints.main import main_bp
    app.register_blueprint(main_bp)

    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.blueprints.inventory import inventory_bp
    app.register_blueprint(inventory_bp)

    from app.blueprints.purchase import purchase_bp
    app.register_blueprint(purchase_bp)

    from app.blueprints.sales import sales_bp
    app.register_blueprint(sales_bp)


    from app.blueprints.reports import reports_bp
    app.register_blueprint(reports_bp)

    from app.blueprints.settings import settings_bp
    app.register_blueprint(settings_bp)

    from app.blueprints.manufacturing import manufacturing_bp
    app.register_blueprint(manufacturing_bp)
    
    # Import models so they are registered
    with app.app_context():
        from app import models
        db.create_all()

    return app
