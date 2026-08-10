# Transporte Santa Marta

Sistema de gestión para la sucursal Santiago del Estero de Transporte Santa Marta:
recepción, zonificación, reparto, pagos y atención al cliente de los paquetes que
llegan desde la Casa Central de Buenos Aires.

Proyecto académico desarrollado en Django 5.2 con SQLite.

## Cómo ejecutarlo

### Requisito: Python 3.10 o superior

Verificar la versión instalada:

```bash
python3 --version
```

> **Importante en macOS:** el sistema trae de fábrica Python 3.9, que **no sirve**
> (Django 5.2 necesita 3.10 o superior). Si `python3 --version` devuelve 3.9,
> hay que instalar una versión más nueva desde <https://www.python.org/downloads/>
> y usar ese comando (por ejemplo `python3.12`) en el paso 2.
>
> El síntoma de usar una versión vieja es este error al instalar:
> `No matching distribution found for Django==5.2.11`.

**1. Descargar el proyecto**

```bash
git clone https://github.com/martinchaud9/transporte-santa.-marta.git
cd transporte-santa.-marta
```

**2. Crear el entorno virtual e instalar las dependencias**

En macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

En Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**3. Aplicar las migraciones**

```bash
python manage.py migrate
```

**4. Levantar el servidor**

```bash
python manage.py runserver
```

Abrir <http://127.0.0.1:8000> en el navegador. Para frenar el servidor: `Ctrl + C`.

> Cada vez que se abre una terminal nueva hay que volver a activar el entorno
> (`source venv/bin/activate`) antes de levantar el servidor.

## Cuentas de prueba

La base de datos (`db.sqlite3`) viene con datos cargados para probar el sistema.

| Usuario | Contraseña | Rol |
|---|---|---|
| `superadmin` | `123456` | Administrador |
| `lautaromoreno` | `test12345` | Empleado |
| `cliente_45435243541` | `test12345` | Cliente (Maria Agostina) |

El panel de Casa Central (simulación de Buenos Aires) se accede sin login en
<http://127.0.0.1:8000/casacentral/>.

Si hace falta crear un administrador nuevo:

```bash
python manage.py createsuperuser
```

## Notificaciones por email

Por defecto los correos **no se envían de verdad**: se imprimen en la terminal
donde corre el servidor (backend de consola de Django). Alcanza para ver el
contenido de cada notificación.

Para enviarlos de verdad con una cuenta de Gmail, definir estas dos variables de
entorno antes de levantar el servidor (hace falta una *contraseña de aplicación*
de Google, no la contraseña normal de la cuenta):

```bash
export EMAIL_HOST_USER="tucuenta@gmail.com"
export EMAIL_HOST_PASSWORD="tu_contrasena_de_aplicacion"
python manage.py runserver
```

Las credenciales nunca se escriben en el código: si las variables no están
definidas, el sistema vuelve solo al modo consola.

## Tareas automáticas

Detectar envíos demorados (más de 2 días sin cambiar de estado) y notificar a los
clientes. Pensado para programarse una vez por día:

```bash
python manage.py detectar_demoras
```

## Estructura del proyecto

| Carpeta | Contenido |
|---|---|
| `core/` | Modelos, formularios, notificaciones por email y zonificación |
| `casacentral/` | Panel de Buenos Aires: alta de envíos, despacho de camiones, etiquetas QR |
| `empleado/` | Panel de la sucursal: recepción, reparto, entregas e incidencias |
| `administrador/` | Panel de gestión: empleados, vehículos, pagos, reportes, reclamos |
| `cliente/` | Portal del cliente: seguimiento, pagos y reclamos |
| `config/` | Configuración de Django |

El documento `Resumen_Mejoras_Santa_Marta.docx` detalla todas las mejoras
implementadas y cómo demostrarlas.
