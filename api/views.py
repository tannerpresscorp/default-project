from django.http import JsonResponse
from rest_framework import viewsets

from .models import Note
from .serializers import NoteSerializer


def health(request):
    return JsonResponse({'status': 'ok'})


class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all().order_by('-created_at')
    serializer_class = NoteSerializer