from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario, Vehiculo, Envio, Pago

class RegistroClienteForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'dni', 'telefono', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.rol = 'cliente'
        if commit:
            user.save()
        return user
    
class RegistroEmpleadoForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'email', 'dni', 'telefono', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.rol = 'empleado'
        if commit:
            user.save()
        return user

class RegistroVehiculoForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='empleado'),
        required=False,
        empty_label='Sin asignar',
    )

    class Meta:
        model = Vehiculo
        fields = ['patente', 'marca', 'modelo', 'tipo', 'empleado']

class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['envio', 'monto', 'medio_pago', 'es_parcial', 'justificacion']

    def clean(self):
        cleaned = super().clean()
        envio = cleaned.get('envio')
        es_parcial = cleaned.get('es_parcial')
        justificacion = cleaned.get('justificacion')

        if es_parcial:
            if not justificacion:
                raise forms.ValidationError('Los pagos parciales requieren una justificación.')
            if envio:
                envios_cliente = Envio.objects.filter(destinatario=envio.destinatario).exclude(id=envio.id)
                cantidad_pagados = sum(1 for e in envios_cliente if e.esta_pagado)
                if cantidad_pagados <= 3:
                    raise forms.ValidationError(
                        'Los pagos parciales solo están permitidos para clientes con más de 3 envíos pagados previamente.'
                    )
        return cleaned