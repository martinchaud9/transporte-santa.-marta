from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Despacho, Envio

# Días que llevan en sucursal los envíos de "retiro en sucursal" de la demo.
# Se fijan respecto de hoy para que el contador de los 20 días tenga sentido
# y el sistema no los devuelva solo al abrir el panel si pasó mucho tiempo
# desde que se armó la base.
ENVIOS_RETIRO = {'ENV-4F2145': 16, 'ENV-F4A420': 8, 'ENV-ED8DE9': 8, 'ENV-5A82A1': 8}


class Command(BaseCommand):
    help = 'Re-fecha los datos de la demo respecto de hoy (plazo de retiro de 20 días y camión despachado)'

    def handle(self, *args, **options):
        ahora = timezone.now()
        n = 0
        for codigo, dias in ENVIOS_RETIRO.items():
            fecha = ahora - timedelta(days=dias)
            n += Envio.objects.filter(codigo=codigo, estado='en_sucursal').update(
                fecha_recepcion=fecha, fecha_actualizacion=fecha
            )
        despacho = Despacho.objects.filter(id=4, recepcion_finalizada=False).first()
        if despacho and despacho.fecha_salida:
            salida = ahora - timedelta(hours=6)
            Despacho.objects.filter(id=4).update(fecha_salida=salida)
            Envio.objects.filter(despacho=despacho, estado='en_transito').update(fecha_actualizacion=salida)
        self.stdout.write(self.style.SUCCESS(f'{n} envíos de retiro en sucursal re-fechados respecto de hoy.'))
