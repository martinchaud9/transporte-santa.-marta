from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from .models import Usuario, Envio, RepartoActivo
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

def rastrear_envio_view(request):
    """Seguimiento público: cualquiera con el código del envío puede ver su
    estado sin necesidad de tener cuenta ni iniciar sesión — como en
    cualquier empresa de logística. No se muestran datos sensibles (dirección
    exacta, teléfono, email, DNI ni precio), solo el estado del envío."""
    codigo = (request.GET.get('codigo') or '').strip().upper()
    envio = None
    buscado = bool(codigo)
    if buscado:
        envio = Envio.objects.filter(codigo=codigo).first()
    return render(request, 'core/rastreo.html', {'codigo_buscado': codigo, 'envio': envio, 'buscado': buscado})


def ubicacion_envio_view(request, codigo):
    """Devuelve en JSON la última posición GPS conocida de quien está
    repartiendo el envío (público, sin login — lo consume el JS del mapa en
    /rastrear/ y en el panel del cliente). Solo hay datos mientras el envío
    está 'en_reparto' y alguien mandó su ubicación al menos una vez."""
    envio = Envio.objects.filter(codigo=codigo.strip().upper(), estado='en_reparto').first()
    if not envio or not envio.zona:
        return JsonResponse({'disponible': False})

    reparto = RepartoActivo.objects.filter(zona=envio.zona).first()
    if not reparto or reparto.ultima_lat is None or reparto.fecha_ultima_ubicacion is None:
        return JsonResponse({'disponible': False})

    hace_segundos = int((timezone.now() - reparto.fecha_ultima_ubicacion).total_seconds())
    return JsonResponse({
        'disponible': True,
        'lat': reparto.ultima_lat,
        'lon': reparto.ultima_lon,
        'hace_segundos': hace_segundos,
    })


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