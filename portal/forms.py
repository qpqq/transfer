from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from administration.models import Student, Teacher


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label=_('Ваш e-mail'))

    def clean_email(self):
        email = self.cleaned_data['email']

        try:
            Student.objects.get(email=email)
            return email
        except Student.DoesNotExist:
            pass

        try:
            Teacher.objects.get(email=email)
            return email
        except Teacher.DoesNotExist:
            pass

        raise ValidationError(
            _('Пользователь с таким e-mail не найден.'),
            code='user_not_found'
        )

    def get_user(self):
        try:
            return Student.objects.get(email=self.cleaned_data['email'])
        except Student.DoesNotExist:
            return Teacher.objects.get(email=self.cleaned_data['email'])
