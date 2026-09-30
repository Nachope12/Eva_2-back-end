"""Filtros con django-filter para los endpoints de consulta."""
import django_filters as filters
from django import forms

from .models import Orden, Producto


class ProductoFilter(filters.FilterSet):
    """
    Ejemplos:
      /api/productos/?categoria=1
      /api/productos/?precio_min=100000&precio_max=500000
      /api/productos/?marca=nvidia&nombre=rtx&en_stock=true
    """

    categoria = filters.NumberFilter(field_name="categoria_id")
    categoria_nombre = filters.CharFilter(field_name="categoria__nombre", lookup_expr="icontains")
    marca = filters.CharFilter(field_name="marca", lookup_expr="icontains")
    nombre = filters.CharFilter(field_name="nombre", lookup_expr="icontains")
    # min="0": el campo de precio del filtro tampoco admite números negativos.
    precio_min = filters.NumberFilter(
        field_name="precio", lookup_expr="gte", min_value=0,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )
    precio_max = filters.NumberFilter(
        field_name="precio", lookup_expr="lte", min_value=0,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )
    en_stock = filters.BooleanFilter(method="filtrar_en_stock")

    def filtrar_en_stock(self, queryset, name, value):
        # true -> solo con stock > 0 ; false -> solo agotados
        return queryset.filter(stock__gt=0) if value else queryset.filter(stock=0)

    class Meta:
        model = Producto
        fields = ["categoria", "categoria_nombre", "marca", "nombre", "precio_min", "precio_max", "en_stock"]


class OrdenFilter(filters.FilterSet):
    """/api/mis-ordenes/?estado=PAGADO&desde=2026-01-01"""

    estado = filters.ChoiceFilter(choices=Orden.Estado.choices)
    desde = filters.DateFilter(field_name="creada", lookup_expr="date__gte")
    hasta = filters.DateFilter(field_name="creada", lookup_expr="date__lte")

    class Meta:
        model = Orden
        fields = ["estado", "desde", "hasta"]
