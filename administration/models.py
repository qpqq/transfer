from collections import defaultdict

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .enums import EducationSystem, Sex, Semester, Status
from .settings import Settings
from .utils import current_semester, current_year


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

    full_name = models.CharField(_('Студент'))
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('Группы'),
        related_name='students'
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        verbose_name=_('Кафедры')
    )
    # faculty  # TODO в таблице краткое наименование, непонятно как его привязывать
    year = models.PositiveIntegerField(_('Курс'))
    # noinspection PyUnresolvedReferences
    sex = models.CharField(
        max_length=2,
        choices=Sex.choices,
        verbose_name=_('Пол')
    )
    birthdate = models.DateField(_('Дата рождения'))
    email = models.EmailField(_('Адрес электронной почты физтех'), unique=True)

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

    def get_full_name(self):
        return self.full_name


class Subject(models.Model):
    class Meta:
        verbose_name = _('Предмет')
        verbose_name_plural = _('Предметы')
        ordering = ['-year', 'semester', 'course', 'faculty', 'department']

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
    course = models.PositiveIntegerField(_('Курс'))
    # noinspection PyUnresolvedReferences
    semester = models.CharField(
        max_length=2,
        choices=Semester.choices,
        default=current_semester,
        verbose_name=_('Семестр')
    )
    year = models.PositiveIntegerField(
        default=current_year,
        verbose_name=_('Год')
    )

    def create_subject_groups(self):
        qs = Student.objects.all()
        qs = qs.filter(year=self.course) if self.course is not None else qs
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
            f' - {self.course} курс'
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

        process_pending_requests_for_groups([self.pk])

    def __str__(self):
        return f'{self.subject.name}{f' - {self.get_teacher_names('')}' if self.get_teacher_names(None) else ''}'


class TransferRequest(models.Model):
    class Meta:
        verbose_name = _('Заявка на перевод')
        verbose_name_plural = _('Заявки на перевод')
        ordering = ['-created_at']

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
    reason = models.TextField(
        _('Прична студента'),
        null=True,
        blank=True,
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
        if self.status == Status.COMPLETED:
            return

        with transaction.atomic():
            if self.from_group.pk != self.to_group.pk:
                self.from_group.students.remove(self.student)
                self.to_group.students.add(self.student)

            self.status = Status.COMPLETED
            self.save()

    def reject(self):
        if self.status == Status.COMPLETED:
            return
        elif self.status == Status.REJECTED:
            return

        self.status = Status.REJECTED
        self.save()

    def undo(self):
        if self.status != Status.COMPLETED and self.status != Status.REJECTED:
            return

        with transaction.atomic():
            if self.from_group.pk != self.to_group.pk:
                self.to_group.students.remove(self.student)
                self.from_group.students.add(self.student)

            self.status = Status.WAITING_ADMIN
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

        old = None
        if not self._state.adding:
            old = self.__class__.objects.filter(pk=self.pk).first()

        super().save(*args, **kwargs)

        if old:
            for field in self._meta.get_fields():
                if not hasattr(field, 'attname') or field.auto_created:
                    continue

                name = field.attname
                old_val = getattr(old, name)
                new_val = getattr(self, name)
                if old_val != new_val:
                    FieldChangeLog.objects.create(
                        content_type=ContentType.objects.get_for_model(self),
                        object_id=self.pk,
                        field_name=name,
                        old_value=str(old_val),
                        new_value=str(new_val),
                        modified_by=getattr(self, '_modified_by', None),
                    )

            old_status = getattr(old, 'status')
            new_status = getattr(self, 'status')
            if new_status == Status.COMPLETED and old_status != Status.COMPLETED:
                process_pending_requests_for_groups([
                    self.from_group_id,
                    self.to_group_id,
                ])

    def clean(self):
        super().clean()
        if self.status == Status.REJECTED and not self.comment:
            raise ValidationError({'comment': _('Комментарий обязателен при отклонении заявки')})

    def __str__(self):
        return f'{self.student.full_name}: {self.from_group} → {self.to_group}'


class FieldChangeLog(models.Model):
    class Meta:
        ordering = ['-timestamp']

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='field_change_logs'
    )
    object_id = models.PositiveIntegerField()
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    modifier_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='field_change_logs_modifier'
    )
    modifier_object_id = models.PositiveIntegerField(null=True, blank=True)
    modified_by = GenericForeignKey('modifier_content_type', 'modifier_object_id')
    timestamp = models.DateTimeField(default=timezone.now)


def evaluate_conditions(from_group: SubjectGroup, to_group: SubjectGroup):
    errors = []

    # в from_group после ухода студента не меньше min_students
    if from_group.students.count() <= from_group.min_students:
        errors.append(f'в группе не может стать меньше {from_group.min_students} студентов')

    # в to_group не больше max_students
    if to_group.students.count() >= to_group.max_students:
        errors.append(f'в группе не может быть больше {to_group.max_students} студентов')

    # дедлайн подачи не истек
    if to_group.deadline and timezone.now() > to_group.deadline:
        errors.append(f'срок подачи заявлений на перевод истёк')

    return errors


def process_pending_requests_for_groups(group_ids: list[int]):
    pending_qs = TransferRequest.objects.filter(
        status=Status.PENDING
    ).filter(
        Q(from_group_id__in=group_ids) | Q(to_group_id__in=group_ids)
    )

    for req in pending_qs.select_related('student', 'from_group', 'to_group'):
        errors = evaluate_conditions(req.from_group, req.to_group)
        if not errors:
            req.status = Status.WAITING_TEACHER
            req.save()
