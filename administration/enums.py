from django.db import models
from django.utils.translation import gettext_lazy as _


class EducationSystem(models.TextChoices):
    regular = 'regular', _('Очная')
    online = 'online', _('Заочная')


class Sex(models.TextChoices):
    male = 'M', _('Мужской')
    female = 'F', _('Женский')


class Semester(models.TextChoices):
    fall = 'F', _('Осенний')
    spring = 'S', _('Весенний')


class Status(models.TextChoices):
    PENDING = 'pending', _('В очереди')
    WAITING_TEACHER = 'waiting_teacher', _('Ждет одобрения преподавателем')
    WAITING_ADMIN = 'waiting_admin', _('Ждет одобрения администратором')
    COMPLETED = 'completed', _('Выполнена')
    REJECTED = 'rejected', _('Отклонена')
