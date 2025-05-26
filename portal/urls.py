from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('cabinet/', views.cabinet_view, name='cabinet'),
    path('transfer/<int:subject_pk>/', views.transfer_view, name='transfer')
]
