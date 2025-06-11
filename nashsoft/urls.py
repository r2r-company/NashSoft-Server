"""
URL configuration for nashsoft project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from backend.views import stock_report
from django.contrib import admin
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

# Swagger schema
schema_view = get_schema_view(
   openapi.Info(
      title="NashSoft API",
      default_version='v1',
      description="📘 Документація по грошових API та взаєморозрахунках",
      contact=openapi.Contact(email="support@nashsoft.local"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path('', stock_report, name='home'),  # Робимо stock_report головною сторінкою
    path('admin/', admin.site.urls),
    path('api/', include('backend.urls')),  # ✅ Додаємо всі маршрути з апки backend
    path('api/', include('settlements.urls')),  # ← ось це додай

    # Swagger / ReDoc
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),


]
