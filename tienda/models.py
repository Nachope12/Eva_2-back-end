"""
Modelos de la tienda de hardware.

Relaciones (integridad referencial):
  User 1---1 Perfil          (rol: CLIENTE / ADMINISTRADOR)         -> OneToOne
  User 1---1 Carro           (carro activo persistente)             -> OneToOne
  Carro 1---N ItemCarro N---1 Producto                              -> ForeignKey
  Categoria 1---N Producto                                          -> ForeignKey
  User 1---N Orden 1---N ItemOrden N---1 Producto                   -> ForeignKey
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Perfil(models.Model):
    """Extiende al User con el ROL (SUPERADMIN / ADMINISTRADOR / CLIENTE) que viajará como claim dentro del JWT."""

    class Rol(models.TextChoices):  # ---- CHOICES (rol) ----
        SUPERADMIN = "SUPERADMIN", "Super Administrador"   # controla todo el sistema
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"   # gestión limitada (sin borrar, sin usuarios)
        CLIENTE = "CLIENTE", "Usuario (cliente)"           # solo ve productos y compra

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CLIENTE)

    def __str__(self):
        return f"{self.usuario.username} ({self.rol})"


class Categoria(models.Model):
    """Categoría del catálogo: Procesadores, Tarjetas de Video, RAM..."""

    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """Componente de hardware con su stock físico disponible."""

    # PROTECT: no se puede borrar una categoría que aún tiene productos.
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=80)
    sku = models.CharField(max_length=40, unique=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)  # stock físico; solo cambia al PAGAR/CANCELAR
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.sku} - {self.nombre}"


class Carro(models.Model):
    """
    Carro de compras persistente: relación 1 a 1 con el usuario.
    Vive en PostgreSQL, por eso sobrevive al logout y al cambio de dispositivo.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carro"
    )
    activo = models.BooleanField(default=True)
    actualizado = models.DateTimeField(auto_now=True)

    def total(self):
        return sum(item.subtotal for item in self.items.select_related("producto"))

    def __str__(self):
        return f"Carro de {self.usuario.username}"


class ItemCarro(models.Model):
    """Línea del carro. Un producto solo puede aparecer una vez por carro."""

    carro = models.ForeignKey(Carro, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            # Evita duplicados: el mismo producto no puede repetirse en el mismo carro.
            models.UniqueConstraint(fields=["carro", "producto"], name="unico_producto_por_carro")
        ]

    @property
    def subtotal(self):
        return self.producto.precio * self.cantidad


class Orden(models.Model):
    """Registro histórico de la compra generado en el checkout."""

    class Estado(models.TextChoices):  # ---- CHOICES (estado de la orden) ----
        PENDIENTE = "PENDIENTE", "Pendiente"
        PAGADO = "PAGADO", "Pagado"
        ENTREGADO = "ENTREGADO", "Entregado"
        CANCELADO = "CANCELADO", "Cancelado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordenes"
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Bandera de control: indica si esta orden ya descontó stock (para reponer solo lo descontado).
    stock_descontado = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada"]

    def __str__(self):
        return f"Orden #{self.pk} - {self.usuario.username} - {self.estado}"


class ItemOrden(models.Model):
    """Línea de la orden. Guarda el PRECIO CONGELADO al momento del checkout."""

    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)  # snapshot histórico

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad
