# ADR-003 · Cambiar de modelo es cambiar una constante

## Contexto

Los proveedores de modelos cambian de precio, de latencia y de calidad cada
pocos meses. Si el `model_id` aparece en cinco archivos, migrar es una cacería.

## Decisión

`pacer/composition_root.py` es el **único** sitio donde se elige qué
implementación entra por cada puerto. Cambiar de familia de modelos es cambiar
`MODEL_ID` y nada más.

La elección se documenta con lo medido, no con lo que se prefiere:

> Medido el 2026-08-15 con el mismo prompt y el mismo catálogo de herramientas:
> Nova Lite no llamó `actualizar_perfil` y filtró un bloque `<thinking>` en el
> texto, que el TTS habría leído en voz alta. Claude Haiku llamó la herramienta y
> parseó "1 de noviembre de 2026" a fecha ISO sin ayuda.

## Consecuencias

Las pruebas inyectan un LLM falso por el mismo puerto sin tocar producción.

Una trampa que costó tiempo y queda anotada: Anthropic en Bedrock exige
*inference profile*, así que el prefijo `us.` del id **no es opcional**.
