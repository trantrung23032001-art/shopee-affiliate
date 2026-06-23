# -*- coding: utf-8 -*-
"""
Database Models cho Shopee Affiliate Redirect
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Product(db.Model):
    """Bảng sản phẩm"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500), nullable=False)
    shopee_product_id = db.Column(db.String(100), unique=True, nullable=False)
    shopee_url = db.Column(db.String(1000), nullable=False)
    image_url = db.Column(db.String(1000), default='')
    original_price = db.Column(db.Float, default=0)
    sale_price = db.Column(db.Float, default=0)
    discount_percent = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(200), default='')
    rating = db.Column(db.Float, default=0)
    sold_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    vouchers = db.relationship('Voucher', backref='product', lazy=True)
    clicks = db.relationship('ClickLog', backref='product', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'shopee_product_id': self.shopee_product_id,
            'shopee_url': self.shopee_url,
            'image_url': self.image_url,
            'original_price': self.original_price,
            'sale_price': self.sale_price,
            'discount_percent': self.discount_percent,
            'description': self.description,
            'category': self.category,
            'rating': self.rating,
            'sold_count': self.sold_count,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<Product {self.name}>'


class Voucher(db.Model):
    """Bảng voucher giảm giá"""
    __tablename__ = 'vouchers'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), default='')
    discount_type = db.Column(db.String(50), default='percent')  # percent, fixed
    discount_value = db.Column(db.Float, default=0)
    min_order = db.Column(db.Float, default=0)
    max_discount = db.Column(db.Float, default=0)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        """Kiểm tra voucher còn hiệu lực không"""
        if not self.is_active:
            return False
        now = datetime.utcnow()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'description': self.description,
            'discount_type': self.discount_type,
            'discount_value': self.discount_value,
            'min_order': self.min_order,
            'max_discount': self.max_discount,
            'is_valid': self.is_valid(),
        }

    def __repr__(self):
        return f'<Voucher {self.code}>'


class ClickLog(db.Model):
    """Bảng theo dõi click"""
    __tablename__ = 'click_logs'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'), nullable=True)
    affiliate_url = db.Column(db.String(1000), default='')
    source = db.Column(db.String(100), default='')  # facebook, tiktok, zalo, instagram...
    ip_address = db.Column(db.String(50), default='')
    user_agent = db.Column(db.String(500), default='')
    referrer = db.Column(db.String(1000), default='')
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    voucher = db.relationship('Voucher', backref='clicks')

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'voucher_id': self.voucher_id,
            'affiliate_url': self.affiliate_url,
            'source': self.source,
            'ip_address': self.ip_address,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
        }

    def __repr__(self):
        return f'<ClickLog product={self.product_id} source={self.source}>'


class DailyStats(db.Model):
    """Bảng thống kê theo ngày"""
    __tablename__ = 'daily_stats'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    total_clicks = db.Column(db.Integer, default=0)
    unique_visitors = db.Column(db.Integer, default=0)
    facebook_clicks = db.Column(db.Integer, default=0)
    tiktok_clicks = db.Column(db.Integer, default=0)
    zalo_clicks = db.Column(db.Integer, default=0)
    instagram_clicks = db.Column(db.Integer, default=0)
    other_clicks = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<DailyStats {self.date}>'
