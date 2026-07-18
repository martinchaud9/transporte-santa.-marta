from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('administrador/', include('administrador.urls')),
    path('empleado/', include('empleado.urls')),
    path('cliente/', include('cliente.urls')),
    path('casacentral/', include('casacentral.urls')),
]