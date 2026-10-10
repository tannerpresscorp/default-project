from django.http import JsonResponse
from rest_framework import viewsets

from .models import Product
from .serializers import ProductSerializer


def health(request):
    return JsonResponse({'status': 'ok'})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer