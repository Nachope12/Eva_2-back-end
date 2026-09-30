"""
Comando: python manage.py cargar_datos
Carga datos de prueba: usuarios (admin y clientes), categorías, productos,
un carro con ítems y una orden PENDIENTE de ejemplo. Es idempotente.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from tienda import services
from tienda.models import Carro, Categoria, ItemCarro, Orden, Perfil, Producto

User = get_user_model()

# (categoria, nombre, marca, sku, precio CLP, stock, descripcion)
PRODUCTOS = [
    ("Procesadores", "Ryzen 7 7800X3D", "AMD", "CPU-AMD-7800X3D", 389990, 12, "8 núcleos / 16 hilos, 3D V-Cache, AM5."),
    ("Procesadores", "Ryzen 5 7600", "AMD", "CPU-AMD-7600", 189990, 25, "6 núcleos / 12 hilos, AM5."),
    ("Procesadores", "Core i7-14700K", "Intel", "CPU-INT-14700K", 429990, 10, "20 núcleos, LGA1700, desbloqueado."),
    ("Procesadores", "Core i5-13400F", "Intel", "CPU-INT-13400F", 159990, 30, "10 núcleos, LGA1700."),
    ("Tarjetas de Video", "GeForce RTX 4070 Super 12GB", "NVIDIA", "GPU-NV-4070S", 719990, 8, "12GB GDDR6X, DLSS 3."),
    ("Tarjetas de Video", "GeForce RTX 4060 8GB", "NVIDIA", "GPU-NV-4060", 329990, 15, "8GB GDDR6, ideal 1080p."),
    ("Tarjetas de Video", "Radeon RX 7800 XT 16GB", "AMD", "GPU-AMD-7800XT", 559990, 6, "16GB GDDR6, RDNA 3."),
    ("Memoria RAM", "Vengeance DDR5 32GB (2x16) 6000MHz", "Corsair", "RAM-COR-D5-32", 129990, 40, "Kit dual channel CL30."),
    ("Memoria RAM", "Fury Beast DDR4 16GB 3200MHz", "Kingston", "RAM-KIN-D4-16", 44990, 60, "Módulo DDR4 CL16."),
    ("Almacenamiento", "SSD NVMe 980 Pro 1TB", "Samsung", "SSD-SAM-980P-1T", 119990, 20, "PCIe 4.0, hasta 7000 MB/s."),
    ("Almacenamiento", "SSD NV2 500GB", "Kingston", "SSD-KIN-NV2-500", 39990, 3, "NVMe PCIe 4.0 económico (stock bajo a propósito)."),
    ("Placas Madre", "ROG STRIX B650-A GAMING WIFI", "ASUS", "MB-ASU-B650A", 259990, 9, "AM5, DDR5, WiFi 6E."),
]


class Command(BaseCommand):
    help = "Carga datos de prueba para la tienda de hardware."

    @transaction.atomic
    def handle(self, *args, **options):
        # ---- Usuarios ----
        # Superusuario admin (la señal le asigna rol SUPERADMIN: controla todo el sistema).
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@techhardware.cl", "Admin12345!")
        # Administrador con permisos limitados (no puede eliminar, pagar/cancelar ni gestionar usuarios).
        gestor, creado = User.objects.get_or_create(username="gestor", defaults={"email": "gestor@techhardware.cl"})
        if creado:
            gestor.set_password("Gestor12345!")
            gestor.save()
        Perfil.objects.filter(usuario=gestor).update(rol=Perfil.Rol.ADMINISTRADOR)

        clientes = {}
        for username in ("cliente", "cliente2"):
            u, creado = User.objects.get_or_create(username=username, defaults={"email": f"{username}@correo.cl"})
            if creado:
                u.set_password("Cliente12345!")
                u.save()
            clientes[username] = u

        # Usuario de prueba pedido por el alumno: nacho / 12345 (rol CLIENTE, puede comprar).
        nacho, creado = User.objects.get_or_create(username="nacho", defaults={"email": "nacho@correo.cl"})
        if creado:
            nacho.set_password("12345")
            nacho.save()
        clientes["nacho"] = nacho

        # ---- Catálogo ----
        for cat, nombre, marca, sku, precio, stock, desc in PRODUCTOS:
            categoria, _ = Categoria.objects.get_or_create(nombre=cat)
            Producto.objects.update_or_create(
                sku=sku,
                defaults={"categoria": categoria, "nombre": nombre, "marca": marca,
                          "precio": precio, "stock": stock, "descripcion": desc, "activo": True},
            )

        # ---- Carro de ejemplo (persistente) para 'cliente' ----
        carro = Carro.objects.get(usuario=clientes["cliente"])
        for sku, cant in (("RAM-COR-D5-32", 1), ("SSD-SAM-980P-1T", 2)):
            ItemCarro.objects.get_or_create(
                carro=carro, producto=Producto.objects.get(sku=sku), defaults={"cantidad": cant}
            )

        # ---- Orden PENDIENTE de ejemplo para 'cliente2' ----
        if not Orden.objects.filter(usuario=clientes["cliente2"]).exists():
            carro2 = Carro.objects.get(usuario=clientes["cliente2"])
            ItemCarro.objects.get_or_create(carro=carro2, producto=Producto.objects.get(sku="GPU-NV-4060"), defaults={"cantidad": 1})
            ItemCarro.objects.get_or_create(carro=carro2, producto=Producto.objects.get(sku="CPU-AMD-7600"), defaults={"cantidad": 1})
            services.checkout_desde_carro(clientes["cliente2"])

        self.stdout.write(self.style.SUCCESS("Datos de prueba cargados."))
        self.stdout.write("  admin / Admin12345!  (SUPERADMIN)  |  gestor / Gestor12345!  (ADMINISTRADOR)")
        self.stdout.write("  cliente / Cliente12345!  |  cliente2 / Cliente12345!  |  nacho / 12345  (CLIENTE)")
