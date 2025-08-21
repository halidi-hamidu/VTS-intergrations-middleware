#!/usr/bin/env python3
"""
CSRF Debug Script for Django Application
This script helps debug CSRF token issues
"""

import os
import sys
import django
from django.conf import settings

# Add the project directory to the path
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'latra_gps.settings')

django.setup()

from django.middleware.csrf import get_token
from django.test import RequestFactory
from django.template.context_processors import csrf

def test_csrf_settings():
    """Test CSRF configuration"""
    print("=== CSRF Configuration Debug ===")
    print(f"DEBUG: {settings.DEBUG}")
    print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    print(f"CSRF_TRUSTED_ORIGINS: {getattr(settings, 'CSRF_TRUSTED_ORIGINS', 'Not set')}")
    print(f"CSRF_COOKIE_SECURE: {getattr(settings, 'CSRF_COOKIE_SECURE', 'Default (False)')}")
    print(f"CSRF_COOKIE_HTTPONLY: {getattr(settings, 'CSRF_COOKIE_HTTPONLY', 'Default (False)')}")
    print(f"CSRF_COOKIE_SAMESITE: {getattr(settings, 'CSRF_COOKIE_SAMESITE', 'Default (Lax)')}")
    print()
    
    # Test CSRF token generation
    factory = RequestFactory()
    request = factory.get('/')
    
    # Add required attributes
    request.session = {}
    request.META['HTTP_HOST'] = 'vts.webgpstracking.co.tz'
    request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
    
    try:
        token = get_token(request)
        print(f"CSRF Token Generated: {token[:16]}... (truncated)")
        print("CSRF token generation: ✓ SUCCESS")
    except Exception as e:
        print(f"CSRF token generation: ✗ FAILED - {e}")
    
    print()
    print("=== Middleware Check ===")
    middlewares = settings.MIDDLEWARE
    csrf_middleware = 'django.middleware.csrf.CsrfViewMiddleware'
    if csrf_middleware in middlewares:
        position = middlewares.index(csrf_middleware)
        print(f"✓ CSRF middleware found at position {position}")
        
        # Check if SessionMiddleware is before CsrfViewMiddleware
        session_middleware = 'django.contrib.sessions.middleware.SessionMiddleware'
        if session_middleware in middlewares:
            session_pos = middlewares.index(session_middleware)
            if session_pos < position:
                print("✓ SessionMiddleware is correctly positioned before CsrfViewMiddleware")
            else:
                print("✗ SessionMiddleware should come before CsrfViewMiddleware")
        else:
            print("✗ SessionMiddleware not found")
    else:
        print("✗ CSRF middleware not found")
    
    print()
    print("=== Domain Check ===")
    trusted_origins = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
    test_domains = [
        'https://vts.webgpstracking.co.tz',
        'http://vts.webgpstracking.co.tz'
    ]
    
    for domain in test_domains:
        if domain in trusted_origins:
            print(f"✓ {domain} is in CSRF_TRUSTED_ORIGINS")
        else:
            print(f"✗ {domain} is NOT in CSRF_TRUSTED_ORIGINS")
    
    print()
    print("=== Recommendations ===")
    if not getattr(settings, 'CSRF_TRUSTED_ORIGINS', None):
        print("• Add CSRF_TRUSTED_ORIGINS to settings.py")
    
    if 'vts.webgpstracking.co.tz' not in settings.ALLOWED_HOSTS:
        print("• Add 'vts.webgpstracking.co.tz' to ALLOWED_HOSTS")
    
    print("• Ensure your login form includes {% csrf_token %}")
    print("• Check browser developer tools for CSRF cookie")
    print("• Verify reverse proxy (nginx) forwards headers correctly")

if __name__ == '__main__':
    test_csrf_settings()
