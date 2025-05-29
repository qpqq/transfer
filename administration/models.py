from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Group(models.Model):
    class Meta:
        verbose_name = _('Учебная группа')
        verbose_name_plural = _('Учебные группы')

    class EducationSystem(models.TextChoices):
        regular = 'R', _('Очная')
        online = 'O', _('Заочная')

    archive = models.BooleanField(_('Архивная'))
    name = models.CharField(_('Наименование'))
    code = models.PositiveIntegerField(_('Код'), unique=True)
    number = models.PositiveIntegerField(_('Номер группы'), blank=True, null=True)
    faculty = models.CharField(_('Физтех-школа (факультет)'), blank=True, null=True)
    stream = models.CharField(_('Учебный поток'), blank=True, null=True)
    education_system = models.CharField(
        max_length=2,
        choices=EducationSystem.choices,
        verbose_name=_('Форма обучения')
    )
    index = models.CharField(_('Индекс группы'), blank=True, null=True)
    department = models.CharField(_('Кафедра'), blank=True, null=True)

    def __str__(self):
        return f'{self.name}'


class Student(models.Model):
    class Meta:
        verbose_name = _('Студент')
        verbose_name_plural = _('Студенты')

    class Sex(models.TextChoices):
        male = 'M', _('Мужской')
        female = 'F', _('Женский')

    full_name = models.CharField(_('Студент'))
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Группа')
    )
    sex = models.CharField(
        max_length=2,
        choices=Sex.choices,
        verbose_name=_('Пол')
    )
    email = models.EmailField(_('Адрес электронной почты физтех'))  # TODO unique=True

    def __str__(self):
        return self.full_name


class Teacher(models.Model):
    class Meta:
        verbose_name = _('Преподаватель')
        verbose_name_plural = _('Преподаватели')

    full_name = models.CharField(_('Преподаватель'))
    email = models.EmailField(_('Адрес электронной почты'))  # TODO unique=True

    def __str__(self):
        return self.full_name


class Subject(models.Model):
    class Meta:
        verbose_name = _('Предмет')
        verbose_name_plural = _('Предметы')

    name = models.CharField(_('Предмет'))

    def __str__(self):
        return self.name


class SubjectGroup(models.Model):
    class Meta:
        verbose_name = _('Предметная группа')
        verbose_name_plural = _('Предметные группы')

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='subject_groups',
        verbose_name=_('Предмет')
    )
    name = models.CharField(_('Название группы'), blank=True, null=True)
    teachers = models.ManyToManyField(
        Teacher,
        blank=True,
        verbose_name=_('Преподаватели')
    )
    students = models.ManyToManyField(
        Student,
        blank=True,
        verbose_name=_('Студенты')
    )

    def __str__(self):
        return f'{self.subject.name}{f' — {self.name}' if self.name else ''}'

    def get_teacher_names(self, default=_('--')):
        qs = self.teachers.all()
        return ', '.join([t.full_name for t in qs]) if qs else default


class TransferRequest(models.Model):
    class Meta:
        verbose_name = _('Заявка на перевод')
        verbose_name_plural = _('Заявки на перевод')
        ordering = ['-created_at']

    student = models.ForeignKey(
        'Student',
        on_delete=models.CASCADE,
        related_name='transfer_requests',
        verbose_name=_('Студент')
    )
    subject = models.ForeignKey(
        'Subject',
        on_delete=models.CASCADE,
        related_name='transfer_requests',
        verbose_name=_('Предмет')
    )
    from_group = models.ForeignKey(
        'SubjectGroup',
        on_delete=models.CASCADE,
        related_name='outgoing_requests',
        verbose_name=_('Из группы')
    )
    to_group = models.ForeignKey(
        'SubjectGroup',
        on_delete=models.CASCADE,
        related_name='incoming_requests',
        verbose_name=_('В группу')
    )
    created_at = models.DateTimeField(
        _('Время подачи заявления'),
        default=timezone.now,
        editable=False
    )

    def __str__(self):
        return f'{self.student.full_name}: {self.from_group} → {self.to_group} ({self.created_at:%Y-%m-%d %H:%M})'
