from flask import Blueprint, render_template, request
from sqlalchemy import text

from app.models import db, Product

search_bp = Blueprint("search", __name__, template_folder="../../templates/search")


@search_bp.get('/')
def search():
    q = (request.args.get('q') or '').strip()
    results = []
    if q:
        if db.engine.url.drivername.startswith('sqlite'):
            # Use FTS5 table
            sql = text("""
                SELECT p.* FROM products p
                JOIN product_fts fts ON fts.rowid = p.id
                WHERE product_fts MATCH :query
            """)
            results = db.session.execute(sql, {"query": q}).mappings().all()
            # Map rows to Product model instances
            product_ids = [row['id'] for row in results]
            if product_ids:
                results = Product.query.filter(Product.id.in_(product_ids)).all()
            else:
                results = []
        else:
            # Fallback naive ILIKE for non-SQLite
            results = Product.query.filter(
                (Product.name.ilike(f"%{q}%")) | (Product.description.ilike(f"%{q}%"))
            ).all()
    return render_template('search/results.html', q=q, results=results)