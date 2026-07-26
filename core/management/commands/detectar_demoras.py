from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Envio
from core.notificaciones import notificar_demora


class Command(BaseCommand):
    help = 'Detecta envíos demorados (sin cambio de estado hace más de N días) y notifica al cliente'

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=Envio.UMBRAL_DEMORA_DIAS)
        demorados = list(Envio.objects.filter(
            estado__in=Envio.ESTADOS_ACTIVOS,
            fecha_actualizacion__lt=limite,
            notificado_demora=False,
        ))

        for envio in demorados:
            notificar_demora(envio)
            envio.notificado_demora = True
            envio.save(update_fields=['notificado_demora'])

        self.stdout.write(self.style.SUCCESS(f'{len(demorados)} envíos demorados notificados'))
