from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from core.models import Envio, Usuario
from core.notificaciones import notificar_cambio_estado
import uuid
import io
import qrcode

def dashboard_view(request):
    envios_pendientes = Envio.objects.filter(estado='pendiente')
    envios_transito = Envio.objects.filter(estado='en_transito')
    envios_entregados = Envio.objects.filter(estado='entregado')
    envios_recibidos = Envio.objects.exclude(fecha_recepcion__isnull=True).order_by('-fecha_recepcion')
    return render(request, 'casacentral/dashboard.html', {
        'envios_pendientes': envios_pendientes,
        'envios_transito': envios_transito,
        'envios_entregados': envios_entregados,
        'envios_recibidos': envios_recibidos,
    })
    
def nuevo_envio_view(request):
    if request.method == 'POST':
        destinatario_nombre = request.POST.get('destinatario_nombre')
        destinatario_dni = request.POST.get('destinatario_dni')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email', '')
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
                'email': email,
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
        afectados = list(Envio.objects.filter(estado='pendiente'))
        Envio.objects.filter(id__in=[e.id for e in afectados]).update(
            estado='en_transito', fecha_actualizacion=timezone.now(), notificado_demora=False
        )
        for envio in afectados:
            envio.estado = 'en_transito'
            notificar_cambio_estado(envio)
        return redirect('casacentral_dashboard')
    return redirect('casacentral_dashboard')

def qr_envio_view(request, codigo):
    get_object_or_404(Envio, codigo=codigo)
    imagen = qrcode.make(codigo)
    buffer = io.BytesIO()
    imagen.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')