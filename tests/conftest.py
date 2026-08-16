"""Configuración común a toda la suite."""

from hypothesis import HealthCheck, settings

# El deadline de Hypothesis mide tiempo de pared por ejemplo. `generar_plan`
# construye planes de hasta 24 semanas, y bajo carga —CI, un build de Docker en
# paralelo— eso pasa de 200 ms sin que nada esté mal. Un test que falla según
# lo ocupada que esté la máquina no informa: entrena a ignorar el rojo.
#
# Lo que sí queremos vigilar es la corrección, y esa la siguen cubriendo las
# propiedades. Si algún día importa el rendimiento, se mide aparte y con una
# cota pensada, no con el reloj de otra prueba.
settings.register_profile(
    "pacer",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("pacer")
