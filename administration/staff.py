from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .models import Department


class StaffProfile(models.Model):
    class Meta:
        verbose_name = _('Профиль админа кафедры')
        verbose_name_plural = _('Профили админов кафедр')

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        verbose_name=_('Кафедры в управлении')
    )

    def __str__(self):
        return str(_(f'Профиль {self.user.username}'))
