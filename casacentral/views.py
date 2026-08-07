from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from core.models import Envio, Usuario, Despacho, Incidencia
from core.notificaciones import notificar_cambio_estado
import uuid
import io
import qrcode

def dashboard_view(request):
    envios_pendientes = Envio.objects.filter(estado='pendiente')
    envios_transito = Envio.objects.filter(estado='en_transito')
    envios_entregados = Envio.objects.filter(estado='entregado')
    envios_recibidos = Envio.objects.exclude(fecha_recepcion__isnull=True).order_by('-fecha_recepcion')
    incidencias_sucursal = Incidencia.objects.filter(
        envio__despacho__isnull=False
    ).select_related('envio', 'envio__despacho', 'envio__destinatario', 'registrado_por').order_by('-fecha')
    return render(request, 'casacentral/dashboard.html', {
        'envios_pendientes': envios_pendientes,
        'envios_transito': envios_transito,
        'envios_entregados': envios_entregados,
        'envios_recibidos': envios_recibidos,
        'incidencias_sucursal': incidencias_sucursal,
        'despachos': Despacho.objects.prefetch_related('envios').order_by('-fecha_salida'),
    })
    
def buscar_cliente_view(request):
    dni = request.GET.get('dni', '').strip()
    if not dni:
        return JsonResponse({'existe': False})
    try:
        cliente = Usuario.objects.get(dni=dni, rol='cliente')
        return JsonResponse({
            'existe': True,
            'nombre': cliente.get_full_name() or cliente.first_name,
            'telefono': cliente.telefono,
            'email': cliente.email,
            'envios': cliente.envios.count(),
        })
    except Usuario.DoesNotExist:
        return JsonResponse({'existe': False})

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

        # Si el cliente ya existía, completar los datos de contacto que le falten
        if not creado:
            cambios = []
            if email and not cliente.email:
                cliente.email = email
                cambios.append('email')
            if telefono and not cliente.telefono:
                cliente.telefono = telefono
                cambios.append('telefono')
            if cambios:
                cliente.save(update_fields=cambios)

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
        if afectados:
            despacho = Despacho.objects.create()
            Envio.objects.filter(id__in=[e.id for e in afectados]).update(
                estado='en_transito', despacho=despacho,
                fecha_actualizacion=timezone.now(), notificado_demora=False
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