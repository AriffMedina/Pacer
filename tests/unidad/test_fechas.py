from datetime import date

from pacer.application.contexto.fechas import interpretar_fecha


def test_acepta_iso() -> None:
    assert interpretar_fecha("2026-12-12") == date(2026, 12, 12)


def test_acepta_el_formato_de_uso_diario_en_mexico() -> None:
    assert interpretar_fecha("12/12/2026") == date(2026, 12, 12)


def test_distingue_dia_de_mes_cuando_es_posible() -> None:
    # 25 no puede ser mes: es día. Sin esto se leería como 25 de... nada.
    assert interpretar_fecha("25/03/2026") == date(2026, 3, 25)


def test_acepta_como_lo_dice_una_persona() -> None:
    assert interpretar_fecha("12 de diciembre de 2026") == date(2026, 12, 12)


def test_acepta_el_mes_sin_la_preposicion() -> None:
    assert interpretar_fecha("1 marzo 2027") == date(2027, 3, 1)


def test_tolera_acentos_y_mayusculas() -> None:
    assert interpretar_fecha("3 de Marzo de 2026") == date(2026, 3, 3)


def test_lo_que_no_entiende_devuelve_none() -> None:
    assert interpretar_fecha("el próximo verano") is None
    assert interpretar_fecha("") is None


def test_una_fecha_imposible_no_revienta() -> None:
    assert interpretar_fecha("2026-02-31") is None
    assert interpretar_fecha("45/13/2026") is None
