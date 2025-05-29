from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from administration.models import Student, SubjectGroup, Subject, TransferRequest
from .forms import EmailLoginForm


def login_view(request):
    if request.method == 'POST':
        form = EmailLoginForm(request.POST)

        if form.is_valid():
            student = form.get_student()

            request.session['student_id'] = student.pk
            return redirect('portal:cabinet')

    else:
        form = EmailLoginForm()

    return render(request, 'portal/login.html', {'form': form})


def cabinet_view(request):
    student_pk = request.session.get('student_id')
    if not student_pk:
        return redirect('portal:login')

    try:
        student = Student.objects.get(pk=student_pk)
    except Student.DoesNotExist:
        request.session.pop('student_id', None)
        return redirect('portal:login')

    subjects = (
        Subject.objects
        .filter(subject_groups__students=student)
        .distinct()
    )

    data = []

    for subj in subjects:
        current_group = (
            SubjectGroup.objects
            .filter(subject=subj, students=student)
            .prefetch_related('teachers')
            .first()
        )

        all_groups = (
            SubjectGroup.objects
            .filter(subject=subj)
            .prefetch_related('teachers', 'students')
        )

        has_pending = TransferRequest.objects.filter(student=student, subject=subj).exists()

        data.append({
            'subject': subj,
            'current_group': current_group,
            'teacher_names': current_group.get_teacher_names(),
            'all_groups': all_groups,
            'has_pending': has_pending
        })

    return render(request, 'portal/cabinet.html', {
        'student': student,
        'data': data,
    })


@require_http_methods(["POST"])
def transfer_view(request, subject_pk):
    student_pk = request.session.get('student_id')
    if not student_pk:
        return JsonResponse({
            'status': 'error',
            'message': _('Пожалуйста, сначала войдите в систему.')
        }, status=403)

    try:
        student = Student.objects.get(pk=student_pk)
    except Student.DoesNotExist:
        request.session.pop('student_id', None)
        return JsonResponse({
            'status': 'error',
            'message': _('Студент не найден. Выполните вход заново.')
        }, status=403)

    try:
        subject = Subject.objects.get(pk=subject_pk)
    except Subject.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _('Предмет не найден.')
        }, status=404)

    existing = TransferRequest.objects.filter(student=student, subject=subject)
    if existing.exists():
        return JsonResponse({
            'status': 'pending',
            'message': _('Заявка уже находится в обработке.')
        }, status=200)

    new_group_str = request.POST.get('new_group')
    if not new_group_str or not new_group_str.isdigit():
        return JsonResponse({
            'status': 'error',
            'message': _('Неверный параметр новой группы.')
        }, status=400)

    new_group_pk = int(new_group_str)

    try:
        to_group = SubjectGroup.objects.get(pk=new_group_pk, subject=subject)
    except SubjectGroup.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _('Выбранной группы не существует или она не относится к этому предмету.')
        }, status=404)

    from_group = (
        SubjectGroup.objects
        .filter(subject=subject, students=student)
        .first()
    )

    if from_group and from_group.pk == to_group.pk:
        return JsonResponse({
            'status': 'error',
            'message': _('Вы уже состоите в выбранной группе.')  # TODO менять отображение (?)
        })

    MIN_STUDENT_NUMBER = 12
    if len(from_group.students.all()) <= MIN_STUDENT_NUMBER:
        return JsonResponse({
            'status': 'error',
            'message': _(f'В группе не может стать меньше {MIN_STUDENT_NUMBER} студентов.')
        })

    MAX_STUDENT_NUMBER = 18
    if len(to_group.students.all()) >= MAX_STUDENT_NUMBER:
        return JsonResponse({
            'status': 'error',
            'message': _(f'В группе не может быть больше {MAX_STUDENT_NUMBER} студентов.')
        })

    TransferRequest.objects.create(
        student=student,
        subject=subject,
        from_group=from_group,
        to_group=to_group
    )

    return JsonResponse({
        'status': 'success',
        'message': _('Ваша заявка на перевод отправлена.')
    })
