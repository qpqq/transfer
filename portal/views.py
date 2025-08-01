from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from administration.enums import Status
from administration.models import Student, SubjectGroup, Subject, TransferRequest, Teacher, evaluate_conditions
from .forms import EmailLoginForm


def login_view(request):
    if request.method == 'POST':
        form = EmailLoginForm(request.POST)

        if form.is_valid():
            user = form.get_user()

            if isinstance(user, Student):
                request.session['student_pk'] = user.pk
                return redirect('portal:cabinet')
            elif isinstance(user, Teacher):
                request.session['teacher_pk'] = user.pk
                return redirect('portal:teacher')

    else:
        form = EmailLoginForm()

    return render(request, 'portal/login.html', {'form': form})


def cabinet_view(request):
    student_pk = request.session.get('student_pk')
    if not student_pk:
        return redirect('portal:login')

    try:
        student = Student.objects.get(pk=student_pk)
    except Student.DoesNotExist:
        request.session.pop('student_pk', None)
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

        transfer_request = (
            TransferRequest.objects
            .filter(student=student, subject=subj)
            .order_by('-created_at')
            .first()
        )

        data.append({
            'subject': subj,
            'current_group': current_group,
            'teacher_names': current_group.get_teacher_names(),
            'all_groups': all_groups,
            'transfer_request': transfer_request
        })

    return render(request, 'portal/cabinet.html', {
        'student': student,
        'data': data,
    })


def teacher_view(request):
    teacher_pk = request.session.get('teacher_pk')
    if not teacher_pk:
        return redirect('portal:login')

    try:
        teacher = Teacher.objects.get(pk=teacher_pk)
    except Teacher.DoesNotExist:
        request.session.pop('teacher_pk', None)
        return redirect('portal:login')

    transfer_requests = (
        TransferRequest.objects
        .filter(status=Status.WAITING_TEACHER,
                to_group__teachers=teacher)
        .select_related('student', 'subject', 'from_group', 'to_group')
    )

    completed = TransferRequest.objects.filter(
        status=Status.COMPLETED
    ).select_related('student')

    subject_groups = (
        SubjectGroup.objects
        .filter(teachers=teacher)
        .select_related('subject')
        .prefetch_related(
            'students',  # текущие
            Prefetch('outgoing_requests', queryset=completed, to_attr='transferred_from'),
            Prefetch('incoming_requests', queryset=completed, to_attr='transferred_to'),
        )
    )

    context = {
        'teacher': teacher,
        'subject_groups': subject_groups,
        'transfer_requests': transfer_requests,
    }
    return render(request, 'portal/teacher.html', context)


@require_http_methods(['POST'])
def transfer_view(request, subject_pk):
    student_pk = request.session.get('student_pk')
    if not student_pk:
        return JsonResponse({
            'status': 'error',
            'message': _('Пожалуйста, сначала войдите в систему.')
        }, status=403)

    try:
        student = Student.objects.get(pk=student_pk)
    except Student.DoesNotExist:
        request.session.pop('student_pk', None)
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

    reason = request.POST.get('reason')
    if not reason:
        return JsonResponse({
            'status': 'error',
            'message': _('Причина подачи заявки обязательна.')
        }, status=400)

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
        }, status=400)

    restrictions = evaluate_conditions(from_group, to_group)

    if restrictions:
        status = Status.PENDING
        response = JsonResponse({
            'status': 'success',
            'message': _(f'Ваша заявка поставлена в очередь, так как {', '.join(restrictions)}.')
        })

    else:
        status = Status.WAITING_TEACHER
        response = JsonResponse({
            'status': 'success',
            'message': _('Ваша заявка на перевод отправлена.')
        })

    TransferRequest.objects.create(
        student=student,
        subject=subject,
        from_group=from_group,
        to_group=to_group,
        status=status,
        reason=reason
    )

    return response


def approve_or_reject(request, pk):
    teacher_pk = request.session.get('teacher_pk')
    if not teacher_pk:
        return JsonResponse({
            'status': 'error',
            'message': _('Пожалуйста, сначала войдите в систему как преподаватель.')
        }, status=403)

    try:
        teacher = Teacher.objects.get(pk=teacher_pk)
    except Teacher.DoesNotExist:
        request.session.pop('teacher_pk', None)
        return JsonResponse({
            'status': 'error',
            'message': _('Преподаватель не найден. Выполните вход заново.')
        }, status=403)

    try:
        req = TransferRequest.objects.get(pk=pk)
    except TransferRequest.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _('Заявка не найдена.')
        }, status=404)

    if req.status != Status.WAITING_TEACHER:
        return JsonResponse({
            'status': 'error',
            'message': _('Заявка не ожидает действия от преподавателя.')
        }, status=403)

    if not req.to_group.teachers.filter(pk=teacher.pk).exists():
        return JsonResponse({
            'status': 'error',
            'message': _('У вас нет прав на действия для этой заявки.')
        }, status=403)

    req._modified_by = teacher
    return req


@require_http_methods(['POST'])
def approve_transfer(request, pk):
    data = approve_or_reject(request, pk)
    if isinstance(data, JsonResponse):
        return data

    req = data

    comment = request.POST.get('comment', '').strip()
    req.comment_teacher = comment

    req.status = Status.WAITING_ADMIN
    req.save()

    return JsonResponse({
        'status': 'success',
        'message': _('Заявка одобрена и отправлена на рассмотрение администратора.')
    })


@require_http_methods(['POST'])
def reject_transfer(request, pk):
    data = approve_or_reject(request, pk)
    if isinstance(data, JsonResponse):
        return data

    req = data

    comment = request.POST.get('comment', '').strip()
    if not comment:
        return JsonResponse({
            'status': 'error',
            'message': _('Комментарий обязателен при отклонении.')
        }, status=400)

    prefix = _('Заявка отклонена преподавателем. Комментарий от преподавателя: ')
    req.comment_teacher = prefix + f'«{comment}»'

    req.status = Status.REJECTED
    req.save()

    return JsonResponse({
        'status': 'success',
        'message': _('Заявка отклонена.')
    })
