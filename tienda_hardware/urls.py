"""Rutas raíz del proyecto."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from tienda.permissions import EsPersonal
from tienda.views import home

# La documentación OpenAPI (Swagger/Redoc) solo puede verla el personal de la tienda
# (rol ADMINISTRADOR o SUPERADMIN). Se agrega SessionAuthentication para que también
# funcione con la sesión del navegador (tras loguearse en /login/), no solo con JWT.
_auth_docs = [JWTAuthentication, SessionAuthentication]
_permisos_docs = dict(authentication_classes=_auth_docs, permission_classes=[EsPersonal])

urlpatterns = [
    path("", home, name="home"),                      # vista HTML base con footer del alumno (requiere login)
    path("admin/", admin.site.urls),
    path("", include("tienda.urls_web")),             # páginas HTML con templates (CRUD)
    path("api/", include("tienda.urls")),             # todos los endpoints de la tienda
    # Documentación OpenAPI: exclusiva de ADMINISTRADOR y SUPERADMIN
    path("api/schema/", SpectacularAPIView.as_view(**_permisos_docs), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", **_permisos_docs), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema", **_permisos_docs), name="redoc"),
]

# Manejo de errores: página de advertencia cuando la URL / el registro no existe (404) o sin permiso (403)
handler404 = "tienda.views_web.error_404"
handler403 = "tienda.views_web.error_403"
