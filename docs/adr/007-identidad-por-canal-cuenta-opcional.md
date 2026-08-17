# ADR-007 · Identidad por canal, cuenta opcional

## Contexto

El piloto resolvía toda visita web al primer corredor de la tabla. Compartir el
enlace era regalar tu plan, tu nombre y tu conversación. Con el despliegue
público eso pasó de defecto a fallo grave.

Pero un muro de registro delante de un coach de voz mata la demo: quien abre el
enlace tiene que poder hablar en el segundo uno.

## Decisión

Tres identidades, en capas:

1. **Cookie anónima** (`clave_sesion`, UNIQUE). Cada navegador es su propio
   corredor desde la primera visita. Sin registro.
2. **Cuenta opcional** (correo + `scrypt`). Registrarse **adopta** el corredor
   que ya venías usando: nadie pierde su plan por crear la cuenta.
3. **Telegram** (`telegram_chat_id`, UNIQUE), unido al corredor web mediante un
   código de seis dígitos de un solo uso que caduca en diez minutos
   (`pacer/domain/servicios/vinculacion.py`).

## Consecuencias

Dos reclutadores abriendo el mismo enlace son dos personas distintas.

Dos trampas que costaron caro y quedan escritas:

- **Crear al corredor no basta con mirar antes de insertar.** Al abrir la app
  salen varias peticiones con la misma cookie; todas miran, ninguna encuentra y
  todas insertan. La primera carga devolvía 500 hasta que quien pierde la carrera
  aprendió a volver a buscar.
- **`ALTER TABLE ADD COLUMN` no crea los índices.** `clave_sesion` llegó a
  producción sin su UNIQUE, y dos peticiones simultáneas creaban dos corredores
  con la misma cookie. La migración aditiva ahora también crea los índices que
  falten.
