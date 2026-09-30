from django.contrib import admin

from .models import Carro, Categoria, ItemCarro, ItemOrden, Orden, Perfil, Producto


class ItemCarroInline(admin.TabularInline):
    model = ItemCarro
    extra = 0


class ItemOrdenInline(admin.TabularInline):
    model = ItemOrden
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "nombre", "marca", "categoria", "precio", "stock", "activo")
    list_filter = ("categoria", "marca", "activo")
    search_fields = ("nombre", "sku", "marca")


@admin.register(Carro)
class CarroAdmin(admin.ModelAdmin):
    inlines = [ItemCarroInline]


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "estado", "total", "stock_descontado", "creada")
    list_filter = ("estado",)
    inlines = [ItemOrdenInline]


admin.site.register(Categoria)
admin.site.register(Perfil)
