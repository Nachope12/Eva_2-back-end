"""Punto de entrada WSGI del proyecto."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tienda_hardware.settings")
application = get_wsgi_application()
