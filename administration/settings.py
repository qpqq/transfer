from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Settings(models.Model):
    class Meta:
        verbose_name = _('Глобальные настройки')
        verbose_name_plural = _('Глобальные настройки')

    @staticmethod
    def get_default_deadline():
        tz = timezone.get_current_timezone()
        now = timezone.now().astimezone(tz)
        naive = datetime(year=now.year, month=9, day=14, hour=23, minute=59, second=59)
        return timezone.make_aware(naive, tz)

    default_min_students = models.PositiveIntegerField(
        _('Минимальное число студентов в предметной группе по умолчанию'),
        default=12
    )
    default_max_students = models.PositiveIntegerField(
        _('Максимальное число студентов в предметной группе по умолчанию'),
        default=18
    )
    default_deadline = models.DateTimeField(
        _('Крайнее время подачи заявления на перевод по умолчанию'),
        default=get_default_deadline
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return str(_('Глобальные настройки'))
