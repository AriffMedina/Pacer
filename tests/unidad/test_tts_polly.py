from pacer.infrastructure.tts.polly import LIMITE_CARACTERES, preparar_para_voz


def test_quita_las_negritas_de_markdown() -> None:
    # Sin esto Polly lee "asterisco asterisco once semanas asterisco asterisco".
    assert preparar_para_voz("Son **11 semanas** en total") == "Son 11 semanas en total"


def test_quita_las_cursivas() -> None:
    assert preparar_para_voz("es *muy* importante") == "es muy importante"


def test_convierte_las_vinetas_en_pausas() -> None:
    texto = "Necesito saber:\n- ¿Cuántos km?\n- ¿Qué día?"

    resultado = preparar_para_voz(texto)

    assert "-" not in resultado
    assert "¿Cuántos km?" in resultado


def test_colapsa_los_saltos_de_linea() -> None:
    resultado = preparar_para_voz("Hola\n\n\nqué tal")

    assert "\n" not in resultado
    assert resultado == "Hola. qué tal"


def test_recorta_lo_que_pase_del_limite() -> None:
    largo = "palabra " * 2000

    resultado = preparar_para_voz(largo)

    assert len(resultado) <= LIMITE_CARACTERES


def test_un_texto_normal_no_se_toca() -> None:
    assert preparar_para_voz("Te bajé la carga esta semana.") == (
        "Te bajé la carga esta semana."
    )
