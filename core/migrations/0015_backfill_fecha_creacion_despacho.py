from django.db import migrations
from django.db.models import F


def backfill_fecha_creacion(apps, schema_editor):
    """Los camiones que ya existían nacieron directamente 'despachados' (el
    diseño anterior no distinguía entre cargar y salir), así que su fecha de
    creación es la misma que su fecha de salida."""
    Despacho = apps.get_model('core', 'Despacho')
    Despacho.objects.filter(fecha_creacion__isnull=True).update(fecha_creacion=F('fecha_salida'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_despacho_fecha_creacion_envio_peso_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_fecha_creacion, migrations.RunPython.noop),
    ]
