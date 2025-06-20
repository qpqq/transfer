import io
from datetime import datetime

import pandas as pd
from django import forms
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .enums import EducationSystem, Sex
from .models import Faculty, Department, Group, Student


class StudentImportForm(forms.Form):
    file = forms.FileField(
        label=_('ODS-файл с данными студентов'),
        help_text=_('Загрузите .ods-файл с данными студентов'),
        validators=[FileExtensionValidator(['ods'])],
        widget=forms.FileInput(attrs={
            'accept': '.ods',
            'required': True,
        })
    )

    @staticmethod
    def parse_and_save_students_from_ods(file_obj):
        df = pd.read_excel(io.BytesIO(file_obj.read()), engine='odf', header=None)

        # Находим строку с заголовками
        header_row = None
        for idx, row in df.iterrows():
            values = [str(x).strip() if not pd.isna(x) else '' for x in row.tolist()]
            if 'Студент' in values:
                header_row = idx
                break
        if header_row is None:
            raise ValueError('Не найдена строка с заголовками.')

        # Вытаскиваем список заголовков и данные под ними
        header = [str(x).strip() if not pd.isna(x) else '' for x in df.iloc[header_row].tolist()]
        data = df.iloc[header_row + 1:].reset_index(drop=True)

        try:
            idx_full_name = header.index('Студент')
            idx_group = header.index('Группа')
            idx_department = header.index('Кафедра')
            idx_year = header.index('Курс')
            idx_sex = header.index('Пол')
            idx_birthdate = header.index('Дата рождения')
            idx_email = header.index('Адрес электронной почты физтех')
        except ValueError as e:
            raise ValueError(f'В заголовке отсутствует колонка: {e}')

        to_create, to_update = [], []
        created = updated = skipped = 0

        with transaction.atomic():
            for _, row in data.iterrows():
                def get_cell(j):
                    v = row[j]
                    return '' if pd.isna(v) else str(v).strip()

                full_name = get_cell(idx_full_name)
                group_name = get_cell(idx_group)
                dept_name = get_cell(idx_department)
                year_text = get_cell(idx_year)
                sex_text = get_cell(idx_sex)
                email = get_cell(idx_email)
                birthdate_txt = get_cell(idx_birthdate)

                if not full_name or not email:
                    skipped += 1
                    continue

                dept_obj = None
                if dept_name:
                    dept_obj, _ = Department.objects.get_or_create(name=dept_name)

                try:
                    year = int(year_text)
                except ValueError:
                    year = None

                try:
                    birthdate = datetime.strptime(birthdate_txt, '%d.%m.%Y').date()
                except (ValueError, TypeError):
                    birthdate = None

                sex = ''
                if sex_text.lower() == 'мужской':
                    sex = Sex.male
                elif sex_text.lower() == 'женский':
                    sex = Sex.female

                group_obj = Group.objects.filter(name=group_name).first()

                try:
                    stu = Student.objects.get(email=email)

                    changed = False
                    if stu.full_name != full_name:
                        stu.full_name = full_name
                        changed = True
                    if stu.sex != sex:
                        stu.sex = sex
                        changed = True
                    if stu.year != year:
                        stu.year = year
                        changed = True
                    if stu.birthdate != birthdate:
                        stu.birthdate = birthdate
                        changed = True

                    if changed:
                        stu.save()
                        updated += 1

                    if group_obj:
                        stu.groups.add(group_obj)
                    if dept_obj:
                        stu.departments.add(dept_obj)

                except Student.DoesNotExist:
                    stu = Student.objects.create(
                        full_name=full_name,
                        year=year,
                        sex=sex,
                        birthdate=birthdate,
                        email=email
                    )

                    if group_obj:
                        stu.groups.add(group_obj)
                    if dept_obj:
                        stu.departments.add(dept_obj)

                    created += 1

            if to_create:
                Student.objects.bulk_create(to_create)
            if to_update:
                Student.objects.bulk_update(to_update, ['full_name', 'group', 'sex'])

        return created, updated, skipped


class GroupImportForm(forms.Form):
    file = forms.FileField(
        label='ODS-файл с данными групп',
        help_text='Разрешается только .ods',
        validators=[FileExtensionValidator(allowed_extensions=['ods'])],
        widget=forms.FileInput(attrs={
            'accept': '.ods',
            'required': True,
        })
    )

    @staticmethod
    def parse_and_save_groups_from_ods(file_obj):
        df = pd.read_excel(io.BytesIO(file_obj.read()), engine='odf', header=None)

        # Находим строку с заголовками
        header_row = None
        for idx, row in df.iterrows():
            values = [str(x).strip() if not pd.isna(x) else '' for x in row.tolist()]
            if 'Код' in values:
                header_row = idx
                break
        if header_row is None:
            raise ValueError('Не найдена строка с заголовками.')

        # Вытаскиваем список заголовков и данные под ними
        header = [str(x).strip() if not pd.isna(x) else '' for x in df.iloc[header_row].tolist()]
        data = df.iloc[header_row + 1:].reset_index(drop=True)

        try:
            idx_archive = header.index('Архивная')
            idx_name = header.index('Наименование')
            idx_code = header.index('Код')
            idx_number = header.index('Номер группы')
            idx_faculty = header.index('Физтех-школа (факультет)')
            idx_stream = header.index('Учебный поток')
            idx_edu = header.index('Форма обучения')
            idx_index = header.index('Индекс группы')
            idx_department = header.index('Кафедра')
        except ValueError as e:
            raise ValueError(f'В заголовке отсутствует колонка: {e}')

        to_create, to_update = [], []
        skipped = created = updated = 0

        with transaction.atomic():
            for _, row in data.iterrows():
                def get_cell(col_idx):
                    v = row[col_idx]
                    return None if pd.isna(v) else str(v).strip()

                archive_text = get_cell(idx_archive)
                name = get_cell(idx_name)
                code_text = get_cell(idx_code)
                number_text = get_cell(idx_number)
                faculty = get_cell(idx_faculty)
                stream = get_cell(idx_stream)
                edu_text = get_cell(idx_edu)
                index_text = get_cell(idx_index)
                dept = get_cell(idx_department)

                if not name or not code_text:
                    skipped += 1
                    continue

                faculty_obj = None
                if faculty:
                    faculty_obj, _ = Faculty.objects.get_or_create(name=faculty)

                department_obj = None
                if dept:
                    department_obj, _ = Department.objects.get_or_create(name=dept)

                # Преобразуем код в int (убрав пробелы/неразрывные пробелы)
                try:
                    code = int(code_text.replace('\xa0', '').replace(' ', ''))
                except ValueError:
                    skipped += 1
                    continue

                archive = False
                if archive_text.lower() in ('да', 'true', '1'):
                    archive = True

                number = None
                if number_text:
                    try:
                        number = int(number_text)
                    except ValueError:
                        number = None

                edu = None
                if edu_text.lower() == 'очная':
                    edu = EducationSystem.regular
                elif edu_text.lower() == 'заочная':
                    edu = EducationSystem.online

                try:
                    grp = Group.objects.get(code=code)
                    changed = False

                    if grp.archive != archive:
                        grp.archive = archive
                        changed = True
                    if grp.name != name:
                        grp.name = name
                        changed = True
                    if grp.number != number:
                        grp.number = number
                        changed = True
                    if grp.faculty_id != (faculty_obj.id if faculty_obj else None):
                        grp.faculty = faculty_obj
                        changed = True
                    if grp.stream != stream:
                        grp.stream = stream
                        changed = True
                    if grp.education_system != edu:
                        grp.education_system = edu
                        changed = True
                    if grp.index != index_text:
                        grp.index = index_text
                        changed = True
                    if grp.department_id != (department_obj.id if department_obj else None):
                        grp.department = department_obj
                        changed = True

                    if changed:
                        to_update.append(grp)
                        updated += 1

                except Group.DoesNotExist:
                    to_create.append(Group(
                        archive=archive,
                        name=name,
                        code=code,
                        number=number,
                        faculty=faculty_obj,
                        stream=stream,
                        education_system=edu,
                        index=index_text,
                        department=department_obj
                    ))
                    created += 1

            if to_create:
                Group.objects.bulk_create(to_create)
            if to_update:
                Group.objects.bulk_update(
                    to_update,
                    [
                        'archive', 'name', 'number', 'faculty',
                        'stream', 'education_system', 'index', 'department'
                    ]
                )

        return created, updated, skipped
