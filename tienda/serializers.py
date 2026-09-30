"""Serializadores: validación y transformación de datos de entrada/salida."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Carro, Categoria, ItemCarro, ItemOrden, Orden, Perfil, Producto

User = get_user_model()


# ------------------------- AUTENTICACIÓN / JWT -----------------------------
class TokenConRolSerializer(TokenObtainPairSerializer):
    """
    Login JWT con payload personalizado: agrega el ROL (y el username) como claims.
    Cualquier vista puede leerlos luego desde request.auth['rol'].
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        perfil, _ = Perfil.objects.get_or_create(usuario=user)
        token["rol"] = perfil.rol
        token["username"] = user.username
        return token

    def validate(self, attrs):
        # Además de los tokens, la respuesta del login incluye el rol para comodidad del frontend.
        data = super().validate(attrs)
        data["rol"] = self.user.perfil.rol
        data["username"] = self.user.username
        return data


class RegistroSerializer(serializers.ModelSerializer):
    """Registro público: siempre crea usuarios con rol CLIENTE (nunca administradores)."""

    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        # create_user hashea la clave; la señal post_save crea Perfil (CLIENTE) y Carro.
        return User.objects.create_user(**validated_data)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


# ------------------------------ CATÁLOGO -----------------------------------
class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ["id", "nombre", "descripcion"]


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)

    class Meta:
        model = Producto
        fields = [
            "id", "categoria", "categoria_nombre", "nombre", "marca",
            "sku", "descripcion", "precio", "stock", "activo",
        ]


# -------------------------------- CARRO ------------------------------------
class ItemCarroSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ItemCarro
        fields = ["id", "producto", "cantidad", "subtotal"]


class CarroSerializer(serializers.ModelSerializer):
    items = ItemCarroSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Carro
        fields = ["id", "activo", "items", "total"]


class ItemEntradaSerializer(serializers.Serializer):
    """Cuerpo para agregar / modificar un ítem del carro."""

    producto_id = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)

    def validate_producto_id(self, value):
        # Solo se pueden agregar productos existentes y activos.
        if not Producto.objects.filter(pk=value, activo=True).exists():
            raise serializers.ValidationError("El producto no existe o no está disponible.")
        return value


# ------------------------------- ÓRDENES -----------------------------------
class ItemOrdenSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    producto_sku = serializers.CharField(source="producto.sku", read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ItemOrden
        fields = ["id", "producto", "producto_nombre", "producto_sku", "cantidad", "precio_unitario", "subtotal"]


class OrdenSerializer(serializers.ModelSerializer):
    items = ItemOrdenSerializer(many=True, read_only=True)
    usuario = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = Orden
        fields = ["id", "usuario", "estado", "total", "stock_descontado", "creada", "actualizada", "items"]


class EstadoOrdenSerializer(serializers.Serializer):
    """Cuerpo del PATCH /ordenes/{id}/estado/ (valida contra los CHOICES del modelo)."""

    estado = serializers.ChoiceField(choices=Orden.Estado.choices)


# ------------------------ USUARIOS (solo SUPERADMIN) ------------------------
class UsuarioAdminSerializer(serializers.ModelSerializer):
    """Gestión de usuarios y roles por el super administrador."""

    rol = serializers.ChoiceField(source="perfil.rol", choices=Perfil.Rol.choices)
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "rol", "is_active"]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "La contraseña es obligatoria al crear."})
        return attrs

    def _guardar(self, user, rol, password):
        # Solo el rol SUPERADMIN habilita el panel /admin de Django (is_staff / is_superuser).
        es_super = rol == Perfil.Rol.SUPERADMIN
        user.is_superuser = es_super
        user.is_staff = es_super
        if password:
            user.set_password(password)
        user.save()
        Perfil.objects.update_or_create(usuario=user, defaults={"rol": rol})
        return user

    def create(self, validated_data):
        rol = validated_data.pop("perfil", {}).get("rol", Perfil.Rol.CLIENTE)
        password = validated_data.pop("password", None)
        return self._guardar(User(**validated_data), rol, password)

    def update(self, instance, validated_data):
        rol = validated_data.pop("perfil", {}).get("rol", instance.perfil.rol)
        password = validated_data.pop("password", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        return self._guardar(instance, rol, password)


class CheckoutSerializer(serializers.Serializer):
    """pagar=false (defecto): solo genera la orden PENDIENTE. pagar=true: compra inmediata (descuenta stock)."""
    pagar = serializers.BooleanField(required=False, default=False)
