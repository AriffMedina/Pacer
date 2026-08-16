"""Esqueleto que camina: el navegador manda audio y recibe audio de vuelta.

No hay lógica de dominio aquí a propósito. Esta fase solo prueba que la
captura de micrófono funciona en un teléfono real.
"""

from pathlib import Path

from fastapi import FastAPI, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

AUDIO_FIJO = Path(__file__).parent / "audio" / "fijo.wav"
DIRECTORIO_WEB = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(title="Pacer")


@app.post("/api/turno")
async def turno(audio: UploadFile) -> Response:
    """Recibe un turno hablado y responde con audio fijo."""
    datos = await audio.read()
    print(f"recibidos {len(datos)} bytes, tipo {audio.content_type}")
    return Response(AUDIO_FIJO.read_bytes(), media_type="audio/wav")


# Se monta al final para que /api/turno tenga precedencia sobre la raíz.
app.mount("/", StaticFiles(directory=DIRECTORIO_WEB, html=True), name="web")
