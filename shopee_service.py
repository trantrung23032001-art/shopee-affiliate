# -*- coding: utf-8 -*-
"""
Shopee Affiliate API Service
Xử lý tạo link affiliate và tương tác với Shopee API
"""

import hashlib
import hmac
import time
import requests
from flask import current_app


class ShopeeAffiliateService:
    """Service xử lý Shopee Affiliate API"""

    def __init__(self):
        self.api_url = None
        self.app_id = None
        self.app_secret = None

    def _get_config(self):
        """Lấy config từ Flask app context"""
        self.api_url = current_app.config.get('SHOPEE_AFFILIATE_API_URL')
        self.app_id = current_app.config.get('SHOPEE_APP_ID')
        self.app_secret = current_app.config.get('SHOPEE_APP_SECRET')

    def _generate_sign(self, request_path, timestamp, access_token=None):
        """Tạo chữ ký cho API request"""
        self._get_config()
        base_string = f"{self.app_id}{timestamp}{access_token or ''}{request_path}"
        sign = hmac.new(
            self.app_secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return sign

    def _make_request(self, method, path, params=None, data=None):
        """Gửi request đến Shopee API"""
        self._get_config()
        timestamp = int(time.time())
        sign = self._generate_sign(path, timestamp)

        headers = {
            'Content-Type': 'application/json',
            'X-Shopee-App-Id': str(self.app_id),
            'X-Shopee-Timestamp': str(timestamp),
            'X-Shopee-Sign': sign,
        }

        url = f"{self.api_url}{path}"

        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=10)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                current_app.logger.error(f"Shopee API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            current_app.logger.error(f"Shopee API exception: {str(e)}")
            return None

    def generate_affiliate_link(self, product_url, voucher_code=None):
        """
        Tạo link affiliate từ URL sản phẩm Shopee
        
        Args:
            product_url: URL sản phẩm Shopee gốc
            voucher_code: Mã voucher (nếu có)
        
        Returns:
            dict: { 'affiliate_url': '...', 'short_url': '...' } hoặc None
        """
        data = {
            'product_url': product_url,
        }
        if voucher_code:
            data['voucher_code'] = voucher_code

        result = self._make_request('POST', '/affiliate/generate_link', data=data)
        
        if result and result.get('code') == 0:
            return result.get('data', {})
        return None

    def get_product_info(self, product_id):
        """
        Lấy thông tin sản phẩm từ Shopee
        
        Args:
            product_id: ID sản phẩm Shopee
        
        Returns:
            dict thông tin sản phẩm hoặc None
        """
        params = {
            'product_id': product_id,
        }
        result = self._make_request('GET', '/affiliate/product_info', params=params)
        
        if result and result.get('code') == 0:
            return result.get('data', {})
        return None

    def generate_direct_affiliate_url(self, shopee_url, affiliate_id=None):
        self._get_config()
        aid = affiliate_id or self.app_id or ''
        if aid and aid != 'YOUR_AFFILIATE_ID':
            import urllib.parse
            encoded_url = urllib.parse.quote(shopee_url, safe='')
            return f"https://shope.ee/aff/{aid}?url={encoded_url}"
        return shopee_url


# Singleton instance
shopee_service = ShopeeAffiliateService()
