"""
Señales: al crearse un User se generan automáticamente su Perfil (rol) y su Carro (1 a 1).
Los superusuarios de Django reciben el rol SUPERADMIN; el resto, CLIENTE
(el rol ADMINISTRADOR lo asigna un super administrador).
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Carro, Perfil


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_perfil_y_carro(sender, instance, created, **kwargs):
    if created:
        rol = Perfil.Rol.SUPERADMIN if instance.is_superuser else Perfil.Rol.CLIENTE
        Perfil.objects.create(usuario=instance, rol=rol)
        Carro.objects.create(usuario=instance)
