from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Usuario, Envio
from core.forms import RegistroEmpleadoForm

@login_required
def dashboard_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    empleados = Usuario.objects.filter(rol='empleado')
    clientes = Usuario.objects.filter(rol='cliente')
    envios_activos = Envio.objects.exclude(estado='entregado').order_by('-fecha_registro')
    envios_entregados = Envio.objects.filter(estado='entregado').order_by('-fecha_registro')
    return render(request, 'administrador/dashboard.html', {
        'empleados': empleados,
        'clientes': clientes,
        'envios': envios_activos,
        'envios_entregados': envios_entregados,
    })

@login_required
def registro_empleado_view(request):
    if request.user.rol != 'admin':
        return redirect('inicio')
    if request.method == 'POST':
        form = RegistroEmpleadoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
        else:
            print(form.errors)
    return redirect('admin_dashboard')