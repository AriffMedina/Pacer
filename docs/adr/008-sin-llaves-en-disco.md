# ADR-008 · Ninguna llave de AWS vive en el proyecto

## Contexto

Lo normal es pegar `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` en el `.env`.
También es la forma más común de filtrar credenciales: el `.env` se copia, se
comparte por chat, se cuela en una imagen de Docker o en una captura de pantalla.

## Decisión

Las credenciales de AWS **nunca** están en el `.env`, ni en la imagen, ni en el
repositorio. Se resuelven por la cadena de credenciales estándar, distinta en
cada entorno:

- **Desarrollo:** `~/.aws` montado de solo lectura en el contenedor.
- **Producción (EC2):** el rol de instancia (`pacer-ec2`) las entrega por IMDS, y
  el montaje de `~/.aws` desaparece del compose.

El rol concede lo justo: `bedrock:InvokeModel` y `polly:SynthesizeSpeech`.

## Consecuencias

Rotar credenciales no toca el proyecto. Un `.env` filtrado no da acceso a AWS.

Verificado en el despliegue, no asumido: dentro del contenedor no existe
`/home/pacer/.aws` ni hay variable alguna con un secreto de AWS, y las
credenciales llegan del rol por IMDS.

Las llaves que **sí** viven en el `.env` (Groq, Telegram, token interno) son de
terceros que no ofrecen roles. Para esas, el `.env` está fuera de git y el
despliegue las recibe por copia directa, nunca por commit.
