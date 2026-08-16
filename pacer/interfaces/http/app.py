"""El cable: audio del navegador → transcripción → coach → voz de vuelta.

Devuelve JSON en vez de audio crudo para que la interfaz pueda mostrar la
transcripción y la latencia. El cajón de diagnóstico no es adorno: sin él, un
turno lento y un turno roto se ven igual desde el teléfono.
"""

import base64
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from pacer.application.casos_uso.atender_turno import atender_turno
from pacer.application.contexto.bloque_estado import construir_bloque
from pacer.application.contexto.prompt_sistema import construir_prompt
from pacer.composition_root import (
    CORREDOR_PILOTO,
    configuracion,
    construir_llm,
    construir_stt,
    construir_tts,
)
from pacer.domain.entidades.perfil import Perfil
from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

DIRECTORIO_WEB = Path(__file__).resolve().parents[3] / "web"


@dataclass
class SesionEnMemoria:
    """Perfil e historial del piloto.

    Limitación conocida: se pierde al reiniciar. El plan sí está en la base;
    persistir el perfil es lo que falta para que Telegram funcione con la app
    cerrada durante días.
    """

    perfil: Perfil = field(default_factory=Perfil)
    mensajes: list[dict[str, Any]] = field(default_factory=list)


sesion = SesionEnMemoria()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    config = configuracion()
    motor = create_async_engine(config.database_url)

    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    app.state.fabrica = async_sessionmaker(motor, expire_on_commit=False)
    app.state.llm = construir_llm(config)
    app.state.stt = construir_stt(config)
    app.state.tts = construir_tts(config)

    yield

    await motor.dispose()


app = FastAPI(title="Pacer", lifespan=ciclo_de_vida)


@app.post("/api/turno")
async def turno(audio: UploadFile) -> JSONResponse:
    """Un turno hablado completo."""
    arranque = time.perf_counter()

    if app.state.stt is None:
        return JSONResponse(
            {"error": "sin_stt", "detalle": "falta GROQ_API_KEY en el .env"},
            status_code=503,
        )

    datos = await audio.read()
    if not datos:
        return JSONResponse({"error": "audio_vacio"}, status_code=400)

    transcripcion = app.state.stt.transcribir(datos, audio.filename or "turno.webm")
    if not transcripcion.texto:
        return JSONResponse({"error": "no_se_entendio"}, status_code=422)

    ms_stt = int((time.perf_counter() - arranque) * 1000)
    hoy = datetime.now(UTC).date()

    sesion.mensajes.append(
        {"role": "user", "content": [{"text": transcripcion.texto}]}
    )

    async with app.state.fabrica() as bd:
        repositorio = RepositorioPlan(bd)
        plan_previo = await repositorio.version_activa(CORREDOR_PILOTO)
        sistema = construir_prompt(
            construir_bloque(plan_previo, hoy=hoy, fecha_carrera=sesion.perfil.fecha_carrera)
            if plan_previo and sesion.perfil.fecha_carrera
            else None
        )

        resultado = await atender_turno(
            llm=app.state.llm,
            repositorio=repositorio,
            sistema=sistema,
            mensajes=sesion.mensajes,
            perfil=sesion.perfil,
            corredor_id=CORREDOR_PILOTO,
            hoy=hoy,
        )

    ms_coach = int((time.perf_counter() - arranque) * 1000)

    sesion.perfil = resultado.perfil
    sesion.mensajes = resultado.mensajes
    sesion.mensajes.append(
        {"role": "assistant", "content": [{"text": resultado.texto or "..."}]}
    )

    voz = app.state.tts.sintetizar(resultado.texto) if resultado.texto else b""
    ms_total = int((time.perf_counter() - arranque) * 1000)

    return JSONResponse(
        {
            "transcripcion": transcripcion.texto,
            "respuesta": resultado.texto,
            "audio_base64": base64.b64encode(voz).decode(),
            "herramientas": list(resultado.herramientas_usadas),
            "plan_version": resultado.plan.version if resultado.plan else None,
            "motivo_cambio": resultado.plan.motivo_cambio if resultado.plan else None,
            "latencia_ms": {
                "transcripcion": ms_stt,
                "coach": ms_coach - ms_stt,
                "voz": ms_total - ms_coach,
                "total": ms_total,
            },
        }
    )


@app.get("/api/salud")
async def salud() -> dict[str, Any]:
    """Qué capacidades están vivas. Útil cuando algo falla desde el teléfono."""
    config = configuracion()
    return {
        "stt": config.stt_disponible,
        "base": "postgres" if config.es_postgres else "sqlite",
        "region": config.aws_region,
        "observabilidad": config.observabilidad_disponible,
    }


# Se monta al final para que las rutas /api tengan precedencia sobre la raíz.
app.mount("/", StaticFiles(directory=DIRECTORIO_WEB, html=True), name="web")
