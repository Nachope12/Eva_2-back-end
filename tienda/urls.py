"""Rutas de la API (prefijo /api/)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

# El router genera automáticamente list/retrieve/create/update/destroy.
router = DefaultRouter()
router.register("productos", views.ProductoViewSet, basename="producto")
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("usuarios", views.UsuarioViewSet, basename="usuario")  # solo SUPERADMIN

urlpatterns = [
    # Autenticación
    path("auth/registro/", views.RegistroView.as_view(), name="registro"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    # Carro persistente
    path("carro/", views.CarroView.as_view(), name="carro"),
    # Checkout y órdenes
    path("ordenes/checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("ordenes/<int:pk>/pagar/", views.PagarOrdenView.as_view(), name="orden-pagar"),
    path("ordenes/<int:pk>/estado/", views.CambiarEstadoOrdenView.as_view(), name="orden-estado"),
    path("ordenes/", views.TodasLasOrdenesView.as_view(), name="ordenes-admin"),
    path("mis-ordenes/", views.MisOrdenesView.as_view(), name="mis-ordenes"),
    # Catálogo (productos y categorías)
    path("", include(router.urls)),
]
