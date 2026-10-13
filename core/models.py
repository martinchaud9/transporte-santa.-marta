from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class Usuario(AbstractUser):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('empleado', 'Empleado'),
        ('cliente', 'Cliente'),
    ]
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    dni = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.rol})"
    
class Despacho(models.Model):
    """Un camión que Casa Central va cargando con paquetes hasta que se
    despacha hacia la sucursal.

    Mientras `fecha_salida` es null, el camión está "abierto": todavía se le
    pueden agregar paquetes nuevos. Apenas se llega al límite de peso, el
    próximo paquete abre automáticamente un camión siguiente, aunque este
    todavía no haya salido. El límite es solo por peso: los paquetes tienen
    volúmenes muy distintos y no tiene sentido toparlos por cantidad.
    """
    # Camión de larga distancia Buenos Aires → Santiago. Sale de ~120 paquetes
    # por viaje (240 envíos/semana en 2 camiones) de 10-15 kg promedio.
    CAPACIDAD_MAX_PESO_KG = 2000

    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    recepcion_finalizada = models.BooleanField(default=False)
    fecha_recepcion_finalizada = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Camión #{self.id}"

    @property
    def despachado(self):
        return self.fecha_salida is not None

    @property
    def total_envios(self):
        # Un envío cancelado nunca viaja: no debe contar ni para el cupo de
        # paquetes ni (más importante) para el peso del camión.
        return self.envios.exclude(estado='cancelado').count()

    @property
    def peso_total(self):
        return self.envios.exclude(estado='cancelado').aggregate(total=models.Sum('peso'))['total'] or 0

    @property
    def envios_a_despachar(self):
        """Los que realmente van a viajar si se despacha este camión ahora."""
        return self.envios.filter(estado='pendiente')

    @property
    def envios_cancelados_a_retirar(self):
        """Envíos cuya cancelación se aprobó mientras el camión seguía
        cargando: hay que sacarlos físicamente antes de despachar."""
        return self.envios.filter(estado='cancelado')

    def puede_recibir(self, peso_adicional):
        """¿Entra un paquete más de `peso_adicional` kg en este camión?"""
        if self.despachado:
            return False
        if self.peso_total + peso_adicional > self.CAPACIDAD_MAX_PESO_KG:
            return False
        return True

    @classmethod
    def obtener_o_crear_abierto(cls, peso_nuevo_envio):
        """Devuelve el camión que está cargando actualmente (el más nuevo sin
        despachar). Si no hay ninguno, o el que hay ya no soporta el peso de
        este paquete, abre uno nuevo."""
        abierto = cls.objects.filter(fecha_salida__isnull=True).order_by('-fecha_creacion').first()
        if abierto and abierto.puede_recibir(peso_nuevo_envio):
            return abierto
        return cls.objects.create(fecha_creacion=timezone.now())

    @property
    def envios_recibidos(self):
        return self.envios.exclude(estado__in=['pendiente', 'en_transito', 'extraviado']).count()

    @property
    def envios_pendientes_recepcion(self):
        return self.envios.filter(estado='en_transito')


class Envio(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_transito', 'En tránsito'),
        ('en_sucursal', 'En sucursal'),
        ('en_reparto', 'En reparto'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
        ('devuelto', 'Devuelto'),
        ('retenido', 'Retenido'),
        ('extraviado', 'Extraviado'),
    ]
    MODALIDAD_CHOICES = [
        ('domicilio', 'Entrega a domicilio'),
        ('sucursal', 'Retiro en sucursal'),
    ]
    ZONA_CHOICES = [
        ('norte', 'Norte'),
        ('sur', 'Sur'),
        ('este', 'Este'),
        ('oeste', 'Oeste'),
    ]

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    destinatario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='envios')
    despacho = models.ForeignKey(Despacho, on_delete=models.SET_NULL, null=True, blank=True, related_name='envios')
    contenido = models.CharField(max_length=200)
    peso = models.DecimalField(max_digits=6, decimal_places=2, default=1, help_text='Peso en kilogramos')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES)
    direccion_entrega = models.CharField(max_length=200, blank=True)
    zona = models.CharField(max_length=10, choices=ZONA_CHOICES, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_recepcion = models.DateTimeField(null=True, blank=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    entregado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='entregas_realizadas'
    )
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    notificado_demora = models.BooleanField(default=False)
    intentos_entrega = models.PositiveSmallIntegerField(default=0)

    ESTADOS_ACTIVOS = ['pendiente', 'en_transito', 'en_sucursal', 'en_reparto']
    UMBRAL_DEMORA_DIAS = 2
    MAX_INTENTOS_ENTREGA = 2
    UMBRAL_RETENCION_DIAS = 20

    def __str__(self):
        return self.codigo

    @property
    def dias_sin_actualizar(self):
        return (timezone.now() - self.fecha_actualizacion).days

    @property
    def esta_demorado(self):
        return self.estado in self.ESTADOS_ACTIVOS and self.dias_sin_actualizar > self.UMBRAL_DEMORA_DIAS

    @property
    def dias_retenido(self):
        return self.dias_sin_actualizar if self.estado == 'retenido' else None

    @property
    def debe_devolverse_por_vencimiento(self):
        return self.estado == 'retenido' and self.dias_sin_actualizar >= self.UMBRAL_RETENCION_DIAS

    @classmethod
    def devolver_retenidos_vencidos(cls):
        """Barre los envíos 'retenido' hace UMBRAL_RETENCION_DIAS días o más
        (sin que el cliente los haya retirado) y los devuelve automáticamente
        a Buenos Aires. Se llama en cada carga del panel admin, no depende de
        un cron. Devuelve la lista de envíos recién devueltos para que quien
        llame les avise por email."""
        limite = timezone.now() - timedelta(days=cls.UMBRAL_RETENCION_DIAS)
        vencidos = list(cls.objects.filter(estado='retenido', fecha_actualizacion__lt=limite))
        if vencidos:
            cls.objects.filter(id__in=[e.id for e in vencidos]).update(
                estado='devuelto', fecha_actualizacion=timezone.now()
            )
            for envio in vencidos:
                envio.estado = 'devuelto'
        return vencidos

    @property
    def tiene_danio_reportado(self):
        return self.incidencias.filter(tipo='danado').exists()

    @property
    def tiene_perdida_reportada(self):
        return self.incidencias.filter(tipo='perdido').exists()

    @property
    def monto_pagado(self):
        # Una transferencia todavía no verificada por el administrador no
        # cuenta como plata recibida, aunque el cliente ya haya subido el
        # comprobante.
        return self.pagos.filter(anulado=False, verificado=True).aggregate(total=models.Sum('monto'))['total'] or 0

    @property
    def esta_pagado(self):
        return self.monto_pagado >= self.precio

    @property
    def saldo_pendiente(self):
        return max(self.precio - self.monto_pagado, 0)

    @property
    def tiene_pago_pendiente_verificacion(self):
        return self.pagos.filter(anulado=False, verificado=False).exists()

    @property
    def tiene_solicitud_cancelacion_pendiente(self):
        return self.solicitudes_cancelacion.filter(estado='pendiente').exists()

    @property
    def puede_entregarse(self):
        # Regla de negocio: no se entrega sin pago completo, salvo que exista
        # un pago parcial autorizado (cliente con relación comercial previa).
        return self.esta_pagado or self.pagos.filter(anulado=False, verificado=True, es_parcial=True).exists()


class RepartoActivo(models.Model):
    """El reparto de una zona en curso: qué empleado la está llevando ahora
    mismo y su última posición GPS conocida (la manda su propio celular
    mientras tiene el panel de reparto abierto). Se crea cuando un empleado
    saca una zona a reparto (`despachar_zona_view`) y se borra solo cuando ya
    no queda ningún envío 'en_reparto' de esa zona — así el rastreo del
    cliente sabe cuándo dejar de mostrar el mapa. Una sola persona reparte
    cada zona por vez, por eso `zona` es única."""
    zona = models.CharField(max_length=10, choices=Envio.ZONA_CHOICES, unique=True)
    empleado = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='repartos_activos')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    ultima_lat = models.FloatField(null=True, blank=True)
    ultima_lon = models.FloatField(null=True, blank=True)
    fecha_ultima_ubicacion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Reparto {self.get_zona_display()} — {self.empleado}"


class Pago(models.Model):
    MEDIO_CHOICES = [
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia bancaria'),
    ]

    envio = models.ForeignKey(Envio, on_delete=models.PROTECT, related_name='pagos')
    registrado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MEDIO_CHOICES)
    fecha = models.DateTimeField(auto_now_add=True)
    es_parcial = models.BooleanField(default=False)
    justificacion = models.TextField(blank=True)
    anulado = models.BooleanField(default=False)

    # Una transferencia queda "sin verificar" hasta que el administrador
    # confirma haber recibido la plata en la cuenta de la empresa; hasta ese
    # momento no cuenta como pago real (no destraba la entrega). El pago con
    # tarjeta, en cambio, lo aprueba la pasarela al instante.
    comprobante_foto = models.ImageField(upload_to='comprobantes/%Y/%m/', null=True, blank=True)
    verificado = models.BooleanField(default=True)
    verificado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos_verificados'
    )
    fecha_verificacion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Pago {self.envio.codigo} — ${self.monto}"


class Incidencia(models.Model):
    TIPO_CHOICES = [
        ('danado', 'Paquete dañado'),
        ('perdido', 'Paquete perdido'),
        ('direccion', 'Dirección incorrecta'),
    ]

    envio = models.ForeignKey(Envio, on_delete=models.PROTECT, related_name='incidencias')
    registrado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Incidencia {self.tipo} — {self.envio.codigo}"


class Reclamo(models.Model):
    TIPO_CHOICES = [
        ('danado', 'Paquete dañado'),
        ('perdida', 'Pérdida'),
        ('demora', 'Demora'),
        ('otro', 'Otro'),
    ]
    ESTADO_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('en_proceso', 'En proceso'),
        ('resuelto', 'Resuelto'),
    ]

    UMBRAL_DEMORA_DIAS = 3

    envio = models.ForeignKey(Envio, on_delete=models.PROTECT, related_name='reclamos')
    cliente = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='reclamos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='nuevo')
    respuesta = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reclamo #{self.id} — {self.envio.codigo}"

    @property
    def dias_sin_actualizar(self):
        return (timezone.now() - self.fecha_actualizacion).days

    @property
    def esta_demorado(self):
        # Igual que con los envíos: si lleva mucho tiempo sin una respuesta
        # nueva del admin, se marca para que no se pierda de vista.
        return self.estado != 'resuelto' and self.dias_sin_actualizar > self.UMBRAL_DEMORA_DIAS


class SolicitudCancelacion(models.Model):
    """El cliente pide cancelar un envío propio; el administrador la aprueba
    o la rechaza. El envío recién pasa a 'cancelado' si se aprueba."""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de autorización'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    envio = models.ForeignKey(Envio, on_delete=models.PROTECT, related_name='solicitudes_cancelacion')
    cliente = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='solicitudes_cancelacion')
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    respuesta_admin = models.TextField(blank=True)
    resuelto_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_cancelacion_resueltas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Solicitud de cancelación #{self.id} — {self.envio.codigo}"


class LogAuditoria(models.Model):
    """Registro de acciones administrativas sensibles e irreversibles (bajas
    de cuentas, anulación de pagos, extravíos), para poder responder "quién
    hizo esto y cuándo" aunque el registro afectado cambie o se desactive."""
    ACCION_CHOICES = [
        ('baja_empleado', 'Baja de empleado'),
        ('anulacion_pago', 'Anulación de pago'),
        ('rechazo_pago', 'Rechazo de comprobante'),
        ('extravio_envio', 'Envío marcado como extraviado'),
    ]

    accion = models.CharField(max_length=30, choices=ACCION_CHOICES)
    realizado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name='logs_como_autor'
    )
    # Según la acción, se completa uno solo de estos tres (el resto queda null).
    usuario_afectado = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_como_afectado'
    )
    pago_afectado = models.ForeignKey(
        'Pago', on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_auditoria'
    )
    envio_afectado = models.ForeignKey(
        'Envio', on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_auditoria'
    )
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    @property
    def objetivo(self):
        return self.usuario_afectado or self.pago_afectado or self.envio_afectado

    def __str__(self):
        return f"{self.get_accion_display()} — {self.objetivo} ({self.fecha:%d/%m/%Y %H:%M})"


class Vehiculo(models.Model):
    # El reparto a domicilio se hace solo en furgón.
    TIPO_CHOICES = [
        ('furgon', 'Furgón'),
    ]

    # Carga máxima del furgón en cada salida de reparto de una zona (un Kangoo
    # o Fiorino soporta ~600-800 kg; se deja margen). Cuando se llena, el resto
    # de los paquetes de esa zona espera a la próxima salida.
    CAPACIDAD_MAX_PESO_KG = 600

    patente = models.CharField(max_length=10, unique=True)
    marca = models.CharField(max_length=50, blank=True)
    modelo = models.CharField(max_length=50, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    empleado = models.OneToOneField(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehiculo')

    def __str__(self):
        return self.patente