# -*- coding: utf-8 -*-
"""
Cấu hình hệ thống Shopee Affiliate Redirect
"""

import os

class Config:
    """Cấu hình chính của ứng dụng"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'shopee-affiliate-secret-key-change-in-production')
    
    # Database
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'affiliate.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Shopee Affiliate API
    SHOPEE_AFFILIATE_API_URL = 'https://open-api.affiliate.shopee.vn/api/v1'
    SHOPEE_APP_ID = os.environ.get('SHOPEE_APP_ID', 'YOUR_APP_ID')
    SHOPEE_APP_SECRET = os.environ.get('SHOPEE_APP_SECRET', 'YOUR_APP_SECRET')
    SHOPEE_AFFILIATE_ID = os.environ.get('SHOPEE_AFFILIATE_ID', 'YOUR_AFFILIATE_ID')
    
    # Redirect settings
    REDIRECT_DELAY = 3  # seconds before redirect (show product info first)
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Admin
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
