from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Envio, Pago, Incidencia, Reclamo

class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Datos adicionales', {'fields': ('rol', 'dni', 'telefono')}),
    )

admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Envio)
admin.site.register(Pago)
admin.site.register(Incidencia)
admin.site.register(Reclamo)