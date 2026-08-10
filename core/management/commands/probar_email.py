from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from core.models import Usuario


class Command(BaseCommand):
    help = 'Diagnostica la configuración de email y envía un correo de prueba'

    def add_arguments(self, parser):
        parser.add_argument('--para', help='Dirección a la que enviar la prueba')

    def handle(self, *args, **options):
        usando_smtp = 'smtp' in settings.EMAIL_BACKEND

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Configuración actual'))
        self.stdout.write(f'  Backend:   {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  Remitente: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'  Usuario:   {settings.EMAIL_HOST_USER or "(vacío)"}')
        self.stdout.write(f'  Password:  {"(cargada)" if settings.EMAIL_HOST_PASSWORD else "(vacía)"}')
        self.stdout.write('')

        if not usando_smtp:
            self.stdout.write(self.style.WARNING(
                'MODO CONSOLA: los correos NO se envían, solo se imprimen en esta terminal.'
            ))
            self.stdout.write(
                '  Para enviarlos de verdad, cerrá el servidor y arrancalo así:\n'
                '    export EMAIL_HOST_USER="tucuenta@gmail.com"\n'
                '    export EMAIL_HOST_PASSWORD="tu_contrasena_de_aplicacion"\n'
                '    python manage.py runserver\n'
                '  Importante: las variables valen solo para esa terminal. Si el servidor\n'
                '  ya estaba corriendo cuando las cargaste, hay que reiniciarlo.'
            )
            self.stdout.write('')

        destino = options.get('para') or settings.EMAIL_HOST_USER
        if not destino:
            clifiltro = Usuario.objects.filter(rol='cliente').exclude(email='').first()
            destino = clifiltro.email if clifiltro else None
        if not destino:
            self.stdout.write(self.style.ERROR('No hay a quién enviarle la prueba. Usá --para tucorreo@gmail.com'))
            return

        self.stdout.write(f'Enviando correo de prueba a {destino}...')
        try:
            send_mail(
                'Prueba de configuración — Santa Marta',
                'Si estás leyendo esto, el envío de correos del sistema funciona correctamente.',
                settings.DEFAULT_FROM_EMAIL,
                [destino],
                fail_silently=False,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'FALLÓ el envío: {type(e).__name__}: {e}'))
            self.stdout.write(
                '  Causas habituales:\n'
                '   - La contraseña de aplicación es incorrecta o tiene espacios.\n'
                '   - La cuenta no tiene activada la verificación en dos pasos.\n'
                '   - No hay conexión a internet.'
            )
            return

        if usando_smtp:
            self.stdout.write(self.style.SUCCESS(f'Correo enviado. Revisá la bandeja de {destino}.'))
        else:
            self.stdout.write(self.style.SUCCESS('Correo "enviado" al modo consola (mirá el texto de arriba).'))

        clientes_sin_email = Usuario.objects.filter(rol='cliente', email='').count()
        if clientes_sin_email:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'Atención: hay {clientes_sin_email} cliente(s) sin email cargado. '
                'A esos no les va a llegar ninguna notificación.'
            ))
