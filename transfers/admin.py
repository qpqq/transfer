from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.translation import gettext_lazy as _

from .forms import StudentImportForm, GroupImportForm
from .models import Group, Teacher, Student, Subject, SubjectGroup, TransferRequest


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'group', 'sex', 'email')
    list_filter = ('sex',)
    search_fields = ('full_name', 'group__name', 'email')

    change_list_template = 'admin/transfers/student_changelist.html'

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path('import/', self.admin_site.admin_view(self.import_view), name='transfers_student_import')
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
                        f'Импорт студентов: создано {created}, обновлено {updated}, пропущено {skipped}.',
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

        return render(request, 'admin/transfers/student_import.html', context)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'number', 'faculty',
        'stream', 'education_system', 'index',
        'department', 'archive'
    )
    list_filter = ('education_system', 'archive')
    search_fields = ('name', 'code', 'faculty', 'department')

    change_list_template = 'admin/transfers/group_changelist.html'

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [path('import/', self.admin_site.admin_view(self.import_view), name='transfers_group_import')]

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
                        f'Импорт групп завершён: создано {created}, обновлено {updated}, пропущено {skipped}.',
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

        return render(request, 'admin/transfers/group_import.html', context)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email')
    search_fields = ('full_name', 'email')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(SubjectGroup)
class SubjectGroupAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'get_teachers')
    search_fields = ('subject__name', 'name', 'teachers__full_name')
    list_filter = ('subject', 'teachers')
    filter_horizontal = ('teachers', 'students')

    def get_teachers(self, obj):
        return ', '.join([t.full_name for t in obj.teachers.all()])

    get_teachers.short_description = 'Преподаватели'


@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'from_group', 'to_group', 'created_at')
    list_filter = ('subject', 'created_at')
    search_fields = ('student__full_name', 'subject__name', 'from_group__name', 'to_group__name')
    actions = ['approve_requests', 'reject_requests']

    @admin.action(description=_('Одобрить выделенные заявки'))
    def approve_requests(self, request, queryset):
        approved = 0

        with transaction.atomic():
            for req in queryset:
                student = req.student
                from_grp = req.from_group
                to_grp = req.to_group

                from_grp.students.remove(student)
                to_grp.students.add(student)

                req.delete()
                approved += 1

        self.message_user(
            request,
            _('Одобрено заявок: %(count)d') % {'count': approved},
            level=messages.SUCCESS
        )

    @admin.action(description=_('Отклонить выделенные заявки'))
    def reject_requests(self, request, queryset):
        count = queryset.count()

        with transaction.atomic():
            queryset.delete()

        self.message_user(
            request,
            _('Отклонено заявок: %(count)d') % {'count': count},
            level=messages.WARNING
        )
