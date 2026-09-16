from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .models import Usuario
from .forms import RegistroClienteForm

def inicio_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.rol == 'admin':
                return redirect('admin_dashboard')
            elif user.rol == 'empleado':
                return redirect('empleado_dashboard')
            else:
                return redirect('cliente_dashboard')
        else:
            return render(request, 'core/inicio.html', {'error': 'Usuario o contraseña incorrectos'})
    return render(request, 'core/inicio.html')

def registro_cliente_view(request):
    if request.method == 'POST':
        dni = request.POST.get('dni')
        password = request.POST.get('password1')
        
        try:
            # Si existe usuario con ese DNI, actualizarlo
            usuario_existente = Usuario.objects.get(dni=dni)
            usuario_existente.first_name = request.POST.get('first_name', usuario_existente.first_name)
            usuario_existente.last_name = request.POST.get('last_name', usuario_existente.last_name)
            usuario_existente.email = request.POST.get('email', usuario_existente.email)
            usuario_existente.telefono = request.POST.get('telefono', usuario_existente.telefono)
            usuario_existente.username = request.POST.get('username', usuario_existente.username)
            usuario_existente.set_password(password)
            usuario_existente.save()
            return redirect('inicio')
        except Usuario.DoesNotExist:
            # Si no existe, crear uno nuevo
            form = RegistroClienteForm(request.POST)
            if form.is_valid():
                form.save()
                return redirect('inicio')
            else:
                print(form.errors)
                return redirect('inicio')
    return redirect('inicio')


def logout_view(request):
    logout(request)
    return redirect('inicio')