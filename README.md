# Flask Marketplace

A secure, non-trivial Flask marketplace demonstrating:
- Authentication: Flask-Login sessions, JWT for API, Google OAuth (Authlib)
- Security: CSRF protection, XSS-safe templates, SQLAlchemy ORM against injections, CSP headers
- MVC: Blueprints (controllers), SQLAlchemy models, Jinja templates (views)
- Stripe Checkout with webhooks
- Product reviews with anti-fake moderation (verified purchase, cooldown + similarity checks)
- Full-text search via SQLite FTS5 integrated with SQLAlchemy

## Quickstart

1. Create virtualenv and install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure environment:
   Copy `.env.example` to `.env` and fill values.
3. Initialize DB:
   ```bash
   export FLASK_APP=wsgi.py
   flask db init
   flask db migrate -m "init"
   flask db upgrade
   ```
4. Run:
   ```bash
   flask run --debug
   ```

## Environment variables

See `.env.example` for full list. Critical ones:
- FLASK_SECRET_KEY
- DATABASE_URL (defaults to sqlite)
- JWT_SECRET_KEY
- STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET
- OAUTH_GOOGLE_CLIENT_ID, OAUTH_GOOGLE_CLIENT_SECRET