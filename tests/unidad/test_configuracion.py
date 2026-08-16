from pacer.infrastructure.configuracion import Configuracion


def test_por_defecto_usa_sqlite_local() -> None:
    config = Configuracion(_env_file=None)

    assert config.database_url.startswith("sqlite+aiosqlite")


def test_la_region_por_defecto_es_us_east_1() -> None:
    config = Configuracion(_env_file=None)

    # us-east-2 no tiene voces neural es-MX en Polly.
    assert config.aws_region == "us-east-1"


def test_una_url_de_postgres_se_respeta() -> None:
    config = Configuracion(
        _env_file=None,
        database_url="postgresql+asyncpg://pacer:pacer@localhost:5432/pacer",
    )

    assert config.es_postgres


def test_sqlite_no_se_confunde_con_postgres() -> None:
    config = Configuracion(_env_file=None)

    assert not config.es_postgres


def test_langfuse_base_url_le_gana_a_langfuse_host() -> None:
    config = Configuracion(
        _env_file=None,
        langfuse_host="http://localhost:3000",
        langfuse_base_url="https://cloud.langfuse.com",
    )

    assert config.langfuse_url == "https://cloud.langfuse.com"


def test_sin_base_url_se_usa_el_host() -> None:
    config = Configuracion(_env_file=None, langfuse_host="http://localhost:3000")

    assert config.langfuse_url == "http://localhost:3000"


def test_sin_llaves_de_langfuse_no_hay_observabilidad() -> None:
    config = Configuracion(_env_file=None)

    assert not config.observabilidad_disponible


def test_sin_llave_de_groq_lo_dice_en_vez_de_reventar() -> None:
    config = Configuracion(_env_file=None)

    assert config.groq_api_key == ""
    assert not config.stt_disponible
