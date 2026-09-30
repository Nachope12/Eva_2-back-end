"""
Permisos por ROL (RBAC). Roles: SUPERADMIN > ADMINISTRADOR > CLIENTE.

MATRIZ DE PERMISOS
------------------------------------------------------------------------------------
Acción                                   Público  CLIENTE  ADMINISTRADOR  SUPERADMIN
Ver catálogo (productos / categorías)      Sí       Sí         Sí             Sí
Carro, comprar, ver mis órdenes            No       Sí         No             No
Crear / editar productos y categorías      No       No         Sí             Sí
Eliminar productos y categorías            No       No         No             Sí
Ver todas las órdenes                      No       No         Sí             Sí
Estado ENTREGADO                           No       No         Sí             Sí
Estado PAGADO / CANCELADO (mueve stock)    No       No         No             Sí
Gestionar usuarios y roles                 No       No         No             Sí
------------------------------------------------------------------------------------
El rol se lee primero desde el claim 'rol' del JWT (request.auth). Si no existe
(sesión de Django en las páginas HTML), se consulta el Perfil en la BD.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Orden, Perfil

ROL = Perfil.Rol
E = Orden.Estado

# Roles que pueden entrar al panel de gestión.
PERSONAL = {ROL.ADMINISTRADOR, ROL.SUPERADMIN}

# Estados a los que cada rol puede llevar una orden.
ESTADOS_PERMITIDOS = {
    ROL.SUPERADMIN: {E.PAGADO, E.ENTREGADO, E.CANCELADO},
    ROL.ADMINISTRADOR: {E.ENTREGADO},
}


def rol_de_usuario(user):
    """Rol según el Perfil en BD (usado por las vistas HTML con sesión)."""
    perfil = getattr(user, "perfil", None)
    return perfil.rol if perfil else None


def obtener_rol(request):
    """Rol del usuario autenticado: claim del JWT o, si no hay token, Perfil en BD."""
    user = request.user
    if not user or not user.is_authenticated:
        return None
    auth = getattr(request, "auth", None)
    if auth is not None:
        try:
            rol = auth.get("rol")
            if rol:
                return rol
        except AttributeError:
            pass
    return rol_de_usuario(user)


class EsCliente(BasePermission):
    """Solo usuarios con rol CLIENTE (carro y compras)."""
    message = "Solo los usuarios (clientes) pueden realizar esta acción."

    def has_permission(self, request, view):
        return obtener_rol(request) == ROL.CLIENTE


class EsPersonal(BasePermission):
    """ADMINISTRADOR o SUPERADMIN (gestión de inventario y órdenes)."""
    message = "Se requiere rol Administrador o Super Administrador."

    def has_permission(self, request, view):
        return obtener_rol(request) in PERSONAL


class EsSuperAdmin(BasePermission):
    """Solo SUPERADMIN (usuarios, eliminaciones, cancelaciones)."""
    message = "Se requiere rol Super Administrador."

    def has_permission(self, request, view):
        return obtener_rol(request) == ROL.SUPERADMIN


class PermisoCatalogo(BasePermission):
    """
    Catálogo: lectura pública; crear/editar -> ADMINISTRADOR o SUPERADMIN;
    eliminar -> solo SUPERADMIN.
    """
    message = "No tiene permiso para modificar el catálogo."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        rol = obtener_rol(request)
        if request.method == "DELETE":
            return rol == ROL.SUPERADMIN
        return rol in PERSONAL
