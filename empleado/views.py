from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Envio, Incidencia

@login_required
def dashboard_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    envios_transito = Envio.objects.filter(estado='en_transito')
    envios_sucursal = Envio.objects.filter(estado='en_sucursal')
    envios_reparto = Envio.objects.filter(estado='en_reparto')
    return render(request, 'empleado/dashboard.html', {
        'envios_transito': envios_transito,
        'envios_sucursal': envios_sucursal,
        'envios_reparto': envios_reparto,
    })

@login_required
def recepcionar_envio_view(request):
    if request.user.rol != 'empleado':
        return redirect('inicio')
    if request.method == 'POST':
        codigo = request.POST.get('codigo')
        try:
            envio = Envio.objects.get(codigo=codigo, estado='en_transito')
            envio.estado = 'en_sucursal'
            envio.save()
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
                envio.save()
        except Envio.DoesNotExist:
            pass
    return redirect('empleado_dashboard')

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