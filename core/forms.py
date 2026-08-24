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

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if dni and Usuario.objects.filter(dni=dni).exists():
            raise forms.ValidationError('Ya existe un empleado registrado con ese DNI.')
        return dni

    def save(self, commit=True):
        user = super().save(commit=False)
        user.rol = 'empleado'
        if commit:
            user.save()
        return user


def _empleado_ya_asignado(empleado, vehiculo_actual_pk=None):
    """Devuelve True si `empleado` ya tiene otro vehículo asignado (distinto del
    que se está editando, si corresponde)."""
    if not empleado:
        return False
    qs = Vehiculo.objects.filter(empleado=empleado)
    if vehiculo_actual_pk:
        qs = qs.exclude(pk=vehiculo_actual_pk)
    return qs.exists()


class RegistroVehiculoForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='empleado'),
        required=False,
        empty_label='Sin asignar',
    )

    class Meta:
        model = Vehiculo
        fields = ['patente', 'marca', 'modelo', 'tipo', 'empleado']

    def clean_patente(self):
        patente = self.cleaned_data.get('patente')
        if patente and Vehiculo.objects.filter(patente=patente).exists():
            raise forms.ValidationError('Ya existe un vehículo registrado con esa patente.')
        return patente

    def clean_empleado(self):
        empleado = self.cleaned_data.get('empleado')
        if _empleado_ya_asignado(empleado):
            raise forms.ValidationError('Este empleado ya tiene un vehículo asignado.')
        return empleado

class EditarVehiculoForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='empleado'),
        required=False,
        empty_label='Sin asignar',
    )

    class Meta:
        model = Vehiculo
        fields = ['marca', 'modelo', 'tipo', 'empleado']

    def clean_empleado(self):
        empleado = self.cleaned_data.get('empleado')
        if _empleado_ya_asignado(empleado, vehiculo_actual_pk=self.instance.pk):
            raise forms.ValidationError('Este empleado ya tiene un vehículo asignado.')
        return empleado


class ModificarDatosClienteForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono']
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono',
        }
