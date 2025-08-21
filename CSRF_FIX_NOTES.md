# CSRF Error Fix Summary

## Problem
- Users getting "Forbidden (403) CSRF verification failed" when trying to login via https://vts.webgpstracking.co.tz/

## Root Cause
Django's CSRF protection was not recognizing the domain `vts.webgpstracking.co.tz` as trusted.

## Fixes Applied

### 1. Updated ALLOWED_HOSTS in settings.py
```python
ALLOWED_HOSTS = ['93.127.139.107', 'localhost', '127.0.0.1', '0.0.0.0', 'vts.webgpstracking.co.tz']
```

### 2. Added CSRF_TRUSTED_ORIGINS
```python
CSRF_TRUSTED_ORIGINS = [
    'https://vts.webgpstracking.co.tz',
    'http://vts.webgpstracking.co.tz', 
    'https://93.127.139.107',
    'http://93.127.139.107',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
```

### 3. Added Security Headers Support
```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

### 4. Added Cookie Security Settings
```python
SESSION_COOKIE_SECURE = False  # Set to True if using HTTPS only
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

CSRF_COOKIE_SECURE = False  # Set to True if using HTTPS only
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
```

### 5. Added Debug Logging
Added logging for CSRF and request debugging to help troubleshoot future issues.

## Additional Troubleshooting Steps

### If the issue persists:

1. **Clear Browser Cache and Cookies**
   - Clear all cookies for the domain
   - Hard refresh (Ctrl+F5)

2. **Check Browser Developer Tools**
   - Go to Network tab
   - Look for CSRF cookie in request headers
   - Check if csrftoken cookie is set

3. **Test in Incognito/Private Mode**
   - This eliminates cached cookie issues

4. **Check Reverse Proxy Configuration (Nginx)**
   Make sure your nginx configuration forwards the correct headers:
   ```nginx
   proxy_set_header Host $host;
   proxy_set_header X-Real-IP $remote_addr;
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header X-Forwarded-Proto $scheme;
   ```

5. **Check Docker Container Logs**
   ```bash
   sudo docker compose logs web
   ```

6. **Verify Login Form Has CSRF Token**
   The login.html template should have `{% csrf_token %}` inside the form tag (✓ Already verified)

## Testing
Try accessing https://vts.webgpstracking.co.tz/ now and attempt to login.

## Security Notes
- In production, set CSRF_COOKIE_SECURE = True and SESSION_COOKIE_SECURE = True when using HTTPS
- Consider setting DEBUG = False in production
- The current settings allow both HTTP and HTTPS for flexibility during testing
