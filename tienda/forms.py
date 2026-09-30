"""Formularios HTML (ModelForms) usados por las plantillas CRUD."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import Categoria, Orden, Perfil, Producto

User = get_user_model()


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["categoria", "nombre", "marca", "sku", "descripcion", "precio", "stock", "activo"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            # min="0": el navegador ya no deja escribir precio o stock negativos.
            # (El modelo también lo valida en el servidor: precio con MinValueValidator(0)
            # y stock con PositiveIntegerField, así que nunca queda un número negativo guardado).
            "precio": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "stock": forms.NumberInput(attrs={"min": "0", "step": "1"}),
        }


class CantidadForm(forms.Form):
    """Cantidad para agregar o modificar un ítem del carro."""
    cantidad = forms.IntegerField(min_value=1, initial=1, label="Cantidad")


class EstadoForm(forms.Form):
    """Cambio de estado de una orden (valida contra los CHOICES del modelo)."""
    estado = forms.ChoiceField(choices=Orden.Estado.choices)


class RegistroForm(UserCreationForm):
    """Registro público de clientes (la señal post_save les asigna rol CLIENTE y carro)."""
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se quitan los textos de indicaciones de la contraseña
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""


class UsuarioForm(forms.ModelForm):
    """Alta / edición de usuarios y roles (solo SUPERADMIN)."""

    rol = forms.ChoiceField(choices=Perfil.Rol.choices)
    password = forms.CharField(
        widget=forms.PasswordInput, required=False, label="Contraseña",
    )

    class Meta:
        model = User
        fields = ["username", "email", "is_active"]

    def __init__(self, *args, usuario_actual=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario_actual = usuario_actual
        if self.instance.pk:
            self.fields["rol"].initial = self.instance.perfil.rol

    def _es_uno_mismo(self):
        return bool(self.instance.pk and self.usuario_actual and self.instance.pk == self.usuario_actual.pk)

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.instance.pk and not password:
            raise forms.ValidationError("La contraseña es obligatoria al crear un usuario.")
        if password:
            validate_password(password)
        return password

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        if self._es_uno_mismo() and rol != Perfil.Rol.SUPERADMIN:
            raise forms.ValidationError("No puede quitarse a sí mismo el rol de Super Administrador.")
        return rol

    def clean_is_active(self):
        activo = self.cleaned_data["is_active"]
        if self._es_uno_mismo() and not activo:
            raise forms.ValidationError("No puede desactivar su propia cuenta.")
        return activo

    def save(self, commit=True):
        user = super().save(commit=False)
        rol = self.cleaned_data["rol"]
        es_super = rol == Perfil.Rol.SUPERADMIN
        user.is_superuser = es_super   # solo el SUPERADMIN accede al /admin de Django
        user.is_staff = es_super
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()
        Perfil.objects.update_or_create(usuario=user, defaults={"rol": rol})
        return user
