# ADR-004 · Los planes se versionan, no se editan

## Contexto

Un plan cambia: te lesionas, te sale un viaje, la carrera se mueve. Editarlo en
su sitio es lo obvio y es un error — el corredor pierde de vista qué cambió, y el
coach pierde la capacidad de explicar por qué.

## Decisión

Cada ajuste crea una **versión nueva** con su `motivo_cambio`. La versión activa
es la de número más alto. Nada se sobrescribe.

## Consecuencias

El coach puede decir "te bajé el volumen porque reportaste dolor" con el dato
delante, no de memoria.

Un fallo real que esto destapó: `generar_plan` devolvía siempre versión 1
mientras `version_activa` tomaba el máximo, así que un plan nuevo nacía por
debajo de su propia historia y no se veía. Se arregló pasando el plan previo
para que la versión suba de verdad.

El coste es espacio en disco, el recurso más barato del proyecto.
