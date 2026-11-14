import json
from importlib import import_module
from django.conf import settings
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from django.contrib.auth.models import User
out = {}
for u in User.objects.filter(is_staff=True):
    s = import_module(settings.SESSION_ENGINE).SessionStore()
    s[SESSION_KEY] = str(u.pk); s[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
    s[HASH_SESSION_KEY] = u.get_session_auth_hash(); s.set_expiry(6 * 3600); s.save()
    out[u.username] = s.session_key
print('SESSIONS=' + json.dumps(out))
