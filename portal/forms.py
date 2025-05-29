from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from administration.models import Student


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label=_('Ваш e-mail'))

    def clean_email(self):
        email = self.cleaned_data['email']

        try:
            Student.objects.get(email=email)
        except Student.DoesNotExist:
            raise ValidationError(
                _('Студент с таким e-mail не найден.'),
                code='student_not_found'
            )

        return email

    def get_student(self):
        return Student.objects.get(email=self.cleaned_data['email'])
