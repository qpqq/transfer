from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from .forms import StudentImportForm, GroupImportForm
from .models import Settings, Faculty, Department, Group, Teacher, Student, Subject, SubjectGroup, TransferRequest


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('default_min_students', 'default_max_students', 'default_deadline')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ['name']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'number', 'faculty',
        'stream', 'education_system', 'index',
        'department', 'archive'
    )
    list_filter = ('education_system', 'archive')
    search_fields = ('name', 'code', 'faculty__name', 'department__name')

    change_list_template = 'administration/group_changelist.html'

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path('import/', self.admin_site.admin_view(self.import_view), name='administration_group_import')
        ]

        return custom_urls + urls

    def import_view(self, request):
        if request.method == 'POST':
            form = GroupImportForm(request.POST, request.FILES)

            if form.is_valid():
                ods_file = form.cleaned_data['file']

                try:
                    created, updated, skipped = GroupImportForm.parse_and_save_groups_from_ods(ods_file)

                    self.message_user(
                        request,
                        f'Импорт групп завершён: создано {created}, обновлено {updated}, пропущено {skipped}',
                        level=messages.SUCCESS
                    )

                except Exception as e:
                    self.message_user(request, f'Ошибка: {e}', level=messages.ERROR)

                return redirect('..')

        else:
            form = GroupImportForm()

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'form': form,
        }

        return render(request, 'administration/group_import.html', context)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'get_groups', 'get_departments', 'year', 'sex', 'birthdate', 'email')
    list_filter = ('sex',)
    search_fields = ('full_name', 'groups__name', 'departments__name', 'email')
    filter_horizontal = ('groups', 'departments')

    change_list_template = 'administration/student_changelist.html'

    def get_groups(self, obj):
        return ', '.join([t.name for t in obj.groups.all()])

    def get_departments(self, obj):
        return ', '.join([t.name for t in obj.departments.all()])

    get_groups.short_description = 'Группы'
    get_departments.short_description = 'Кафедры'

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path('import/', self.admin_site.admin_view(self.import_view), name='administration_student_import')
        ]

        return custom_urls + urls

    def import_view(self, request):
        if request.method == 'POST':
            form = StudentImportForm(request.POST, request.FILES)

            if form.is_valid():
                ods_file = form.cleaned_data['file']

                try:
                    created, updated, skipped = StudentImportForm.parse_and_save_students_from_ods(ods_file)

                    self.message_user(
                        request,
                        f'Импорт студентов: создано {created}, обновлено {updated}, пропущено {skipped}',
                        level=messages.SUCCESS
                    )

                except Exception as e:
                    self.message_user(request, f'Ошибка: {e}', level=messages.ERROR)

                return redirect('..')

        else:
            form = StudentImportForm()

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'form': form,
        }

        return render(request, 'administration/student_import.html', context)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email')
    search_fields = ('full_name', 'email')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'faculty', 'year')
    search_fields = ('name', 'department__name', 'faculty__name', 'year')

    change_form_template = 'administration/subject_change_form.html'

    def get_urls(self):
        custom_urls = [
            path(
                '<int:object_id>/make-groups/',
                self.admin_site.admin_view(self.make_groups),
                name='administration_subject_make_groups',
            ),
        ]
        return custom_urls + super().get_urls()

    def make_groups(self, request, object_id):
        subject = self.get_object(request, object_id)
        missing = []
        if not subject.faculty:
            missing.append('факультет')

        if missing:
            messages.warning(request, f'Не указаны: {', '.join(missing)}')
        else:
            subject.create_subject_groups()
            messages.success(request, 'Предметные группы успешно сформированы')

        return redirect(
            reverse('admin:%s_%s_change' % (
                subject._meta.app_label,
                subject._meta.model_name,
            ), args=[object_id])
        )


@admin.register(SubjectGroup)
class SubjectGroupAdmin(admin.ModelAdmin):
    list_display = ('subject', 'get_teachers', 'students_count')
    search_fields = ('subject__name', 'teachers__full_name')
    filter_horizontal = ('teachers', 'students')

    def get_teachers(self, obj):
        return ', '.join([t.full_name for t in obj.teachers.all()])

    def students_count(self, obj):
        return obj.students.count()

    get_teachers.short_description = 'Преподаватели'
    students_count.short_description = 'Число студентов'


@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    list_display = ('code', 'student', 'subject', 'from_group', 'to_group', 'status', 'created_at')
    readonly_fields = ('status', 'comment_teacher', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('student__full_name', 'subject__name')
    actions = ['approve_requests']

    change_form_template = 'administration/transferrequest_change_form.html'

    def save_model(self, request, obj, form, change):
        if not change or 'status' in form.changed_data:
            obj._modified_by = request.user

        super().save_model(request, obj, form, change)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        transfer_request = get_object_or_404(TransferRequest, pk=object_id)
        logs = transfer_request.logs.all().order_by('-timestamp')

        extra_context = extra_context or {}
        extra_context['logs'] = logs

        return super().change_view(
            request, object_id, form_url,
            extra_context=extra_context
        )

    @admin.action(description=_('Одобрить выделенные заявки'))
    def approve_requests(self, request, queryset):
        count = 0

        with transaction.atomic():
            for req in queryset:
                req.complete()
                count += 1

        self.message_user(
            request,
            _('Одобрено заявок: %(count)d') % {'count': count},
            level=messages.SUCCESS
        )

    def get_urls(self):
        custom_urls = [
            path(
                '<int:object_id>/approve/',
                self.admin_site.admin_view(self.approve),
                name='administration_transferrequest_approve'
            ),
            path(
                '<int:object_id>/reject/',
                self.admin_site.admin_view(self.reject),
                name='administration_transferrequest_reject'
            ),
            path(
                '<int:object_id>/undo/',
                self.admin_site.admin_view(self.undo),
                name='administration_transferrequest_undo',
            )
        ]
        return custom_urls + super().get_urls()

    def approve(self, request, object_id):
        transfer_request = self.get_object(request, object_id)

        if transfer_request.status == transfer_request.Status.COMPLETED:
            self.message_user(
                request,
                _('Заявка уже одобрена и перевод выполнен'),
                level=messages.ERROR
            )

        else:
            transfer_request.complete()

        return redirect(
            reverse('admin:%s_%s_change' % (
                transfer_request._meta.app_label,
                transfer_request._meta.model_name,
            ), args=[object_id])
        )

    def reject(self, request, object_id):
        transfer_request = self.get_object(request, object_id)

        if not transfer_request.comment:
            self.message_user(
                request,
                _('При отклонении заявки необходимо указывать комментарий'),
                level=messages.ERROR
            )

        elif transfer_request.status == transfer_request.Status.COMPLETED:
            self.message_user(
                request,
                _('Нельзя отклонить одобренную заявку'),
                level=messages.ERROR
            )

        elif transfer_request.status == transfer_request.Status.REJECTED:
            self.message_user(
                request,
                _('Заявка уже отклонена'),
                level=messages.ERROR
            )

        else:
            transfer_request.reject()

        return redirect(
            reverse('admin:%s_%s_change' % (
                transfer_request._meta.app_label,
                transfer_request._meta.model_name,
            ), args=[object_id])
        )

    def undo(self, request, object_id):
        transfer_request = self.get_object(request, object_id)

        if transfer_request.status != transfer_request.Status.COMPLETED \
                and transfer_request.status != transfer_request.Status.REJECTED:
            self.message_user(
                request,
                _('Заявка должна быть одобрена или отклонена'),
                level=messages.ERROR
            )

        else:
            transfer_request.undo()

        return redirect(
            reverse('admin:%s_%s_change' % (
                transfer_request._meta.app_label,
                transfer_request._meta.model_name,
            ), args=[object_id])
        )
