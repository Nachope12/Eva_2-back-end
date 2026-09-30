"""
Vistas WEB (HTML con templates) del sistema. Usan autenticación por SESIÓN de Django
(la API REST usa JWT). Implementan los CRUD completos:

  ADMINISTRADOR:  CRUD Categorías, CRUD Productos, gestión de Órdenes (cambio de estado).
  CLIENTE:        Carro persistente (agregar / modificar / eliminar), checkout, pago, mis órdenes.
  PÚBLICO:        Catálogo con filtros (django-filter) y detalle de producto.

Control de errores: un registro inexistente lanza Http404 y el middleware
(tienda/middleware.py) muestra la plantilla 404.html con la advertencia.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from rest_framework.exceptions import ValidationError

from . import services
from .filters import OrdenFilter, ProductoFilter
from .forms import CantidadForm, CategoriaForm, EstadoForm, ProductoForm, RegistroForm, UsuarioForm
from .models import Carro, Categoria, ItemCarro, Orden, Perfil, Producto
from .permissions import ESTADOS_PERMITIDOS, PERSONAL, rol_de_usuario

User = get_user_model()


# ------------------------------ UTILIDADES ---------------------------------
def error_404(request, exception=None):
    """handler404 de Django (DEBUG=False): muestra la advertencia de página inexistente."""
    return render(request, "tienda/404.html", status=404)


def error_403(request, exception=None):
    """handler403: usuario autenticado sin el rol necesario."""
    return render(request, "tienda/403.html", status=403)


def _mensajes(exc):
    """Convierte el detalle de un ValidationError de DRF en una lista de textos."""
    detalle = exc.detail
    if isinstance(detalle, dict):
        items = [x for v in detalle.values() for x in (v if isinstance(v, list) else [v])]
    elif isinstance(detalle, list):
        items = detalle
    else:
        items = [detalle]
    return [str(i) for i in items]


def _querystring_sin_pagina(request):
    """Conserva los filtros al cambiar de página en la paginación."""
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


class SoloPersonal(LoginRequiredMixin, UserPassesTestMixin):
    """ADMINISTRADOR o SUPERADMIN (panel de gestión). Anónimo -> login; otro rol -> 403."""

    def test_func(self):
        return rol_de_usuario(self.request.user) in PERSONAL


class SoloSuperAdmin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo SUPERADMIN (eliminar registros, gestionar usuarios, cancelar/pagar órdenes)."""

    def test_func(self):
        return rol_de_usuario(self.request.user) == Perfil.Rol.SUPERADMIN


class SoloCliente(LoginRequiredMixin, UserPassesTestMixin):
    """Acceso solo para rol CLIENTE."""

    def test_func(self):
        return rol_de_usuario(self.request.user) == Perfil.Rol.CLIENTE


class ListaFiltradaMixin:
    """Agrega el querystring de filtros al contexto para la paginación."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["querystring"] = _querystring_sin_pagina(self.request)
        return ctx


# -------------------------- REGISTRO DE USUARIOS ---------------------------
class RegistroWebView(SuccessMessageMixin, CreateView):
    form_class = RegistroForm
    template_name = "tienda/registro.html"
    success_url = reverse_lazy("web:login")
    success_message = "Cuenta creada correctamente. Ya puede iniciar sesión."


# ------------------------------ CATÁLOGO (público) -------------------------
class CatalogoLista(ListaFiltradaMixin, FilterView):
    """Listado público con filtros django-filter (categoría, marca, rango de precio...)."""
    filterset_class = ProductoFilter
    queryset = Producto.objects.filter(activo=True).select_related("categoria")
    template_name = "tienda/catalogo_lista.html"
    paginate_by = 9


class CatalogoDetalle(DetailView):
    queryset = Producto.objects.filter(activo=True).select_related("categoria")
    template_name = "tienda/catalogo_detalle.html"
    extra_context = {"form": CantidadForm()}


# ------------------------- CRUD CATEGORÍAS (admin) -------------------------
class CategoriaLista(SoloPersonal, ListView):
    template_name = "tienda/categoria_lista.html"
    paginate_by = 20

    def get_queryset(self):
        return Categoria.objects.annotate(total_productos=Count("productos")).order_by("nombre")


class CategoriaCrear(SoloPersonal, SuccessMessageMixin, CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = "tienda/crud_form.html"
    success_url = reverse_lazy("web:categoria_lista")
    success_message = "Categoría creada correctamente."
    extra_context = {"titulo": "Nueva categoría", "volver": reverse_lazy("web:categoria_lista")}


class CategoriaEditar(SoloPersonal, SuccessMessageMixin, UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = "tienda/crud_form.html"
    success_url = reverse_lazy("web:categoria_lista")
    success_message = "Categoría actualizada correctamente."
    extra_context = {"titulo": "Editar categoría", "volver": reverse_lazy("web:categoria_lista")}


class EliminarProtegido(DeleteView):
    """
    DELETE con control de integridad referencial: si el registro está protegido por una
    ForeignKey (on_delete=PROTECT) se informa el motivo en vez de fallar con error 500.
    """
    template_name = "tienda/crud_eliminar.html"
    mensaje_ok = "Registro eliminado."
    mensaje_bloqueo = "No se puede eliminar: tiene registros asociados."
    url_volver = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["volver"] = reverse(self.url_volver)
        return ctx

    def form_valid(self, form):
        destino = reverse(self.url_volver)
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(self.request, self.mensaje_bloqueo)
            return redirect(destino)
        messages.success(self.request, self.mensaje_ok)
        return redirect(destino)


class CategoriaEliminar(SoloSuperAdmin, EliminarProtegido):
    model = Categoria
    url_volver = "web:categoria_lista"
    mensaje_ok = "Categoría eliminada."
    mensaje_bloqueo = "No se puede eliminar la categoría porque tiene productos asociados."


# -------------------------- CRUD PRODUCTOS (admin) -------------------------
class ProductoLista(SoloPersonal, ListaFiltradaMixin, FilterView):
    filterset_class = ProductoFilter
    queryset = Producto.objects.select_related("categoria")  # el admin ve también los inactivos
    template_name = "tienda/producto_lista.html"
    paginate_by = 15


class ProductoCrear(SoloPersonal, SuccessMessageMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = "tienda/crud_form.html"
    success_url = reverse_lazy("web:producto_lista")
    success_message = "Producto creado correctamente."
    extra_context = {"titulo": "Nuevo producto", "volver": reverse_lazy("web:producto_lista")}


class ProductoEditar(SoloPersonal, SuccessMessageMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = "tienda/crud_form.html"
    success_url = reverse_lazy("web:producto_lista")
    success_message = "Producto actualizado correctamente."
    extra_context = {"titulo": "Editar producto", "volver": reverse_lazy("web:producto_lista")}


class ProductoEliminar(SoloSuperAdmin, EliminarProtegido):
    model = Producto
    url_volver = "web:producto_lista"
    mensaje_ok = "Producto eliminado."
    mensaje_bloqueo = "No se puede eliminar: el producto figura en órdenes históricas. Desactívelo en su lugar."


# ------------------------------ CARRO (cliente) ----------------------------
class CarroWeb(SoloCliente, TemplateView):
    """Muestra el carro persistente (guardado en PostgreSQL, sobrevive al logout)."""
    template_name = "tienda/carro.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        carro, _ = Carro.objects.get_or_create(usuario=self.request.user)
        ctx["carro"] = carro
        ctx["items"] = carro.items.select_related("producto")
        ctx["total"] = carro.total()
        ctx["form"] = CantidadForm()
        return ctx


class CarroAgregar(SoloCliente, View):
    """CREATE del carro: agrega un producto (si ya existe, suma la cantidad)."""

    def post(self, request, producto_pk):
        producto = get_object_or_404(Producto, pk=producto_pk, activo=True)
        form = CantidadForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Cantidad inválida.")
            return redirect("web:catalogo_detalle", pk=producto.pk)
        carro, _ = Carro.objects.get_or_create(usuario=request.user)
        item, creado = ItemCarro.objects.get_or_create(
            carro=carro, producto=producto, defaults={"cantidad": form.cleaned_data["cantidad"]}
        )
        if not creado:
            item.cantidad += form.cleaned_data["cantidad"]
            item.save(update_fields=["cantidad"])
        messages.success(request, f"«{producto.nombre}» agregado al carro.")
        return redirect("web:carro")


class CarroActualizar(SoloCliente, View):
    """UPDATE del carro: cambia la cantidad de un ítem (solo del carro propio)."""

    def post(self, request, pk):
        item = get_object_or_404(ItemCarro, pk=pk, carro__usuario=request.user)
        form = CantidadForm(request.POST)
        if form.is_valid():
            item.cantidad = form.cleaned_data["cantidad"]
            item.save(update_fields=["cantidad"])
            messages.success(request, "Cantidad actualizada.")
        else:
            messages.error(request, "Cantidad inválida.")
        return redirect("web:carro")


class CarroEliminarItem(SoloCliente, View):
    """DELETE del carro: quita un ítem."""

    def post(self, request, pk):
        item = get_object_or_404(ItemCarro, pk=pk, carro__usuario=request.user)
        item.delete()
        messages.success(request, "Producto quitado del carro.")
        return redirect("web:carro")


class CarroVaciar(SoloCliente, View):
    def post(self, request):
        ItemCarro.objects.filter(carro__usuario=request.user).delete()
        messages.success(request, "Carro vaciado.")
        return redirect("web:carro")


# --------------------------- CHECKOUT Y ÓRDENES ----------------------------
class CheckoutWeb(SoloCliente, View):
    """
    modo=comprar   -> checkout + pago atómico: la orden queda PAGADO y el INVENTARIO se actualiza.
    modo=pendiente -> solo genera la orden PENDIENTE (no descuenta stock hasta pagar).
    Si falta stock, no se crea nada y el carro queda intacto.
    """

    def post(self, request):
        comprar = request.POST.get("modo", "comprar") == "comprar"
        try:
            if comprar:
                orden = services.comprar_desde_carro(request.user)
            else:
                orden = services.checkout_desde_carro(request.user)
        except ValidationError as exc:
            for m in _mensajes(exc):
                messages.error(request, m)
            return redirect("web:carro")
        if comprar:
            messages.success(request, f"¡Compra realizada! Orden #{orden.pk} pagada; el inventario fue actualizado.")
        else:
            messages.success(request, f"Orden #{orden.pk} generada como PENDIENTE. Puede pagarla desde su detalle.")
        return redirect("web:mis_ordenes_detalle", pk=orden.pk)


class MisOrdenesLista(SoloCliente, ListaFiltradaMixin, FilterView):
    filterset_class = OrdenFilter
    template_name = "tienda/orden_lista.html"
    paginate_by = 15
    extra_context = {"es_panel": False}

    def get_queryset(self):
        return Orden.objects.filter(usuario=self.request.user).select_related("usuario")


class MisOrdenesDetalle(SoloCliente, DetailView):
    template_name = "tienda/orden_detalle.html"
    extra_context = {"es_panel": False}

    def get_queryset(self):
        # Un cliente solo puede ver SUS órdenes; las ajenas responden 404.
        return Orden.objects.filter(usuario=self.request.user).prefetch_related("items__producto")


class PagarOrdenWeb(SoloCliente, View):
    """Pago simulado: valida y descuenta stock de forma atómica (services.cambiar_estado_orden)."""

    def post(self, request, pk):
        try:
            services.cambiar_estado_orden(pk, Orden.Estado.PAGADO, usuario=request.user)
            messages.success(request, "Pago confirmado. Stock descontado.")
        except ValidationError as exc:
            for m in _mensajes(exc):
                messages.error(request, m)
        return redirect("web:mis_ordenes_detalle", pk=pk)


# ------------------------- ÓRDENES (administrador) -------------------------
class OrdenesAdminLista(SoloPersonal, ListaFiltradaMixin, FilterView):
    filterset_class = OrdenFilter
    queryset = Orden.objects.select_related("usuario")
    template_name = "tienda/orden_lista.html"
    paginate_by = 15
    extra_context = {"es_panel": True}


class OrdenesAdminDetalle(SoloPersonal, DetailView):
    queryset = Orden.objects.select_related("usuario").prefetch_related("items__producto")
    template_name = "tienda/orden_detalle.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Solo se ofrecen las transiciones válidas según la máquina de estados Y según el rol.
        rol = rol_de_usuario(self.request.user)
        permitidas = services.TRANSICIONES[self.object.estado] & ESTADOS_PERMITIDOS.get(rol, set())
        ctx["es_panel"] = True
        ctx["transiciones"] = [(e.value, e.label) for e in Orden.Estado if e in permitidas]
        return ctx


class OrdenesAdminEstado(SoloPersonal, View):
    """PAGADO (descuenta stock) / ENTREGADO / CANCELADO (repone stock)."""

    def post(self, request, pk):
        form = EstadoForm(request.POST)
        if form.is_valid():
            rol = rol_de_usuario(request.user)
            if form.cleaned_data["estado"] not in ESTADOS_PERMITIDOS.get(rol, set()):
                raise PermissionDenied  # el rol no puede aplicar este estado (403)
            try:
                services.cambiar_estado_orden(pk, form.cleaned_data["estado"])
                messages.success(request, "Estado actualizado.")
            except ValidationError as exc:
                for m in _mensajes(exc):
                    messages.error(request, m)
        else:
            messages.error(request, "Estado inválido.")
        return redirect("web:panel_orden_detalle", pk=pk)


# ------------------------ USUARIOS Y ROLES (SUPERADMIN) --------------------
class UsuarioLista(SoloSuperAdmin, ListView):
    template_name = "tienda/usuario_lista.html"
    paginate_by = 20

    def get_queryset(self):
        return User.objects.select_related("perfil").order_by("username")


class UsuarioFormMixin:
    """Pasa el usuario logueado al formulario (evita que el super admin se degrade a sí mismo)."""
    form_class = UsuarioForm
    template_name = "tienda/crud_form.html"
    success_url = reverse_lazy("web:usuario_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario_actual"] = self.request.user
        return kwargs


class UsuarioCrear(SoloSuperAdmin, UsuarioFormMixin, SuccessMessageMixin, CreateView):
    model = User
    success_message = "Usuario creado correctamente."
    extra_context = {"titulo": "Nuevo usuario", "volver": reverse_lazy("web:usuario_lista")}


class UsuarioEditar(SoloSuperAdmin, UsuarioFormMixin, SuccessMessageMixin, UpdateView):
    model = User
    success_message = "Usuario actualizado correctamente."
    extra_context = {"titulo": "Editar usuario / rol", "volver": reverse_lazy("web:usuario_lista")}


class UsuarioEliminar(SoloSuperAdmin, EliminarProtegido):
    model = User
    url_volver = "web:usuario_lista"
    mensaje_ok = "Usuario eliminado."
    mensaje_bloqueo = "No se puede eliminar: el usuario tiene órdenes históricas. Desactívelo en su lugar."

    def form_valid(self, form):
        if self.object == self.request.user:
            messages.error(self.request, "No puede eliminar su propia cuenta.")
            return redirect("web:usuario_lista")
        return super().form_valid(form)
