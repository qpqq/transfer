from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.db.models.signals import post_save
from django.dispatch import receiver

from .staff import StaffProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_staff_profile(sender, instance, created, **kwargs):
    if created:
        StaffProfile.objects.create(user=instance)


@receiver(post_migrate)
def create_default_settings(sender, **kwargs):
    if sender.name != 'administration':
        return

    TransferRequestModel = apps.get_model('administration', 'TransferRequest')
    ct = ContentType.objects.get_for_model(TransferRequestModel)
    perms = Permission.objects.filter(content_type=ct)
    group, created = Group.objects.get_or_create(name='DepartmentAdmins')
    group.permissions.set(perms)

    Settings = apps.get_model('administration', 'Settings')
    Settings.objects.get_or_create(pk=1)
