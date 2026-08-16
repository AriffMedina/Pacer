"""API interna que consume n8n.

`Architecture.md` §7.3: token en header, guardado en las credenciales de n8n y
nunca en el JSON del workflow. Y clave de idempotencia obligatoria, garantizada
por un UNIQUE en base de datos — los reintentos son seguros por construcción,
no por suerte.

n8n habla con el backend por HTTP igual que el navegador. No tiene credenciales
de base de datos. No es un componente privilegiado: es un cliente más.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from pacer.application.casos_uso.materializar_recordatorios import (
    materializar_recordatorios,
)
from pacer.composition_root import configuracion
from pacer.infrastructure.persistencia.repositorio_recordatorio import (
    RepositorioRecordatorio,
)

router = APIRouter(prefix="/internal", tags=["interna"])


def _exigir_token(recibido: str | None) -> None:
    """Sin token configurado la API interna queda cerrada, no abierta.

    El default inseguro es el que se olvida en producción.
    """
    esperado = configuracion().pacer_token

    if not esperado:
        raise HTTPException(status_code=503, detail="api interna sin configurar")
    if recibido != esperado:
        raise HTTPException(status_code=401, detail="token inválido")


@router.get("/recordatorios/vencidos")
async def vencidos(
    peticion: Request,
    x_pacer_token: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    """Lo que ya tocaba entregar. n8n hace fan-out y confirma."""
    _exigir_token(x_pacer_token)

    async with peticion.app.state.fabrica() as bd:
        pendientes = await RepositorioRecordatorio(bd).vencidos(datetime.now(UTC))

    return [
        {
            "id": r.id,
            "corredor_id": r.corredor_id,
            "texto": r.texto,
            "canal": r.canal,
            "clave_idempotencia": r.clave,
        }
        for r in pendientes
    ]


@router.post("/recordatorios/{recordatorio_id}/confirmar")
async def confirmar(
    recordatorio_id: int,
    peticion: Request,
    cuerpo: dict[str, Any] | None = None,
    x_pacer_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Marca un recordatorio como entregado.

    Repetir la llamada devuelve `entregado: false` en vez de reenviar. Eso es
    lo que vuelve seguro el reintento automático de n8n.
    """
    _exigir_token(x_pacer_token)
    datos = cuerpo or {}

    async with peticion.app.state.fabrica() as bd:
        marcado = await RepositorioRecordatorio(bd).confirmar(
            recordatorio_id, datos.get("id_mensaje_proveedor")
        )

    return {"entregado": marcado, "id": recordatorio_id}


@router.post("/recordatorios/materializar")
async def materializar(
    peticion: Request,
    x_pacer_token: str | None = Header(default=None),
) -> dict[str, int]:
    """Crea los recordatorios que falten a partir del plan vigente.

    Lo llama un workflow diario. Correrlo de más no duplica nada.
    """
    _exigir_token(x_pacer_token)

    async with peticion.app.state.fabrica() as bd:
        nuevos = await materializar_recordatorios(bd, ahora=datetime.now(UTC))

    return {"nuevos": nuevos}
