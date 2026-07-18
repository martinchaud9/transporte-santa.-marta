from django.shortcuts import render, redirect
from core.models import Envio, Usuario
import uuid

def dashboard_view(request):
    envios_pendientes = Envio.objects.filter(estado='pendiente')
    envios_transito = Envio.objects.filter(estado='en_transito')
    envios_entregados = Envio.objects.filter(estado='entregado')
    return render(request, 'casacentral/dashboard.html', {
        'envios_pendientes': envios_pendientes,
        'envios_transito': envios_transito,
        'envios_entregados': envios_entregados,
    })
    
def nuevo_envio_view(request):
    if request.method == 'POST':
        destinatario_nombre = request.POST.get('destinatario_nombre')
        destinatario_dni = request.POST.get('destinatario_dni')
        telefono = request.POST.get('telefono')
        contenido = request.POST.get('contenido')
        precio = request.POST.get('precio')
        modalidad = request.POST.get('modalidad')
        direccion = request.POST.get('direccion', '')

        # Buscar o crear el cliente destinatario
        cliente, creado = Usuario.objects.get_or_create(
            dni=destinatario_dni,
            defaults={
                'username': f"cliente_{destinatario_dni}",
                'first_name': destinatario_nombre,
                'telefono': telefono,
                'rol': 'cliente',
            }
        )

        # Generar código único
        codigo = f"ENV-{str(uuid.uuid4())[:6].upper()}"

        Envio.objects.create(
            codigo=codigo,
            destinatario=cliente,
            contenido=contenido,
            precio=precio,
            modalidad=modalidad,
            direccion_entrega=direccion,
            estado='pendiente',
        )
        return redirect('casacentral_dashboard')
    return redirect('casacentral_dashboard')

def despachar_camion_view(request):
    if request.method == 'POST':
        Envio.objects.filter(estado='pendiente').update(estado='en_transito')
        return redirect('casacentral_dashboard')
    return redirect('casacentral_dashboard')