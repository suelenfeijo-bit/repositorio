import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
from flask_talisman import Talisman
from dotenv import load_dotenv

# Extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
jwt = JWTManager()

def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Config
    app.config.from_object("app.config.Config")

    # Security headers via Talisman (CSP)
    csp = app.config.get("CONTENT_SECURITY_POLICY", {
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", 'data:'],
        'connect-src': ["'self'"],
        'frame-src': ["https://js.stripe.com"],
    })
    Talisman(app, content_security_policy=csp, force_https=False)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    jwt.init_app(app)

    login_manager.login_view = "auth.login"

    # Register blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.products.routes import products_bp
    from app.blueprints.checkout.routes import checkout_bp
    from app.blueprints.reviews.routes import reviews_bp
    from app.blueprints.search.routes import search_bp
    from app.blueprints.api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(reviews_bp, url_prefix="/reviews")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Create FTS5 virtual table and triggers for SQLite on startup
    with app.app_context():
        from app.models import ensure_sqlite_fts5
        ensure_sqlite_fts5()

    # Root route
    @app.get("/")
    def index():
        from flask import render_template
        from app.models import Product
        products = Product.query.order_by(Product.created_at.desc()).limit(8).all()
        return render_template("index.html", products=products)

    return app