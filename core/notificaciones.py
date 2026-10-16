from django.conf import settings
from django.core.mail import send_mail as _send_mail


def enviar(asunto, cuerpo, destinatario):
    """Envía un correo sin interrumpir la operación si falla, pero dejando
    el error visible en la terminal del servidor para poder diagnosticarlo."""
    if not destinatario:
        print(f'[email] NO ENVIADO ("{asunto}"): el destinatario no tiene email cargado.')
        return
    try:
        _send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [destinatario], fail_silently=False)
    except Exception as e:
        print(f'[email] ERROR al enviar "{asunto}" a {destinatario}: {type(e).__name__}: {e}')

MENSAJES_ESTADO = {
    'en_transito': (
        'Tu envío salió de Buenos Aires',
        'Tu paquete {codigo} salió de Casa Central y está en camino a Santiago del Estero.',
    ),
    'en_sucursal': (
        'Tu envío llegó a la sucursal',
        'Tu paquete {codigo} llegó a la sucursal de Santiago del Estero.',
    ),
    'en_reparto': (
        'Tu envío está en reparto',
        'Tu paquete {codigo} salió a reparto.',
    ),
    'entregado': (
        'Tu envío fue entregado',
        'Tu paquete {codigo} fue entregado con éxito. ¡Gracias por elegir Santa Marta!',
    ),
    'cancelado': (
        'Tu envío fue cancelado',
        'Tu paquete {codigo} fue cancelado. Si no lo solicitaste o tenés dudas, comunicate con la sucursal.',
    ),
    'devuelto': (
        'Tu envío fue devuelto a Buenos Aires',
        'Tu paquete {codigo} fue devuelto a Casa Central en Buenos Aires porque no pudo ser retirado a tiempo. '
        'Comunicate con la sucursal para coordinar un nuevo envío.',
    ),
}


def notificar_cambio_estado(envio):
    datos = MENSAJES_ESTADO.get(envio.estado)
    if not datos:
        return
    asunto, cuerpo = datos
    enviar(asunto, cuerpo.format(codigo=envio.codigo), envio.destinatario.email)


def notificar_recibo_pago(pago):
    envio = pago.envio
    lineas = [
        'Recibimos tu pago. Detalle:',
        '',
        f'  Envío: {envio.codigo}',
        f'  Monto: ${pago.monto}',
        f'  Medio de pago: {pago.get_medio_pago_display()}',
        f'  Fecha: {pago.fecha.strftime("%d/%m/%Y %H:%M") if pago.fecha else ""}',
    ]
    saldo = envio.saldo_pendiente
    if saldo > 0:
        lineas.append(f'  Saldo pendiente: ${saldo}')
    else:
        lineas.append('  Estado: Pagado en su totalidad')
    lineas.append('')
    lineas.append('¡Gracias por elegir Santa Marta!')
    enviar(f'Recibo de pago — {envio.codigo}', '\n'.join(lineas), envio.destinatario.email)


def notificar_comprobante_recibido(pago):
    envio = pago.envio
    enviar(
        f'Recibimos tu comprobante — {envio.codigo}',
        (
            f'Recibimos el comprobante de tu transferencia por ${pago.monto} para el envío {envio.codigo}.\n\n'
            'Un administrador va a verificar que la transferencia haya llegado a la cuenta de Santa Marta. '
            'Te vamos a avisar por este mismo medio cuando quede confirmado.'
        ),
        envio.destinatario.email,
    )


def notificar_intento_fallido(envio):
    if envio.intentos_entrega >= envio.MAX_INTENTOS_ENTREGA:
        asunto = 'Tu paquete te espera en la sucursal'
        cuerpo = (
            f'Visitamos tu domicilio para entregar el paquete {envio.codigo} y nuevamente no había nadie. '
            'Como ya se realizaron los dos intentos de entrega, el paquete quedó retenido en la sucursal '
            'de Santiago del Estero. Por favor acercate a retirarlo con tu DNI.'
        )
    else:
        asunto = 'No pudimos entregar tu paquete'
        cuerpo = (
            f'Visitamos tu domicilio para entregar el paquete {envio.codigo} pero no había nadie. '
            'En los próximos días lo visitaremos de nuevo.'
        )
    enviar(asunto, cuerpo, envio.destinatario.email)


def notificar_reclamo_actualizado(reclamo):
    lineas = [
        f'Tu reclamo N° {reclamo.id} sobre el envío {reclamo.envio.codigo} fue actualizado.',
        '',
        f'Estado actual: {reclamo.get_estado_display()}',
    ]
    if reclamo.respuesta:
        lineas += ['', 'Respuesta de la sucursal:', reclamo.respuesta]
    enviar(f'Actualización de tu reclamo N° {reclamo.id}', '\n'.join(lineas), reclamo.cliente.email)


def notificar_solicitud_cancelacion_recibida(solicitud):
    envio = solicitud.envio
    enviar(
        f'Recibimos tu pedido de cancelación — {envio.codigo}',
        (
            f'Recibimos tu solicitud de cancelación N° {solicitud.id} para el envío {envio.codigo}.\n\n'
            'Un administrador lo va a revisar y te vamos a avisar por este mismo medio cuando quede resuelto.'
        ),
        envio.destinatario.email,
    )


def notificar_demora(envio):
    enviar(
        'Tu envío está demorado',
        f'Tu paquete {envio.codigo} lleva más de {envio.UMBRAL_DEMORA_DIAS} días sin actualizar su estado. Estamos revisando la demora.',
        envio.destinatario.email,
    )


def notificar_pago_rechazado(pago):
    envio = pago.envio
    enviar(
        f'No pudimos confirmar tu pago — {envio.codigo}',
        (
            f'Revisamos el comprobante de tu transferencia por ${pago.monto} para el envío {envio.codigo} '
            'y no pudimos confirmar que el dinero haya llegado a la cuenta de Santa Marta, por eso fue rechazado.\n\n'
            f'El envío sigue con el pago pendiente. Podés volver a pagarlo desde “Mis envíos”, '
            'subiendo un comprobante correcto o abonando con tarjeta.'
        ),
        envio.destinatario.email,
    )


def notificar_consulta_respondida(consulta):
    lineas = [
        f'Respondimos tu consulta N° {consulta.id} ({consulta.get_motivo_display()}).',
        '',
        'Tu mensaje:',
        consulta.mensaje,
        '',
        'Nuestra respuesta:',
        consulta.respuesta,
    ]
    enviar(f'Respuesta a tu consulta N° {consulta.id}', '\n'.join(lineas), consulta.cliente.email)


def notificar_solicitud_cancelacion_rechazada(solicitud):
    envio = solicitud.envio
    lineas = [f'Tu solicitud de cancelación N° {solicitud.id} para el envío {envio.codigo} fue rechazada.']
    if solicitud.respuesta_admin:
        lineas += ['', 'Motivo:', solicitud.respuesta_admin]
    lineas += ['', 'El envío sigue su curso normal. Si lo necesitás, podés volver a pedir la cancelación mientras siga pendiente.']
    enviar(f'No se pudo cancelar tu envío {envio.codigo}', '\n'.join(lineas), envio.destinatario.email)
