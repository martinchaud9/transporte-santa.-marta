from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from core.models import Envio, Usuario, Despacho, Incidencia, Vehiculo
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
        # Camiones que ya salieron: para el historial de incidencias de la sucursal.
        'despachos': Despacho.objects.filter(fecha_salida__isnull=False).prefetch_related('envios').order_by('-fecha_salida'),
        # Camiones que todavía se están cargando (pueden recibir más paquetes).
        'despachos_abiertos': Despacho.objects.filter(fecha_salida__isnull=True).prefetch_related('envios__destinatario').order_by('fecha_creacion'),
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

        try:
            peso = Decimal(request.POST.get('peso', ''))
            if peso <= 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, 'Ingresá un peso válido para el paquete (en kilogramos).')
            return redirect('casacentral_dashboard')

        if peso > Despacho.CAPACIDAD_MAX_PESO_KG:
            messages.error(
                request,
                f'Un paquete de {peso} kg no entra en ningún camión: el límite por camión es '
                f'{Despacho.CAPACIDAD_MAX_PESO_KG} kg.'
            )
            return redirect('casacentral_dashboard')

        # Un paquete a domicilio tiene que entrar en el furgón de reparto; si es
        # más pesado, nunca se podría entregar.
        if modalidad == 'domicilio' and peso > Vehiculo.CAPACIDAD_MAX_PESO_KG:
            messages.error(
                request,
                f'Un paquete de {peso} kg no entra en el furgón de reparto (máximo '
                f'{Vehiculo.CAPACIDAD_MAX_PESO_KG} kg). Registralo con retiro en sucursal.'
            )
            return redirect('casacentral_dashboard')

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

        # Asigna el paquete al camión que se está cargando; si ya no soporta
        # el peso de este paquete, abre uno nuevo automáticamente.
        despacho = Despacho.obtener_o_crear_abierto(peso)

        Envio.objects.create(
            codigo=codigo,
            destinatario=cliente,
            despacho=despacho,
            contenido=contenido,
            peso=peso,
            precio=precio,
            modalidad=modalidad,
            direccion_entrega=direccion,
            estado='pendiente',
        )
        messages.success(
            request,
            f'✓ Envío {codigo} registrado y asignado al Camión #{despacho.id} '
            f'({despacho.total_envios} paquete(s), '
            f'{despacho.peso_total} kg de {Despacho.CAPACIDAD_MAX_PESO_KG} kg).'
        )
        return redirect('casacentral_dashboard')
    return redirect('casacentral_dashboard')

def despachar_camion_view(request):
    if request.method == 'POST':
        despacho_id = request.POST.get('despacho_id')
        try:
            despacho = Despacho.objects.get(id=despacho_id, fecha_salida__isnull=True)
        except Despacho.DoesNotExist:
            messages.error(request, 'Ese camión ya fue despachado o no existe.')
            return redirect('casacentral_dashboard')

        if despacho.total_envios == 0:
            messages.error(request, f'El Camión #{despacho.id} no tiene paquetes para despachar.')
            return redirect('casacentral_dashboard')

        afectados = list(
            despacho.envios.filter(estado='pendiente').exclude(solicitudes_cancelacion__estado='pendiente')
        )
        retenidos = despacho.envios.filter(estado='pendiente', solicitudes_cancelacion__estado='pendiente').count()
        despacho.fecha_salida = timezone.now()
        despacho.save(update_fields=['fecha_salida'])
        Envio.objects.filter(id__in=[e.id for e in afectados]).update(
            estado='en_transito', fecha_actualizacion=timezone.now(), notificado_demora=False
        )
        for envio in afectados:
            envio.estado = 'en_transito'
            notificar_cambio_estado(envio)
        if retenidos:
            messages.warning(
                request,
                f'✓ Camión #{despacho.id} despachado con {len(afectados)} paquetes. '
                f'{retenidos} paquete(s) con cancelación en trámite se dejaron afuera hasta que un administrador la resuelva.'
            )
        else:
            messages.success(request, f'✓ Camión #{despacho.id} despachado con {len(afectados)} paquetes.')
        return redirect('casacentral_dashboard')
    return redirect('casacentral_dashboard')

def qr_envio_view(request, codigo):
    get_object_or_404(Envio, codigo=codigo)
    imagen = qrcode.make(codigo)
    buffer = io.BytesIO()
    imagen.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')