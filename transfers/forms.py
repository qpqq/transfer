import io

import pandas as pd
from django import forms
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import Group, Student


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
            idx_sex = header.index('Пол')
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
                sex_text = get_cell(idx_sex)
                email = get_cell(idx_email)

                if not full_name or not email:
                    skipped += 1
                    continue

                sex = ''
                if sex_text.lower() == 'мужской':
                    sex = Student.Sex.male
                elif sex_text.lower() == 'женский':
                    sex = Student.Sex.female

                group_obj = Group.objects.filter(name=group_name).first()

                try:
                    stu = Student.objects.get(email=email)

                    changed = False
                    if stu.full_name != full_name:
                        stu.full_name = full_name
                        changed = True
                    if stu.group_id != (group_obj.id if group_obj else None):
                        stu.group = group_obj
                        changed = True
                    if stu.sex != sex:
                        stu.sex = sex
                        changed = True

                    if changed:
                        to_update.append(stu)
                        updated += 1

                except Student.DoesNotExist:
                    to_create.append(
                        Student(
                            full_name=full_name,
                            group=group_obj,
                            sex=sex,
                            email=email
                        )
                    )

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
                    return '' if pd.isna(v) else str(v).strip()

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

                edu = ''
                if edu_text.lower() == 'очная':
                    edu = Group.EducationSystem.regular
                elif edu_text.lower() == 'заочная':
                    edu = Group.EducationSystem.online

                index_val = index_text if index_text else ''
                department = dept if dept else ''

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
                    if grp.faculty != faculty:
                        grp.faculty = faculty
                        changed = True
                    if grp.stream != stream:
                        grp.stream = stream
                        changed = True
                    if grp.education_system != edu:
                        grp.education_system = edu
                        changed = True
                    if grp.index != index_val:
                        grp.index = index_val
                        changed = True
                    if grp.department != department:
                        grp.department = department
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
                        faculty=faculty,
                        stream=stream,
                        education_system=edu,
                        index=index_val,
                        department=department
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
