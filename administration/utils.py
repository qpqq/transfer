from django.utils import timezone

from .enums import Semester


def current_semester():
    if timezone.now().month < 7:
        return Semester.spring

    return Semester.fall

def current_year():
    return timezone.now().year