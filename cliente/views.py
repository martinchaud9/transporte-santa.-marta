from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Envio, Reclamo

@login_required
def dashboard_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    envios = Envio.objects.filter(destinatario=request.user).order_by('-fecha_registro')
    return render(request, 'cliente/dashboard.html', {
        'envios': envios,
    })

@login_required
def generar_reclamo_view(request):
    if request.user.rol != 'cliente':
        return redirect('inicio')
    if request.method == 'POST':
        envio_id = request.POST.get('envio_id')
        tipo = request.POST.get('tipo')
        descripcion = request.POST.get('descripcion')
        try:
            envio = Envio.objects.get(id=envio_id, destinatario=request.user)
            Reclamo.objects.create(
                envio=envio,
                cliente=request.user,
                tipo=tipo,
                descripcion=descripcion,
            )
        except Envio.DoesNotExist:
            pass
    return redirect('cliente_dashboard')