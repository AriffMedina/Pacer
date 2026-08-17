# ADR-002 · El plan lo calcula código, no el modelo

## Contexto

La tentación evidente es pedirle el plan al modelo: sabe de running y escribe
bien. Pero un plan de entrenamiento es carga física sobre una persona real. Un
modelo que alucina un 20% de más no comete un error de formato: manda a alguien
a correr más de lo que aguanta.

Y lo peor no es equivocarse, es equivocarse **distinto cada vez**. El mismo
corredor preguntando lo mismo dos veces recibiría dos planes.

## Decisión

El plan lo genera `pacer/domain/servicios/generador_plan.py`: una función pura,
determinista y probada con Hypothesis. El modelo **nunca** decide la carga.

El modelo hace tres cosas, y solo tres:

1. **Traduce** lo que dices a hechos (`actualizar_perfil`).
2. **Pide** que se genere o ajuste un plan (`generar_plan`, `pausar_por_lesion`).
3. **Explica** en voz alta lo que el código decidió.

Los límites viven en el código, no en el prompt. Un guardarraíl escrito en el
prompt es una sugerencia; escrito en una función es una garantía.

## Consecuencias

Mismos datos, mismo plan, siempre. Se puede probar por propiedades: la carga
nunca sube más de lo permitido entre semanas, el tapering siempre baja.

El modelo se vuelve reemplazable: cambia cómo suena el coach, no lo que manda.
