from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Product
from .serializers import LoginRequestSerializer, LoginResponseSerializer, ProductSerializer


def health(request):
    return JsonResponse({'status': 'ok'})


@extend_schema(request=LoginRequestSerializer, responses=LoginResponseSerializer)
class LoginView(ObtainAuthToken):
    """Exchange username + password for a token (`Authorization: Token <key>`)."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.get_username()})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'sku', 'description']