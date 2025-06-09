from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
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


class Faculty(models.Model):
    class Meta:
        verbose_name = _('Факультет')
        verbose_name_plural = _('Факультеты')
        ordering = ['name']

    name = models.CharField(_('Наименование'))

    def __str__(self):
        return f'{self.name}'


class Department(models.Model):
    class Meta:
        verbose_name = _('Кафедра')
        verbose_name_plural = _('Кафедры')

    name = models.CharField(_('Наименование'))

    def __str__(self):
        return f'{self.name}'


class Group(models.Model):
    class Meta:
        verbose_name = _('Учебная группа')
        verbose_name_plural = _('Учебные группы')
        ordering = ['-code']

    class EducationSystem(models.TextChoices):
        regular = 'regular', _('Очная')
        online = 'online', _('Заочная')

    archive = models.BooleanField(_('Архивная'))
    name = models.CharField(_('Наименование'))
    code = models.PositiveIntegerField(_('Код'), unique=True)
    number = models.PositiveIntegerField(_('Номер группы'), blank=True, null=True)
    faculty = models.ForeignKey(
        Faculty,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Физтех-школа (факультет)')
    )
    stream = models.CharField(_('Учебный поток'), blank=True, null=True)
    # noinspection PyUnresolvedReferences
    education_system = models.CharField(
        choices=EducationSystem.choices,
        verbose_name=_('Форма обучения')
    )
    index = models.CharField(_('Индекс группы'), blank=True, null=True)
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Кафедра')
    )

    def __str__(self):
        return f'{self.name}'


class Student(models.Model):
    class Meta:
        verbose_name = _('Студент')
        verbose_name_plural = _('Студенты')
        ordering = ['full_name']

    class Sex(models.TextChoices):
        male = 'M', _('Мужской')
        female = 'F', _('Женский')

    full_name = models.CharField(_('Студент'))
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('Группы')
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        verbose_name=_('Кафедры')
    )
    # faculty  # TODO в таблице краткое наименование, непонятно как его привязывать
    year = models.IntegerField(_('Курс'))
    # noinspection PyUnresolvedReferences
    sex = models.CharField(
        max_length=2,
        choices=Sex.choices,
        verbose_name=_('Пол')
    )
    birthdate = models.DateField(_('Дата рождения'))
    email = models.EmailField(_('Адрес электронной почты физтех'))  # TODO unique=True

    def __str__(self):
        return self.full_name


class Teacher(models.Model):
    class Meta:
        verbose_name = _('Преподаватель')
        verbose_name_plural = _('Преподаватели')
        ordering = ['full_name']

    full_name = models.CharField(_('Преподаватель'))
    email = models.EmailField(_('Адрес электронной почты'), unique=True)

    def __str__(self):
        return self.full_name


class Subject(models.Model):
    class Meta:
        verbose_name = _('Предмет')
        verbose_name_plural = _('Предметы')
        ordering = ['name']

    name = models.CharField(_('Предмет'))
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Кафедра')
    )
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Факультет')
    )
    year = models.IntegerField(_('Курс'))

    def create_subject_groups(self):
        qs = Student.objects.all()
        qs = qs.filter(year=self.year) if self.year is not None else qs
        if self.faculty is not None:
            qs = qs.filter(groups__faculty=self.faculty)
        if self.department is not None:
            qs = qs.filter(departments=self.department)
        qs = qs.distinct().prefetch_related('groups')

        groups_map = defaultdict(list)
        for student in qs:
            for grp in student.groups.all():
                if self.faculty and grp.faculty != self.faculty:
                    continue
                groups_map[grp].append(student)

        with transaction.atomic():
            # SubjectGroup.objects.filter(subject=self).delete()  # TODO удалить старые предметные группы?
            for grp, students in groups_map.items():
                sg = SubjectGroup.objects.create(subject=self)
                sg.students.add(*students)

    def __str__(self):
        return (
            f'{self.name}'
            f'{f' - {self.department}' if self.department else ''}'
            f'{f' - {self.faculty}' if self.faculty else ''}'
            f' - {self.year} курс'
        )


class SubjectGroup(models.Model):
    class Meta:
        verbose_name = _('Предметная группа')
        verbose_name_plural = _('Предметные группы')
        ordering = ['subject']

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='subject_groups',
        verbose_name=_('Предмет')
    )
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
    min_students = models.PositiveIntegerField(_('Минимальное число студентов в группе'), default=0)
    max_students = models.PositiveIntegerField(_('Максимальное число студентов в группе'), default=0)
    deadline = models.DateTimeField(_('Крайнее время подачи заявления на перевод'), null=True, blank=True)

    def get_teacher_names(self, default: any = _('--')):
        qs = self.teachers.all()
        return ', '.join([t.full_name for t in qs]) if qs else default

    def save(self, *args, **kwargs):
        if not self.pk:
            admin_settings = Settings.load()

            if not self.min_students:
                self.min_students = admin_settings.default_min_students
            if not self.max_students:
                self.max_students = admin_settings.default_max_students
            if not self.deadline:
                self.deadline = admin_settings.default_deadline

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.subject.name}{f' - {self.get_teacher_names('')}' if self.get_teacher_names(None) else ''}'


class TransferRequest(models.Model):
    class Meta:
        verbose_name = _('Заявка на перевод')
        verbose_name_plural = _('Заявки на перевод')
        ordering = ['-created_at']

    class Status(models.TextChoices):
        PENDING = 'pending', _('В очереди')
        WAITING_TEACHER = 'waiting_teacher', _('Ждет одобрения преподавателем')
        WAITING_ADMIN = 'waiting_admin', _('Ждет одобрения администратором')
        COMPLETED = 'completed', _('Выполнена')
        REJECTED = 'rejected', _('Отклонено')

    code = models.CharField(
        _('Код заявки'),
        unique=True,
        editable=False,
        help_text=_('Код заявки, формируется автоматически')
    )
    student = models.ForeignKey(
        'Student',
        on_delete=models.CASCADE,  # TODO удалять?
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
    # noinspection PyUnresolvedReferences
    status = models.CharField(
        _('Статус'),
        choices=Status.choices,
        default=Status.PENDING,
        editable=False
    )
    comment_teacher = models.TextField(
        _('Комментарий преподавателя'),
        null=True,
        blank=True,
        editable=False
    )
    comment = models.TextField(
        _('Комментарий'),
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        _('Время подачи заявления'),
        default=timezone.now,
        editable=False
    )

    def complete(self):
        if self.status == self.Status.COMPLETED:
            return

        with transaction.atomic():
            if self.from_group.pk != self.to_group.pk:
                self.from_group.students.remove(self.student)
                self.to_group.students.add(self.student)

            self.status = TransferRequest.Status.COMPLETED
            self.save()

    def reject(self):
        if self.status == self.Status.COMPLETED:
            return
        elif self.status == self.Status.REJECTED:
            return

        self.status = TransferRequest.Status.REJECTED
        self.save()

    def undo(self):
        if self.status != self.Status.COMPLETED and self.status != self.Status.REJECTED:
            return

        with transaction.atomic():
            if self.from_group.pk != self.to_group.pk:
                self.to_group.students.remove(self.student)
                self.from_group.students.add(self.student)

            self.status = TransferRequest.Status.WAITING_ADMIN
            self.save()

    def save(self, *args, **kwargs):
        # Создать уникальный человеко-читаемый код
        if not self.code:
            today_str = timezone.localtime(self.created_at).strftime('%d%m%Y')
            prefix = f'{today_str}'

            with transaction.atomic():
                # Сколько уже записей с таким префиксом?
                last = (
                    TransferRequest.objects
                    .filter(code__startswith=prefix)
                    .order_by('-code')
                    .first()
                )
                if last is None:
                    next_num = 1
                else:
                    last_seq = int(last.code.split('-')[-1])
                    next_num = last_seq + 1

                suffix = str(next_num).zfill(4)
                self.code = f'{prefix}-{suffix}'

        is_new = self._state.adding
        old_status = None

        if not is_new:
            prev = TransferRequest.objects.filter(pk=self.pk).only('status').first()
            if prev:
                old_status = prev.status

        super().save(*args, **kwargs)

        new_status = self.status

        if is_new or (old_status and old_status != new_status):
            TransferRequestLog.objects.create(
                transfer_request=self,
                old_status=old_status or TransferRequest.Status.PENDING,
                new_status=new_status,
                performed_by=getattr(self, '_modified_by', None),
                comment=getattr(self, '_status_comment', None)
            )

    def clean(self):
        super().clean()
        if self.status == TransferRequest.Status.REJECTED and not self.comment:
            raise ValidationError({'comment': _('Комментарий обязателен при отклонении заявки')})

    def __str__(self):
        return f'{self.student.full_name}: {self.from_group} → {self.to_group}'


class TransferRequestLog(models.Model):
    class Meta:
        verbose_name = _('История заявки')
        verbose_name_plural = _('Истории заявок')
        ordering = ['-timestamp']

    transfer_request = models.ForeignKey(
        TransferRequest,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name=_('Заявка на перевод')
    )
    timestamp = models.DateTimeField(
        _('Время действия'),
        default=timezone.now,
        editable=False
    )
    # noinspection PyUnresolvedReferences
    old_status = models.CharField(
        _('Старый статус'),
        choices=TransferRequest.Status.choices
    )
    # noinspection PyUnresolvedReferences
    new_status = models.CharField(
        _('Новый статус'),
        choices=TransferRequest.Status.choices
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Кем выполнено')
    )
    comment = models.TextField(
        _('Комментарий'),
        null=True,
        blank=True
    )

    def __str__(self):
        return (
            f'[{self.timestamp:%d-%m-%Y %H:%M}] '
            f'{self.get_old_status_display()} → {self.get_new_status_display()}'
            f'{f' ({self.performed_by})' if self.performed_by else ''}'
        )
