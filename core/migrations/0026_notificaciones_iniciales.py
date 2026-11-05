from django.db import migrations

# Un aviso por cada envío ya existente según su estado actual, para que el
# panel del cliente no arranque vacío en la base de la demo.
TITULOS = {
    'en_transito': ('Tu envío salió de Buenos Aires', 'Tu paquete {codigo} salió de Casa Central y está en camino a Santiago del Estero.'),
    'en_sucursal': ('Tu envío llegó a la sucursal', 'Tu paquete {codigo} llegó a la sucursal de Santiago del Estero.'),
    'en_reparto': ('Tu envío está en reparto', 'Tu paquete {codigo} salió a reparto.'),
    'entregado': ('Tu envío fue entregado', 'Tu paquete {codigo} fue entregado con éxito. ¡Gracias por elegir Santa Marta!'),
    'cancelado': ('Tu envío fue cancelado', 'Tu paquete {codigo} fue cancelado. Si no lo solicitaste o tenés dudas, comunicate con la sucursal.'),
    'devuelto': ('Tu envío fue devuelto a Buenos Aires', 'Tu paquete {codigo} fue devuelto a Casa Central en Buenos Aires porque no pudo ser retirado a tiempo. Comunicate con la sucursal para coordinar un nuevo envío.'),
}
ACTIVOS = ('en_transito', 'en_sucursal', 'en_reparto')


def crear_avisos(apps, schema_editor):
    Envio = apps.get_model('core', 'Envio')
    Notificacion = apps.get_model('core', 'Notificacion')
    for envio in Envio.objects.select_related('destinatario').filter(estado__in=TITULOS):
        titulo, cuerpo = TITULOS[envio.estado]
        n = Notificacion.objects.create(
            usuario=envio.destinatario, envio=envio, titulo=titulo,
            mensaje=cuerpo.format(codigo=envio.codigo),
            # Los de envíos en curso quedan sin leer; el resto, ya leídos.
            leida=envio.estado not in ACTIVOS,
        )
        Notificacion.objects.filter(pk=n.pk).update(fecha=envio.fecha_actualizacion)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_notificacion'),
    ]

    operations = [
        migrations.RunPython(crear_avisos, migrations.RunPython.noop),
    ]
