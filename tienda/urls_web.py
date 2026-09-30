"""Rutas de las páginas HTML (templates). Namespace: 'web'."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views_web as v

app_name = "web"

urlpatterns = [
    # Sesión
    path("login/", auth_views.LoginView.as_view(template_name="tienda/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("registro/", v.RegistroWebView.as_view(), name="registro"),
    # Catálogo público
    path("catalogo/", v.CatalogoLista.as_view(), name="catalogo"),
    path("catalogo/<int:pk>/", v.CatalogoDetalle.as_view(), name="catalogo_detalle"),
    # Carro (cliente)
    path("carro/", v.CarroWeb.as_view(), name="carro"),
    path("carro/agregar/<int:producto_pk>/", v.CarroAgregar.as_view(), name="carro_agregar"),
    path("carro/item/<int:pk>/actualizar/", v.CarroActualizar.as_view(), name="carro_actualizar"),
    path("carro/item/<int:pk>/eliminar/", v.CarroEliminarItem.as_view(), name="carro_eliminar"),
    path("carro/vaciar/", v.CarroVaciar.as_view(), name="carro_vaciar"),
    path("checkout/", v.CheckoutWeb.as_view(), name="checkout"),
    # Mis órdenes (cliente)
    path("mis-ordenes/", v.MisOrdenesLista.as_view(), name="mis_ordenes"),
    path("mis-ordenes/<int:pk>/", v.MisOrdenesDetalle.as_view(), name="mis_ordenes_detalle"),
    path("mis-ordenes/<int:pk>/pagar/", v.PagarOrdenWeb.as_view(), name="mis_ordenes_pagar"),
    # CRUD Categorías (ADMINISTRADOR / SUPERADMIN; eliminar solo SUPERADMIN)
    path("panel/categorias/", v.CategoriaLista.as_view(), name="categoria_lista"),
    path("panel/categorias/nueva/", v.CategoriaCrear.as_view(), name="categoria_crear"),
    path("panel/categorias/<int:pk>/editar/", v.CategoriaEditar.as_view(), name="categoria_editar"),
    path("panel/categorias/<int:pk>/eliminar/", v.CategoriaEliminar.as_view(), name="categoria_eliminar"),
    # CRUD Productos (admin)
    path("panel/productos/", v.ProductoLista.as_view(), name="producto_lista"),
    path("panel/productos/nuevo/", v.ProductoCrear.as_view(), name="producto_crear"),
    path("panel/productos/<int:pk>/editar/", v.ProductoEditar.as_view(), name="producto_editar"),
    path("panel/productos/<int:pk>/eliminar/", v.ProductoEliminar.as_view(), name="producto_eliminar"),
    # Usuarios y roles (solo SUPERADMIN)
    path("panel/usuarios/", v.UsuarioLista.as_view(), name="usuario_lista"),
    path("panel/usuarios/nuevo/", v.UsuarioCrear.as_view(), name="usuario_crear"),
    path("panel/usuarios/<int:pk>/editar/", v.UsuarioEditar.as_view(), name="usuario_editar"),
    path("panel/usuarios/<int:pk>/eliminar/", v.UsuarioEliminar.as_view(), name="usuario_eliminar"),
    # Órdenes (admin)
    path("panel/ordenes/", v.OrdenesAdminLista.as_view(), name="panel_ordenes"),
    path("panel/ordenes/<int:pk>/", v.OrdenesAdminDetalle.as_view(), name="panel_orden_detalle"),
    path("panel/ordenes/<int:pk>/estado/", v.OrdenesAdminEstado.as_view(), name="panel_orden_estado"),
]
