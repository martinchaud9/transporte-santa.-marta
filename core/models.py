from django.contrib.auth.models import AbstractUser
from django.db import models

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

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    destinatario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='envios')
    contenido = models.CharField(max_length=200)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES)
    direccion_entrega = models.CharField(max_length=200, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.codigo


class Pago(models.Model):
    MEDIO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia bancaria'),
    ]

    envio = models.ForeignKey(Envio, on_delete=models.PROTECT, related_name='pagos')
    registrado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MEDIO_CHOICES)
    fecha = models.DateTimeField(auto_now_add=True)
    es_parcial = models.BooleanField(default=False)
    justificacion = models.TextField(blank=True)

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