"""
Configuración del proyecto TechHardware (Proyecto 1 - EVA-2 Backend).

Bloques principales:
  1. Datos del alumno (se muestran en el footer y en Swagger).
  2. Apps instaladas.
  3. Base de datos PostgreSQL (motor django.db.backends.postgresql).
  4. Django REST Framework + JWT + django-filter + drf-spectacular.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 1. DATOS DEL ALUMNO (footer obligatorio de la pauta)  <-- EDITAR
# ---------------------------------------------------------------------------
ALUMNO_NOMBRE = "Diego Ignacio Aros Huencho"
ALUMNO_SECCION = "Sección AP-N4-C2"
ALUMNO_ANIO = "2026"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-clave-insegura-cambiar-en-produccion")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# 2. APLICACIONES
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # permite invalidar refresh tokens en el logout
    "django_filters",
    "drf_spectacular",
    # Aplicación propia
    "tienda.apps.TiendaConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "tienda.middleware.Manejo404Middleware",  # reemplaza todo 404 por la advertencia "la página no existe"
]

ROOT_URLCONF = "tienda_hardware.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "tienda.context_processors.datos_globales",  # datos del alumno + rol en todas las plantillas
            ],
        },
    },
]

WSGI_APPLICATION = "tienda_hardware.wsgi.application"

# ---------------------------------------------------------------------------
# 3. BASE DE DATOS: PostgreSQL (NO SQLite)
#    Los valores pueden sobreescribirse con variables de entorno.
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "tienda_hardware_db"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "12345"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# Sin validadores: se acepta cualquier contraseña (sin largo mínimo ni reglas)
AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Sesión para las páginas HTML (la API sigue usando JWT)
LOGIN_URL = "web:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# 4. DJANGO REST FRAMEWORK
#    - Autenticación: JWT (Authorization: Bearer <access>)
#    - Filtros globales: django-filter + búsqueda + ordenamiento
#    - Esquema OpenAPI: drf-spectacular
#    Los permisos se definen vista por vista (ver tienda/permissions.py).
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Vida útil de los tokens JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Documentación Swagger / OpenAPI (se sirve en /api/docs/)
SPECTACULAR_SETTINGS = {
    "TITLE": "TechHardware API - Tienda de Hardware y Componentes PC",
    "DESCRIPTION": (
        "API REST de e-commerce de componentes informáticos.\n\n"
        f"**Alumno:** {ALUMNO_NOMBRE} | **Sección:** {ALUMNO_SECCION} | **Año:** {ALUMNO_ANIO}\n\n"
        "Para probar endpoints protegidos: obtenga el token en `/api/auth/login/`, "
        "presione **Authorize** e ingrese `Bearer <access>`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
}
