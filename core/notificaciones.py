from django.conf import settings
from django.core.mail import send_mail

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
}


def notificar_cambio_estado(envio):
    datos = MENSAJES_ESTADO.get(envio.estado)
    if not datos or not envio.destinatario.email:
        return
    asunto, cuerpo = datos
    send_mail(asunto, cuerpo.format(codigo=envio.codigo), settings.DEFAULT_FROM_EMAIL, [envio.destinatario.email], fail_silently=True)


def notificar_demora(envio):
    if not envio.destinatario.email:
        return
    send_mail(
        'Tu envío está demorado',
        f'Tu paquete {envio.codigo} lleva más de {envio.UMBRAL_DEMORA_DIAS} días sin actualizar su estado. Estamos revisando la demora.',
        settings.DEFAULT_FROM_EMAIL,
        [envio.destinatario.email],
        fail_silently=True,
    )
