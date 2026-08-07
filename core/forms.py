from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario, Vehiculo

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

class EditarVehiculoForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='empleado'),
        required=False,
        empty_label='Sin asignar',
    )

    class Meta:
        model = Vehiculo
        fields = ['marca', 'modelo', 'tipo', 'empleado']
