from django.db import migrations
from django.db.models import F


def ajustar_datos(apps, schema_editor):
    Envio = apps.get_model('core', 'Envio')
    # Los envíos retenidos (2 visitas a domicilio fallidas) pasan a retiro en
    # sucursal: es lo que el cliente tiene que hacer ahora.
    Envio.objects.filter(estado='retenido').update(modalidad='sucursal')
    # Los reportes cuentan las entregas por fecha_entrega: se completa en los
    # entregados anteriores que no la tenían.
    Envio.objects.filter(estado='entregado', fecha_entrega__isnull=True).update(fecha_entrega=F('fecha_actualizacion'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_auditoria_nuevas_acciones'),
    ]

    operations = [
        migrations.RunPython(ajustar_datos, migrations.RunPython.noop),
    ]
