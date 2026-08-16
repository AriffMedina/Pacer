"""Puerto de persistencia de planes.

El dominio y la aplicación hablan con esto; quién lo implemente —Postgres,
SQLite o una lista en memoria— es problema de infraestructura.
"""

from typing import Protocol

from pacer.domain.entidades.plan import Plan


class PuertoRepositorioPlan(Protocol):
    async def guardar(self, plan: Plan, corredor_id: int) -> None: ...

    async def version_activa(self, corredor_id: int) -> Plan | None: ...

    async def versiones(self, corredor_id: int) -> list[Plan]: ...
