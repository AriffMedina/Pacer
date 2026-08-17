# ADR-001 · El dominio no importa nada

## Contexto

Un coach de voz junta cuatro proveedores externos: Bedrock para conversar, Groq
para transcribir, Polly para hablar y Telegram para avisar. Si la lógica de
entrenamiento toca cualquiera de ellos, probarla exige red — y probar contra la
red significa no probar casi nada.

## Decisión

Arquitectura hexagonal, con una regla que se verifica sola: **`pacer.domain` no
importa `application`, `infrastructure` ni `interfaces`**. No es una buena
intención escrita en un documento; es un contrato que corre en CI.

```ini
[importlinter:contract:regla-de-dependencia]
type = forbidden
source_modules = pacer.domain
forbidden_modules = pacer.infrastructure, pacer.interfaces, pacer.application
```

Los proveedores entran por puertos (`pacer/domain/puertos/`) y se eligen en un
único sitio (`pacer/composition_root.py`).

## Consecuencias

El dominio se prueba sin red, sin base de datos y sin dobles: es aritmética y
calendario. De ahí que la mayoría de los 434 tests corran en milisegundos.

El precio es la ceremonia: agregar un proveedor obliga a definir el puerto antes
que el adaptador. Se paga una vez por proveedor.
