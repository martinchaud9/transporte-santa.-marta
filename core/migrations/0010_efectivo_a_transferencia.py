from django.db import migrations


def convertir_efectivo(apps, schema_editor):
    Pago = apps.get_model('core', 'Pago')
    Pago.objects.filter(medio_pago='efectivo').update(medio_pago='transferencia')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_alter_pago_medio_pago'),
    ]

    operations = [
        migrations.RunPython(convertir_efectivo, migrations.RunPython.noop),
    ]
