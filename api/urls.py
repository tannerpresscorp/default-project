from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('notes', views.NoteViewSet, basename='note')

urlpatterns = [
    path('health/', views.health),
] + router.urls