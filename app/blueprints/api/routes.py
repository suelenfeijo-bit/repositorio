from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import text

from app.models import db, Product, Order, OrderItem

api_bp = Blueprint('api', __name__)


@api_bp.get('/products')
def api_products():
    q = (request.args.get('q') or '').strip()
    query = Product.query.filter_by(active=True)
    if q:
        query = query.filter((Product.name.ilike(f"%{q}%")) | (Product.description.ilike(f"%{q}%")))
    products = query.order_by(Product.created_at.desc()).limit(50).all()
    return {"products": [
        {"id": p.id, "name": p.name, "price_cents": p.price_cents, "currency": p.currency}
        for p in products
    ]}


@api_bp.get('/purchases')
@jwt_required()
def api_purchases():
    user_id = int(get_jwt_identity())
    orders = Order.query.filter_by(user_id=user_id, status='paid').order_by(Order.created_at.desc()).limit(20).all()
    data = []
    for order in orders:
        items = []
        for item in order.items:
            items.append({
                'product_id': item.product_id,
                'name': item.product.name,
                'quantity': item.quantity,
                'unit_price_cents': item.unit_price_cents,
            })
        data.append({'order_id': order.id, 'total_cents': order.total_cents, 'currency': order.currency, 'items': items})
    return {"orders": data}