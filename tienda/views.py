"""Vistas / endpoints de la API."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import services
from .filters import OrdenFilter, ProductoFilter
from .models import Carro, Categoria, ItemCarro, Orden, Perfil, Producto
from .permissions import (
    ESTADOS_PERMITIDOS, PERSONAL, EsCliente, EsPersonal, EsSuperAdmin, PermisoCatalogo, obtener_rol,
)
from .serializers import (
    CarroSerializer, CategoriaSerializer, CheckoutSerializer, EstadoOrdenSerializer, ItemEntradaSerializer,
    LogoutSerializer, OrdenSerializer, ProductoSerializer, RegistroSerializer,
    TokenConRolSerializer, UsuarioAdminSerializer,
)

User = get_user_model()


# ---------------------------- VISTA HTML BASE ------------------------------
def home(request):
    """
    Página de inicio: es un DASHBOARD distinto según el rol.
      - CLIENTE: solo ve su carro y sus órdenes (nunca la API/Swagger).
      - ADMINISTRADOR / SUPERADMIN: ve indicadores del negocio y el acceso a la API.
    Es pública: un visitante anónimo ve la portada estilo NEXUS (hero, categorías y opiniones).
    Los datos del alumno (footer) llegan vía context processor (tienda/context_processors.py).
    """
    contexto = {}
    perfil = getattr(request.user, "perfil", None)
    rol = perfil.rol if perfil else None

    if rol == Perfil.Rol.CLIENTE:
        carro, _ = Carro.objects.get_or_create(usuario=request.user)
        contexto.update(
            carro_items=carro.items.count(),
            carro_total=carro.total(),
            ordenes_pendientes=Orden.objects.filter(usuario=request.user, estado=Orden.Estado.PENDIENTE).count(),
            ordenes_totales=Orden.objects.filter(usuario=request.user).count(),
        )
    elif rol in (Perfil.Rol.ADMINISTRADOR, Perfil.Rol.SUPERADMIN):
        contexto.update(
            total_productos=Producto.objects.filter(activo=True).count(),
            total_categorias=Categoria.objects.count(),
            ordenes_pendientes=Orden.objects.filter(estado=Orden.Estado.PENDIENTE).count(),
            stock_bajo=Producto.objects.filter(activo=True, stock__lte=5).count(),
        )

    return render(request, "tienda/index.html", contexto)


# ----------------------------- AUTENTICACIÓN -------------------------------
class LoginView(TokenObtainPairView):
    """Login (check-in): devuelve access + refresh con el claim 'rol'."""

    serializer_class = TokenConRolSerializer
    permission_classes = [AllowAny]


class RegistroView(generics.CreateAPIView):
    """Registro público de clientes."""

    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """
    Logout: invalida (blacklist) el refresh token. El carro NO se toca:
    sigue guardado en PostgreSQL y estará intacto en el próximo login.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={205: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except Exception:
            return Response({"detail": "Refresh token inválido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


# -------------------------------- CATÁLOGO ---------------------------------
class CategoriaViewSet(viewsets.ModelViewSet):
    """GET público. Crear/editar: ADMINISTRADOR y SUPERADMIN. Eliminar: solo SUPERADMIN."""

    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [PermisoCatalogo]
    search_fields = ["nombre"]


class ProductoViewSet(viewsets.ModelViewSet):
    """
    GET público (con filtros django-filter, búsqueda y ordenamiento).
    Crear/editar: ADMINISTRADOR y SUPERADMIN. Eliminar: solo SUPERADMIN.
    """

    serializer_class = ProductoSerializer
    permission_classes = [PermisoCatalogo]
    filterset_class = ProductoFilter
    search_fields = ["nombre", "marca", "sku", "descripcion"]
    ordering_fields = ["precio", "nombre", "stock"]

    def get_queryset(self):
        qs = Producto.objects.select_related("categoria")
        # El público y los clientes solo ven productos activos; el personal ve todos.
        if obtener_rol(self.request) in PERSONAL:
            return qs
        return qs.filter(activo=True)


# --------------------------------- CARRO -----------------------------------
class CarroView(APIView):
    """
    Carro persistente del CLIENTE (1 a 1 con el usuario, guardado en PostgreSQL).
    NOTA: agregar al carro NO descuenta stock; el stock solo se valida y descuenta al PAGAR.
    """

    permission_classes = [EsCliente]

    def _carro(self, request):
        return Carro.objects.get_or_create(usuario=request.user)[0]

    @extend_schema(responses=CarroSerializer)
    def get(self, request):
        """Devuelve el carro con sus ítems y total."""
        return Response(CarroSerializer(self._carro(request)).data)

    @extend_schema(request=ItemEntradaSerializer, responses=CarroSerializer)
    def post(self, request):
        """Agrega un producto. Si ya estaba en el carro, SUMA la cantidad (sin duplicar filas)."""
        s = ItemEntradaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        carro = self._carro(request)
        item, creado = ItemCarro.objects.get_or_create(
            carro=carro,
            producto_id=s.validated_data["producto_id"],
            defaults={"cantidad": s.validated_data["cantidad"]},
        )
        if not creado:
            item.cantidad += s.validated_data["cantidad"]
            item.save(update_fields=["cantidad"])
        return Response(CarroSerializer(carro).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ItemEntradaSerializer, responses=CarroSerializer)
    def patch(self, request):
        """Modifica la cantidad de un ítem existente (reemplaza el valor)."""
        s = ItemEntradaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        carro = self._carro(request)
        actualizados = ItemCarro.objects.filter(
            carro=carro, producto_id=s.validated_data["producto_id"]
        ).update(cantidad=s.validated_data["cantidad"])
        if not actualizados:
            return Response({"detail": "El producto no está en el carro."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CarroSerializer(carro).data)

    @extend_schema(
        parameters=[OpenApiParameter("producto_id", int, required=False,
                                     description="Si se omite, se vacía todo el carro.")],
        responses=CarroSerializer,
    )
    def delete(self, request):
        """Elimina un ítem (?producto_id=) o vacía el carro completo."""
        carro = self._carro(request)
        producto_id = request.query_params.get("producto_id")
        items = carro.items.filter(producto_id=producto_id) if producto_id else carro.items.all()
        items.delete()
        return Response(CarroSerializer(carro).data)


# --------------------------- CHECKOUT Y ÓRDENES ----------------------------
class CheckoutView(APIView):
    """
    POST /api/ordenes/checkout/
      - {"pagar": false} (defecto): genera la Orden PENDIENTE desde el carro (sin tocar stock).
      - {"pagar": true}: compra inmediata; la orden queda PAGADO y el inventario se actualiza.
    """

    permission_classes = [EsCliente]

    @extend_schema(request=CheckoutSerializer, responses=OrdenSerializer)
    def post(self, request):
        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if s.validated_data["pagar"]:
            orden = services.comprar_desde_carro(request.user)
        else:
            orden = services.checkout_desde_carro(request.user)
        return Response(OrdenSerializer(orden).data, status=status.HTTP_201_CREATED)


class PagarOrdenView(APIView):
    """
    POST /api/ordenes/{id}/pagar/ : el cliente paga su orden (simulado).
    Valida stock y lo descuenta atómicamente; si falta stock, se rechaza con 400.
    """

    permission_classes = [EsCliente]

    @extend_schema(request=None, responses=OrdenSerializer)
    def post(self, request, pk):
        orden = services.cambiar_estado_orden(pk, Orden.Estado.PAGADO, usuario=request.user)
        return Response(OrdenSerializer(orden).data)


class CambiarEstadoOrdenView(APIView):
    """
    PATCH /api/ordenes/{id}/estado/
      - ADMINISTRADOR: solo puede marcar ENTREGADO.
      - SUPERADMIN: PAGADO / ENTREGADO / CANCELADO (los que mueven inventario).
    """

    permission_classes = [EsPersonal]

    @extend_schema(request=EstadoOrdenSerializer, responses=OrdenSerializer)
    def patch(self, request, pk):
        s = EstadoOrdenSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        nuevo_estado = s.validated_data["estado"]
        rol = obtener_rol(request)
        # Cada rol solo puede llevar la orden a ciertos estados (ver permissions.ESTADOS_PERMITIDOS).
        if nuevo_estado not in ESTADOS_PERMITIDOS.get(rol, set()):
            raise PermissionDenied(f"El rol {rol} no puede cambiar una orden a {nuevo_estado}.")
        orden = services.cambiar_estado_orden(pk, nuevo_estado)
        return Response(OrdenSerializer(orden).data)


class MisOrdenesView(generics.ListAPIView):
    """GET /api/mis-ordenes/ : historial de órdenes del cliente autenticado."""

    serializer_class = OrdenSerializer
    permission_classes = [EsCliente]
    filterset_class = OrdenFilter
    ordering_fields = ["creada", "total"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Orden.objects.none()
        return Orden.objects.filter(usuario=self.request.user).prefetch_related("items__producto")


class TodasLasOrdenesView(generics.ListAPIView):
    """GET /api/ordenes/ : listado global de órdenes (ADMINISTRADOR y SUPERADMIN)."""

    serializer_class = OrdenSerializer
    permission_classes = [EsPersonal]
    filterset_class = OrdenFilter
    queryset = Orden.objects.prefetch_related("items__producto").select_related("usuario")


# ------------------------ USUARIOS (solo SUPERADMIN) -----------------------
class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuarios y roles. Exclusivo del SUPERADMIN."""

    serializer_class = UsuarioAdminSerializer
    permission_classes = [EsSuperAdmin]
    queryset = User.objects.select_related("perfil").order_by("username")
    filterset_fields = ["is_active", "perfil__rol"]
    search_fields = ["username", "email"]

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        if usuario == request.user:
            return Response({"detail": "No puede eliminar su propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            usuario.delete()
        except ProtectedError:
            return Response(
                {"detail": "El usuario tiene órdenes históricas; desactívelo (is_active=false) en vez de eliminarlo."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
