from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('cabinet/', views.cabinet_view, name='cabinet'),
    path('teacher/', views.teacher_view, name='teacher'),
    path('transfer/create/<int:subject_pk>/', views.transfer_view, name='transfer'),
    path('transfer/approve/<int:pk>/', views.approve_transfer, name='approve_transfer'),
    path('transfer/reject/<int:pk>/', views.reject_transfer, name='reject_transfer'),
]
