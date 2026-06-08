# v1.1.0
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """POST /api/expense/auth/login/
    Body: {"username": "...", "password": "..."}
    Returns: {"token": "...", "user_id": ..., "username": "..."}
    """
    username = request.data.get("username")
    password = request.data.get("password")
    if not username or not password:
        return Response(
            {"detail": "username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user_id": user.id,
        "username": user.username,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    """POST /api/expense/auth/logout/ — deletes the current token."""
    Token.objects.filter(user=request.user).delete()
    return Response({"detail": "Logged out."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/expense/auth/me/ — current user info."""
    return Response({
        "user_id": request.user.id,
        "username": request.user.username,
        "email": request.user.email,
    })
