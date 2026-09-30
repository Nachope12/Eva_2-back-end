from django.apps import AppConfig


class TiendaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tienda"

    def ready(self):
        # Registra las señales (creación automática de Perfil y Carro).
        from . import signals  # noqa: F401
