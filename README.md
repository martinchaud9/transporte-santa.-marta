# Transporte Santa Marta

Sistema de gestión para la sucursal Santiago del Estero de Transporte Santa Marta:
recepción, zonificación, reparto, pagos y atención al cliente de los paquetes que
llegan desde la Casa Central de Buenos Aires.

Proyecto académico desarrollado en Django 5.2 con SQLite.

## Requisito previo: Python 3.10 o superior

Django 5.2 **no funciona** con versiones anteriores. Para verificar qué versión hay instalada:

```bash
python --version
```

Si el comando no existe o devuelve algo menor a 3.10, instalar Python desde
<https://www.python.org/downloads/>. **En Windows, durante la instalación hay que
tildar la casilla "Add python.exe to PATH"** (está abajo de todo en la primera
pantalla) — si no, ningún comando de esta guía va a funcionar.

> Síntoma de estar usando una versión vieja: al instalar las dependencias aparece
> `No matching distribution found for Django==5.2.11`.
>
> En macOS el sistema trae Python 3.9 de fábrica, que tampoco sirve.

---

## Cómo ejecutarlo en Windows

Abrir **PowerShell** (botón de Windows → escribir "PowerShell" → Enter) y ejecutar
los comandos uno por uno.

**1. Descargar el proyecto**

```powershell
git clone https://github.com/martinchaud9/transporte-santa.-marta.git
cd transporte-santa.-marta
```

Si no tenés Git instalado, se puede descargar el proyecto como ZIP desde el botón
verde **Code → Download ZIP** de GitHub, descomprimirlo y entrar a la carpeta.

**2. Crear el entorno virtual**

```powershell
python -m venv venv
```

**3. Activar el entorno virtual**

```powershell
venv\Scripts\Activate.ps1
```

> **Si aparece el error "no se puede cargar el archivo ... la ejecución de scripts
> está deshabilitada en este sistema"**, es una restricción de PowerShell.
> Ejecutar esto una vez y volver a intentar el paso 3:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```
>
> (Solo afecta a esa ventana de PowerShell, no cambia la configuración de Windows.)

Cuando el entorno está activado, aparece `(venv)` al principio de la línea.

**4. Instalar las dependencias**

```powershell
pip install -r requirements.txt
```

**5. Aplicar las migraciones**

```powershell
python manage.py migrate
```

**6. Levantar el servidor**

```powershell
python manage.py runserver
```

Abrir <http://127.0.0.1:8000> en el navegador. Para frenar el servidor: `Ctrl + C`.

> Los pasos 1, 2, 4 y 5 se hacen **una sola vez**. Para volver a usar el sistema
> después, alcanza con abrir PowerShell en la carpeta del proyecto y repetir los
> pasos 3 y 6 (activar el entorno y levantar el servidor).

---

## Cómo ejecutarlo en macOS / Linux

```bash
git clone https://github.com/martinchaud9/transporte-santa.-marta.git
cd transporte-santa.-marta
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Después de la primera vez, alcanza con `source venv/bin/activate` y
`python manage.py runserver`.

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
de Google, no la contraseña normal de la cuenta).

En Windows (PowerShell):

```powershell
$env:EMAIL_HOST_USER="tucuenta@gmail.com"
$env:EMAIL_HOST_PASSWORD="tu_contrasena_de_aplicacion"
python manage.py runserver
```

En macOS / Linux:

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
