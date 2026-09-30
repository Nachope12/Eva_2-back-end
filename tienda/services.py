"""
Lógica de negocio transaccional (checkout, stock y estados).

Se separa de las vistas para que el flujo sea fácil de defender:
  - checkout_desde_carro():  Carro -> Orden PENDIENTE (precios congelados). NO toca el stock.
  - cambiar_estado_orden():  aplica la máquina de estados y mueve el stock de forma ATÓMICA.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from .models import Carro, ItemOrden, Orden, Producto

E = Orden.Estado

# Máquina de estados: qué transiciones están permitidas.
TRANSICIONES = {
    E.PENDIENTE: {E.PAGADO, E.CANCELADO},
    E.PAGADO: {E.ENTREGADO, E.CANCELADO},
    E.ENTREGADO: set(),   # estado final
    E.CANCELADO: set(),   # estado final
}


@transaction.atomic
def checkout_desde_carro(usuario):
    """
    CHECKOUT: convierte el contenido del carro en una Orden histórica PENDIENTE.
      - Congela el precio unitario de cada producto en ItemOrden.
      - Vacía el carro (queda listo para una nueva compra).
      - NO descuenta stock (eso ocurre solo al pasar a PAGADO).
    """
    # Bloquea la fila del carro para evitar checkouts dobles simultáneos.
    carro = Carro.objects.select_for_update().get_or_create(usuario=usuario)[0]
    items = list(carro.items.select_related("producto"))

    if not items:
        raise ValidationError({"carro": "El carro está vacío."})

    inactivos = [i.producto.nombre for i in items if not i.producto.activo]
    if inactivos:
        raise ValidationError({"carro": f"Productos ya no disponibles: {', '.join(inactivos)}"})

    orden = Orden.objects.create(usuario=usuario, estado=E.PENDIENTE)
    total = 0
    for item in items:
        ItemOrden.objects.create(
            orden=orden,
            producto=item.producto,
            cantidad=item.cantidad,
            precio_unitario=item.producto.precio,  # precio congelado (snapshot)
        )
        total += item.producto.precio * item.cantidad

    orden.total = total
    orden.save(update_fields=["total"])
    carro.items.all().delete()  # el carro se liquida
    return orden


def _descontar_stock(orden):
    """Valida y descuenta el stock de todos los ítems. Si falta alguno, RECHAZA todo."""
    items = list(orden.items.all())
    ids = sorted({i.producto_id for i in items})
    # select_for_update: bloquea las filas de producto hasta terminar la transacción
    # (evita sobreventa cuando dos pagos ocurren al mismo tiempo). order_by evita deadlocks.
    productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=ids).order_by("pk")}

    faltantes = []
    for item in items:
        producto = productos[item.producto_id]
        if producto.stock < item.cantidad:
            faltantes.append(
                f"{producto.nombre}: solicitado {item.cantidad}, disponible {producto.stock}"
            )
    if faltantes:
        # Se lanza ANTES de modificar nada; además, al salir del atomic se hace rollback.
        raise ValidationError({"stock": ["Stock insuficiente.", *faltantes]})

    for item in items:
        producto = productos[item.producto_id]
        producto.stock -= item.cantidad
        producto.save(update_fields=["stock"])
    orden.stock_descontado = True


def _reponer_stock(orden):
    """Devuelve al catálogo el stock que esta orden había descontado (solo si lo descontó)."""
    if not orden.stock_descontado:
        return
    ids = sorted({i.producto_id for i in orden.items.all()})
    productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    for item in orden.items.all():
        producto = productos[item.producto_id]
        producto.stock += item.cantidad
        producto.save(update_fields=["stock"])
    orden.stock_descontado = False


@transaction.atomic
def cambiar_estado_orden(orden_id, nuevo_estado, usuario=None):
    """
    Cambia el estado de una orden aplicando las reglas de inventario:
      * -> PAGADO     : valida stock; si alcanza, lo descuenta (todo o nada).
      * -> CANCELADO  : si la orden ya había descontado stock, lo repone.
      * -> ENTREGADO  : solo cierra la transacción.
    `usuario` (opcional) restringe la orden a su dueño (pago hecho por el cliente).
    """
    ordenes = Orden.objects.select_for_update()  # bloquea la orden durante la transacción
    if usuario is not None:
        ordenes = ordenes.filter(usuario=usuario)
    orden = get_object_or_404(ordenes, pk=orden_id)

    if nuevo_estado not in TRANSICIONES[orden.estado]:
        raise ValidationError(
            {"estado": f"Transición no permitida: {orden.estado} -> {nuevo_estado}."}
        )

    if nuevo_estado == E.PAGADO:
        _descontar_stock(orden)
    elif nuevo_estado == E.CANCELADO:
        _reponer_stock(orden)

    orden.estado = nuevo_estado
    orden.save()
    return orden


@transaction.atomic
def comprar_desde_carro(usuario):
    """
    COMPRA INMEDIATA: checkout + pago en una sola transacción atómica.
      1) Carro -> Orden PENDIENTE (precios congelados).
      2) Orden PENDIENTE -> PAGADO: valida y DESCUENTA el inventario.
    Si falta stock en cualquier producto, se hace rollback de TODO: no se crea la orden
    y el carro queda intacto. Cada compra exitosa actualiza el inventario.
    """
    orden = checkout_desde_carro(usuario)
    return cambiar_estado_orden(orden.pk, E.PAGADO, usuario=usuario)
