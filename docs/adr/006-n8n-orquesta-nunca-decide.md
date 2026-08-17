# ADR-006 · n8n entrega; la app decide

## Contexto

Es cómodo meter la lógica en el workflow: un nodo Code y listo. También es la
forma más rápida de tener reglas de negocio que nadie puede probar, versionar ni
revisar.

## Decisión

La app decide **qué** recordar y **cuándo**
(`pacer/domain/servicios/recordatorios.py`, función pura). n8n solo transporta:

```
cada 15 min → materializar → vencidos → ¿hay chat? → Telegram → confirmar
```

Tres propiedades sostienen esto:

- **El destino viaja con el dato.** `vencidos` devuelve cada recordatorio con
  *su* `chat_id`. El mismo workflow sirve para un corredor o para mil.
- **La idempotencia vive en la base.** `clave` es UNIQUE: materializar dos veces
  no duplica y confirmar dos veces no reenvía. Los reintentos son seguros por
  construcción del esquema, no por el cuidado de quien llama.
- **Se confirma después de entregar.** Si Telegram falla, el flujo se detiene y
  reintenta. Un recordatorio que no salió jamás queda marcado como enviado.

## Consecuencias

Si n8n se cae no se pierde nada: los recordatorios quedan pendientes en la base y
salen en la siguiente vuelta.

Los secretos van en las credenciales de n8n, nunca en el JSON. Por eso
`n8n/workflows/recordatorios.json` puede vivir en el repositorio.
