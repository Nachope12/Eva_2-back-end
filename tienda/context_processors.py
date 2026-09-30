"""
Context processor: deja disponibles en TODAS las plantillas los datos del alumno (footer)
y el rol del usuario (para mostrar/ocultar opciones del menú).
"""
from django.conf import settings

from .models import Perfil


def datos_globales(request):
    usuario = getattr(request, "user", None)
    perfil = getattr(usuario, "perfil", None)  # AnonymousUser -> None
    rol = perfil.rol if perfil else None

    # Cantidad de ítems en el carro (para el globo del ícono del carrito en la barra superior).
    carrito_cantidad = 0
    if rol == Perfil.Rol.CLIENTE:
        carro = getattr(usuario, "carro", None)
        if carro:
            carrito_cantidad = sum(i.cantidad for i in carro.items.all())

    return {
        "alumno_nombre": settings.ALUMNO_NOMBRE,
        "alumno_seccion": settings.ALUMNO_SECCION,
        "alumno_anio": settings.ALUMNO_ANIO,
        "rol_actual": rol,
        "es_super": rol == Perfil.Rol.SUPERADMIN,                                   # controla todo
        "es_admin": rol == Perfil.Rol.ADMINISTRADOR,                                # gestión limitada
        "es_personal": rol in (Perfil.Rol.SUPERADMIN, Perfil.Rol.ADMINISTRADOR),    # panel de gestión
        "es_cliente": rol == Perfil.Rol.CLIENTE,                                    # comprador
        "carrito_cantidad": carrito_cantidad,
    }
