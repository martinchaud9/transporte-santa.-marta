import time

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Envio, Incidencia
from core.zonificacion import geocodificar, calcular_zona, ordenar_ruta
from core.notificaciones import notificar_cambio_estado

def _contexto_dashboard():
    return {
        'envios_transito': Envio.objects.filter(estado='en_transito'),
        'envios_sucursal': Envio.objects.filter(estado='en_sucursal'),
        'envios_reparto': Envio.objects.filter(estado='en_reparto'),
    }

@login_required
def dashboard_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    return render(request, 'empleado/dashboard.html', _contexto_dashboard())

@login_required
def recepcionar_envio_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        codigo = request.POST.get('codigo')
        try:
            envio = Envio.objects.get(codigo=codigo, estado='en_transito')
            envio.estado = 'en_sucursal'
            envio.fecha_recepcion = timezone.now()
            envio.notificado_demora = False
            envio.save()
            notificar_cambio_estado(envio)
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_dashboard')

@login_required
def actualizar_estado_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        nuevo_estado = request.POST.get('estado')
        estados_permitidos = ['en_reparto', 'entregado']
        try:
            envio = Envio.objects.get(id=envio_id)
            if nuevo_estado in estados_permitidos:
                envio.estado = nuevo_estado
                envio.notificado_demora = False
                envio.save()
                notificar_cambio_estado(envio)
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_dashboard')

@login_required
def preparar_reparto_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    candidatos = Envio.objects.filter(estado='en_sucursal', modalidad='domicilio')

    sin_zona_previo = candidatos.filter(zona='')
    for i, envio in enumerate(sin_zona_previo):
        if i > 0:
            time.sleep(1)  # respeta el límite de 1 request/segundo de Nominatim
        coordenadas = geocodificar(envio.direccion_entrega)
        if coordenadas:
            envio.lat, envio.lon = coordenadas
            envio.zona = calcular_zona(*coordenadas)
            envio.save()

    zonas = [
        (clave, etiqueta, ordenar_ruta(list(candidatos.filter(zona=clave))))
        for clave, etiqueta in Envio.ZONA_CHOICES
    ]
    contexto = _contexto_dashboard()
    contexto.update({
        'reparto_zonas': zonas,
        'reparto_sin_zona': candidatos.filter(zona=''),
        'zona_choices': Envio.ZONA_CHOICES,
        'mostrar_reparto': True,
    })
    return render(request, 'empleado/dashboard.html', contexto)

@login_required
def despachar_zona_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        zona = request.POST.get('zona')
        afectados = list(Envio.objects.filter(estado='en_sucursal', modalidad='domicilio', zona=zona))
        Envio.objects.filter(id__in=[e.id for e in afectados]).update(
            estado='en_reparto', fecha_actualizacion=timezone.now(), notificado_demora=False
        )
        for envio in afectados:
            envio.estado = 'en_reparto'
            notificar_cambio_estado(envio)
    return redirect('empleado_preparar_reparto')

@login_required
def asignar_zona_manual_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        zona = request.POST.get('zona')
        zonas_validas = [clave for clave, _ in Envio.ZONA_CHOICES]
        try:
            envio = Envio.objects.get(id=envio_id)
            if zona in zonas_validas:
                envio.zona = zona
                envio.save()
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_preparar_reparto')

@login_required
def registrar_incidencia_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        tipo = request.POST.get('tipo')
        descripcion = request.POST.get('descripcion')
        try:
            envio = Envio.objects.get(id=envio_id)
            Incidencia.objects.create(
                envio=envio,
                registrado_por=request.user,
                tipo=tipo,
                descripcion=descripcion,
            )
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_dashboard')