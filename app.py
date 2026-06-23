# -*- coding: utf-8 -*-
"""
Shopee Affiliate Redirect - Main Flask Application
Luồng: User -> Click link MXH -> Website trung gian -> Lấy thông tin SP+Voucher 
       -> Tạo link affiliate Shopee -> Redirect -> Shopee -> Ghi nhận hoa hồng
"""

import os
import re
from datetime import datetime, date
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for, 
                   jsonify, flash, session, abort)
from werkzeug.security import check_password_hash, generate_password_hash

from config import config
from models import db, Product, Voucher, ClickLog, DailyStats
from shopee_service import shopee_service


def create_app(config_name='default'):
    """Tạo Flask app factory"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Khởi tạo database
    db.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_sample_data()

    # Đăng ký routes
    _register_routes(app)

    return app


def _seed_sample_data():
    """Tạo dữ liệu mẫu nếu database trống"""
    if Product.query.first() is None:
        # Thêm sản phẩm mẫu
        products = [
            Product(
                name='Tai nghe Bluetooth Samsung Galaxy Buds2 Pro',
                shopee_product_id='SP001',
                shopee_url='https://shopee.vn/samsung-galaxy-buds2-pro-i.1234567.10000000',
                image_url='https://down-vn.img.susercontent.com/file/sg-11134201-22110-1q3j5j7v1gjv00',
                original_price=4990000,
                sale_price=2990000,
                discount_percent=40,
                description='Tai nghe không dây True Wireless ANC cao cấp từ Samsung',
                category='Điện tử',
                rating=4.8,
                sold_count=15000,
            ),
            Product(
                name='Sạc nhanh Samsung 45W Type-C',
                shopee_product_id='SP002',
                shopee_url='https://shopee.vn/sac-nhanh-samsung-45w-i.1234567.10000001',
                image_url='https://down-vn.img.susercontent.com/file/sg-11134201-22110-1q3j5j7v1gjv01',
                original_price=890000,
                sale_price=450000,
                discount_percent=49,
                description='Sạc siêu nhanh 45W cho Samsung Galaxy S24 Ultra',
                category='Phụ kiện',
                rating=4.6,
                sold_count=25000,
            ),
            Product(
                name='Ốp lưng Samsung Galaxy S24 Ultra Silicon',
                shopee_product_id='SP003',
                shopee_url='https://shopee.vn/op-lung-samsung-s24-ultra-i.1234567.10000002',
                image_url='https://down-vn.img.susercontent.com/file/sg-11134201-22110-1q3j5j7v1gjv02',
                original_price=350000,
                sale_price=99000,
                discount_percent=72,
                description='Ốp lưng silicon mềm cao cấp bảo vệ điện thoại',
                category='Phụ kiện',
                rating=4.5,
                sold_count=50000,
            ),
        ]
        db.session.add_all(products)

        # Thêm voucher mẫu
        vouchers = [
            Voucher(
                code='SHOPEE50K',
                description='Giảm 50K cho đơn từ 500K',
                discount_type='fixed',
                discount_value=50000,
                min_order=500000,
                max_discount=50000,
                is_active=True,
            ),
            Voucher(
                code='SALE10P',
                description='Giảm 10% tối đa 100K',
                discount_type='percent',
                discount_value=10,
                min_order=200000,
                max_discount=100000,
                is_active=True,
            ),
            Voucher(
                code='FREESHIP',
                description='Miễn phí vận chuyển',
                discount_type='fixed',
                discount_value=30000,
                min_order=0,
                max_discount=30000,
                is_active=True,
            ),
        ]
        db.session.add_all(vouchers)
        db.session.commit()


def _detect_source(referrer=''):
    """Phát hiện nguồn traffic từ referrer"""
    referrer = referrer.lower()
    sources = {
        'facebook': ['facebook.com', 'fb.com', 'm.facebook.com', 'fb.me'],
        'tiktok': ['tiktok.com', 'vt.tiktok.com'],
        'zalo': ['zalo.me', 'zaloapp.com'],
        'instagram': ['instagram.com'],
        'youtube': ['youtube.com', 'youtu.be'],
        'telegram': ['t.me', 'telegram.org'],
    }
    for source, domains in sources.items():
        if any(d in referrer for d in domains):
            return source
    return 'direct'


def _log_click(product_id=None, voucher_id=None, affiliate_url='', source=''):
    """Ghi log click và cập nhật thống kê"""
    # Lấy thông tin request
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    referrer = request.headers.get('Referer', '')

    if not source:
        source = _detect_source(referrer)

    # Tạo log
    click = ClickLog(
        product_id=product_id,
        voucher_id=voucher_id,
        affiliate_url=affiliate_url,
        source=source,
        ip_address=ip,
        user_agent=user_agent,
        referrer=referrer,
    )
    db.session.add(click)

    # Cập nhật thống kê ngày
    today = date.today()
    stats = DailyStats.query.filter_by(date=today).first()
    if not stats:
        stats = DailyStats(
            date=today,
            total_clicks=0,
            unique_visitors=0,
            facebook_clicks=0,
            tiktok_clicks=0,
            zalo_clicks=0,
            instagram_clicks=0,
            other_clicks=0,
        )
        db.session.add(stats)
        db.session.flush()  # Ensure defaults are applied

    stats.total_clicks = (stats.total_clicks or 0) + 1
    source_map = {
        'facebook': 'facebook_clicks',
        'tiktok': 'tiktok_clicks',
        'zalo': 'zalo_clicks',
        'instagram': 'instagram_clicks',
    }
    if source in source_map:
        current_val = getattr(stats, source_map[source]) or 0
        setattr(stats, source_map[source], current_val + 1)
    else:
        stats.other_clicks = (stats.other_clicks or 0) + 1

    db.session.commit()
    return click


def _admin_required(f):
    """Decorator kiểm tra đăng nhập admin"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Vui lòng đăng nhập!', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def _register_routes(app):
    """Đăng ký tất cả routes"""

    # ==================== PUBLIC ROUTES ====================

    @app.route('/')
    def index():
        """Trang chủ - Hiển thị danh sách sản phẩm"""
        products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
        vouchers = Voucher.query.filter_by(is_active=True).all()
        return render_template('index.html', products=products, vouchers=vouchers)

    @app.route('/p/<int:product_id>')
    def product_page(product_id):
        """
        Trang trung gian - Hiển thị thông tin sản phẩm + voucher
        Sau đó tự động redirect sang Shopee affiliate link
        Đây là luồng chính: User click link -> Trang này -> Redirect Shopee
        """
        product = Product.query.get_or_404(product_id)

        if not product.is_active:
            abort(404)

        # Lấy voucher áp dụng cho sản phẩm hoặc voucher toàn sàn
        vouchers = Voucher.query.filter(
            db.or_(
                Voucher.product_id == product_id,
                db.and_(Voucher.product_id.is_(None), Voucher.is_active == True)
            )
        ).all()

        # Lấy source từ query param hoặc detect từ referrer
        source = request.args.get('source', '')
        referrer = request.headers.get('Referer', '')
        if not source:
            source = _detect_source(referrer)

        # Tạo affiliate URL
        affiliate_url = shopee_service.generate_direct_affiliate_url(product.shopee_url)

        # Ghi log click
        _log_click(
            product_id=product_id,
            affiliate_url=affiliate_url,
            source=source,
        )

        # Render trang trung gian với auto redirect
        return render_template(
            'product.html',
            product=product,
            vouchers=vouchers,
            affiliate_url=affiliate_url,
            redirect_delay=app.config.get('REDIRECT_DELAY', 3),
            source=source,
        )

    @app.route('/p/<int:product_id>/redirect')
    def product_redirect(product_id):
        """Redirect trực tiếp sang Shopee (không hiển thị trang trung gian)"""
        product = Product.query.get_or_404(product_id)
        source = request.args.get('source', '')
        voucher_code = request.args.get('voucher', '')

        # Tạo affiliate URL
        affiliate_url = shopee_service.generate_direct_affiliate_url(product.shopee_url)

        # Nếu có voucher, thêm vào URL
        if voucher_code:
            affiliate_url += f"&voucher={voucher_code}"

        # Ghi log
        _log_click(
            product_id=product_id,
            affiliate_url=affiliate_url,
            source=source,
        )

        return redirect(affiliate_url)

    @app.route('/go/<shopee_product_id>')
    def quick_redirect(shopee_product_id):
        """
        Quick redirect - Dùng cho link ngắn
        Format: /go/SP001 -> Redirect thẳng sang Shopee
        """
        product = Product.query.filter_by(shopee_product_id=shopee_product_id).first_or_404()
        source = request.args.get('source', '')

        affiliate_url = shopee_service.generate_direct_affiliate_url(product.shopee_url)

        _log_click(
            product_id=product.id,
            affiliate_url=affiliate_url,
            source=source,
        )

        return redirect(affiliate_url)

    @app.route('/v/<voucher_code>')
    def voucher_page(voucher_code):
        """Trang hiển thị voucher + sản phẩm áp dụng"""
        voucher = Voucher.query.filter_by(code=voucher_code).first_or_404()

        if voucher.product_id:
            products = [Product.query.get(voucher.product_id)]
        else:
            products = Product.query.filter_by(is_active=True).limit(10).all()

        return render_template('voucher.html', voucher=voucher, products=products)

    @app.route('/robots.txt')
    def robots_txt():
        """SEO: robots.txt cho Googlebot"""
        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        robots = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: {base_url}/sitemap.xml
"""
        return app.response_class(robots, mimetype='text/plain')

    @app.route('/sitemap.xml')
    def sitemap_xml():
        """SEO: sitemap.xml cho Google"""
        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        products = Product.query.filter_by(is_active=True).all()
        vouchers = Voucher.query.filter_by(is_active=True).all()

        urls = [f"""
  <url>
    <loc>{base_url}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""]

        for p in products:
            urls.append(f"""
  <url>
    <loc>{base_url}/p/{p.id}</loc>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""")

        for v in vouchers:
            urls.append(f"""
  <url>
    <loc>{base_url}/v/{v.code}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>""")

        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{''.join(urls)}
</urlset>"""
        return app.response_class(sitemap, mimetype='application/xml')

    @app.route('/api/generate-link', methods=['POST'])
    def api_generate_link():
        """API tạo affiliate link (AJAX)"""
        data = request.get_json()
        product_url = data.get('product_url', '')
        voucher_code = data.get('voucher_code', '')

        if not product_url:
            return jsonify({'error': 'Thiếu product_url'}), 400

        # Thử tạo link qua API trước
        result = shopee_service.generate_affiliate_link(product_url, voucher_code)

        if result:
            return jsonify({'success': True, 'data': result})

        # Fallback: tạo link trực tiếp
        affiliate_url = shopee_service.generate_direct_affiliate_url(product_url)
        return jsonify({'success': True, 'data': {'affiliate_url': affiliate_url}})

    # ==================== ADMIN ROUTES ====================

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        """Đăng nhập admin"""
        if request.method == 'POST':
            username = request.form.get('username', '')
            password = request.form.get('password', '')

            if (username == app.config['ADMIN_USERNAME'] and
                    password == app.config['ADMIN_PASSWORD']):
                session['admin_logged_in'] = True
                flash('Đăng nhập thành công!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Sai tên đăng nhập hoặc mật khẩu!', 'error')

        return render_template('admin/login.html')

    @app.route('/admin/logout')
    def admin_logout():
        """Đăng xuất admin"""
        session.pop('admin_logged_in', None)
        flash('Đã đăng xuất!', 'info')
        return redirect(url_for('admin_login'))

    @app.route('/admin')
    @_admin_required
    def admin_dashboard():
        """Dashboard admin"""
        total_products = Product.query.filter_by(is_active=True).count()
        total_vouchers = Voucher.query.filter_by(is_active=True).count()
        total_clicks = ClickLog.query.count()
        today_clicks = ClickLog.query.filter(
            db.func.date(ClickLog.clicked_at) == date.today()
        ).count()

        # Thống kê 7 ngày gần nhất
        stats = DailyStats.query.order_by(DailyStats.date.desc()).limit(7).all()

        # Click theo nguồn
        source_stats = db.session.query(
            ClickLog.source, db.func.count(ClickLog.id)
        ).group_by(ClickLog.source).all()

        # Sản phẩm click nhiều nhất
        top_products = db.session.query(
            Product.name, db.func.count(ClickLog.id).label('clicks')
        ).join(ClickLog).group_by(Product.id).order_by(
            db.text('clicks DESC')
        ).limit(5).all()

        return render_template('admin/dashboard.html',
                               total_products=total_products,
                               total_vouchers=total_vouchers,
                               total_clicks=total_clicks,
                               today_clicks=today_clicks,
                               stats=stats,
                               source_stats=source_stats,
                               top_products=top_products)

    @app.route('/admin/products')
    @_admin_required
    def admin_products():
        """Quản lý sản phẩm"""
        products = Product.query.order_by(Product.created_at.desc()).all()
        return render_template('admin/products.html', products=products)

    @app.route('/admin/products/add', methods=['GET', 'POST'])
    @_admin_required
    def admin_product_add():
        """Thêm sản phẩm mới"""
        if request.method == 'POST':
            product = Product(
                name=request.form.get('name'),
                shopee_product_id=request.form.get('shopee_product_id'),
                shopee_url=request.form.get('shopee_url'),
                image_url=request.form.get('image_url', ''),
                original_price=float(request.form.get('original_price', 0)),
                sale_price=float(request.form.get('sale_price', 0)),
                discount_percent=int(request.form.get('discount_percent', 0)),
                description=request.form.get('description', ''),
                category=request.form.get('category', ''),
                rating=float(request.form.get('rating', 0)),
                sold_count=int(request.form.get('sold_count', 0)),
            )
            db.session.add(product)
            db.session.commit()
            flash('Thêm sản phẩm thành công!', 'success')
            return redirect(url_for('admin_products'))

        return render_template('admin/product_form.html', product=None)

    @app.route('/admin/products/<int:id>/edit', methods=['GET', 'POST'])
    @_admin_required
    def admin_product_edit(id):
        """Sửa sản phẩm"""
        product = Product.query.get_or_404(id)

        if request.method == 'POST':
            product.name = request.form.get('name')
            product.shopee_product_id = request.form.get('shopee_product_id')
            product.shopee_url = request.form.get('shopee_url')
            product.image_url = request.form.get('image_url', '')
            product.original_price = float(request.form.get('original_price', 0))
            product.sale_price = float(request.form.get('sale_price', 0))
            product.discount_percent = int(request.form.get('discount_percent', 0))
            product.description = request.form.get('description', '')
            product.category = request.form.get('category', '')
            product.rating = float(request.form.get('rating', 0))
            product.sold_count = int(request.form.get('sold_count', 0))
            product.is_active = 'is_active' in request.form
            db.session.commit()
            flash('Cập nhật sản phẩm thành công!', 'success')
            return redirect(url_for('admin_products'))

        return render_template('admin/product_form.html', product=product)

    @app.route('/admin/products/<int:id>/delete', methods=['POST'])
    @_admin_required
    def admin_product_delete(id):
        """Xóa sản phẩm"""
        product = Product.query.get_or_404(id)
        product.is_active = False
        db.session.commit()
        flash('Đã ẩn sản phẩm!', 'info')
        return redirect(url_for('admin_products'))

    @app.route('/admin/vouchers')
    @_admin_required
    def admin_vouchers():
        """Quản lý voucher"""
        vouchers = Voucher.query.order_by(Voucher.created_at.desc()).all()
        return render_template('admin/vouchers.html', vouchers=vouchers)

    @app.route('/admin/vouchers/add', methods=['GET', 'POST'])
    @_admin_required
    def admin_voucher_add():
        """Thêm voucher mới"""
        products = Product.query.filter_by(is_active=True).all()
        if request.method == 'POST':
            voucher = Voucher(
                code=request.form.get('code'),
                description=request.form.get('description', ''),
                discount_type=request.form.get('discount_type', 'percent'),
                discount_value=float(request.form.get('discount_value', 0)),
                min_order=float(request.form.get('min_order', 0)),
                max_discount=float(request.form.get('max_discount', 0)),
                is_active='is_active' in request.form,
                product_id=int(request.form.get('product_id')) if request.form.get('product_id') else None,
            )
            db.session.add(voucher)
            db.session.commit()
            flash('Thêm voucher thành công!', 'success')
            return redirect(url_for('admin_vouchers'))

        return render_template('admin/voucher_form.html', voucher=None, products=products)

    @app.route('/admin/vouchers/<int:id>/edit', methods=['GET', 'POST'])
    @_admin_required
    def admin_voucher_edit(id):
        """Sửa voucher"""
        voucher = Voucher.query.get_or_404(id)
        products = Product.query.filter_by(is_active=True).all()

        if request.method == 'POST':
            voucher.code = request.form.get('code')
            voucher.description = request.form.get('description', '')
            voucher.discount_type = request.form.get('discount_type', 'percent')
            voucher.discount_value = float(request.form.get('discount_value', 0))
            voucher.min_order = float(request.form.get('min_order', 0))
            voucher.max_discount = float(request.form.get('max_discount', 0))
            voucher.is_active = 'is_active' in request.form
            voucher.product_id = int(request.form.get('product_id')) if request.form.get('product_id') else None
            db.session.commit()
            flash('Cập nhật voucher thành công!', 'success')
            return redirect(url_for('admin_vouchers'))

        return render_template('admin/voucher_form.html', voucher=voucher, products=products)

    @app.route('/admin/vouchers/<int:id>/delete', methods=['POST'])
    @_admin_required
    def admin_voucher_delete(id):
        """Xóa voucher"""
        voucher = Voucher.query.get_or_404(id)
        db.session.delete(voucher)
        db.session.commit()
        flash('Đã xóa voucher!', 'info')
        return redirect(url_for('admin_vouchers'))

    @app.route('/admin/clicks')
    @_admin_required
    def admin_clicks():
        """Xem log click"""
        page = request.args.get('page', 1, type=int)
        per_page = 20
        pagination = ClickLog.query.order_by(ClickLog.clicked_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return render_template('admin/clicks.html', clicks=pagination.items,
                               pagination=pagination)

    @app.route('/admin/links')
    @_admin_required
    def admin_links():
        """Quản lý link - Tạo link chia sẻ"""
        products = Product.query.filter_by(is_active=True).all()
        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        return render_template('admin/links.html', products=products, base_url=base_url)


# ==================== RUN APP ====================

if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)
