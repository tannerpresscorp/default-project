from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'sku', 'created_at', 'updated_at']


class LoginRequestSerializer(serializers.Serializer):
    """Credentials accepted by `POST /api/auth/login/`."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class LoginResponseSerializer(serializers.Serializer):
    """Token issued by `POST /api/auth/login/`."""

    token = serializers.CharField()
    username = serializers.CharField()