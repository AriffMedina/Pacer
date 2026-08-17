# ADR-005 · Los hechos van en tablas; la conversación es efímera

## Contexto

La ley que este proyecto aprendió a golpes:

> **Lo que no le das explícito al modelo, lo inventa. Lo que quiere hacer y no
> puede, lo falsea.**

Un coach que "recuerda" tu plan porque lo leyó veinte turnos atrás no lo
recuerda: lo reconstruye, y reconstruir es inventar. Pasó de verdad — el coach
afirmó estar en 2024 porque nadie le había dicho la fecha.

## Decisión

Dos canales separados, y no se mezclan:

- **Hechos** (perfil, plan, sesiones, carreras, fecha de hoy) → columnas en la
  base, que entran en cada turno por el **bloque de estado**
  (`pacer/application/contexto/bloque_estado.py`), deletreados sin ambigüedad:
  `FECHA DE HOY: lunes 17 de agosto de 2026 (2026-08-17)`.
- **Conversación** → los últimos 24 mensajes, solo para continuidad de trato.
  Nunca como fuente de verdad.

Y una regla explícita en el prompt: **el estado manda sobre lo que el coach
recuerde haber dicho**.

## Consecuencias

Los turnos son más caros en tokens y radicalmente más fiables.

Corolario que costó varias iteraciones: **datos al bloque de estado, acciones a
herramientas**. Cuando el coach quiso pausar el entrenamiento y la herramienta no
existía, no dijo "no puedo": prometió el cambio y no lo hizo. Se arregló creando
`pausar_por_lesion` y una regla de no prometer.
