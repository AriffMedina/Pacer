from pacer.application.contexto.prompt_sistema import construir_prompt


def test_sin_plan_devuelve_solo_las_instrucciones() -> None:
    prompt = construir_prompt()

    assert "REGLA DE REGISTRO" in prompt
    assert "ESTADO ACTUAL" not in prompt


def test_con_estado_lo_incrusta_y_pide_que_lo_lea() -> None:
    prompt = construir_prompt("HOY: jueves 20 de agosto · SEMANA 2 DE 12")

    assert "SEMANA 2 DE 12" in prompt
    assert "léelo, no lo calcules" in prompt


def test_ordena_guardar_antes_de_preguntar() -> None:
    prompt = construir_prompt()

    assert "Guardar primero, preguntar después" in prompt


def test_le_prohibe_afirmar_lo_que_no_hizo() -> None:
    """Medido en vivo: recibió un error de herramienta y dijo "ya lo registré"."""
    prompt = construir_prompt()

    assert "REGLA DE HONESTIDAD" in prompt
    assert "NO PASÓ NADA" in prompt


def test_le_prohibe_echarle_la_culpa_al_sistema() -> None:
    prompt = construir_prompt()

    assert "REGLA DE VOZ PROPIA" in prompt
    assert "el sistema" in prompt


def test_limita_el_largo_porque_el_texto_se_vuelve_audio() -> None:
    prompt = construir_prompt()

    assert "MÁXIMO 2 frases" in prompt
    assert "UNA sola pregunta" in prompt


def test_prohibe_listas_y_negritas() -> None:
    prompt = construir_prompt()

    assert "Nada de listas" in prompt


def test_ordena_registrar_la_sesion_sin_esperar_los_kilometros() -> None:
    prompt = construir_prompt()

    assert "REGLA DE SESIÓN" in prompt
    assert "kilómetros son OPCIONALES" in prompt


def test_le_prohibe_prometer_cambios_que_no_hizo() -> None:
    """El fallo más caro: dijo "listo, ajusto el plan" y el plan no cambió."""
    prompt = construir_prompt()

    assert "REGLA DE NO PROMETER" in prompt
    assert "todavía no lo puedo hacer" in prompt


def test_el_estado_manda_sobre_lo_que_el_modelo_cree_recordar() -> None:
    """Una promesa falsa se queda en el historial pareciendo un hecho.

    Medido en vivo: al día siguiente afirmó "estás en reposo hasta el viernes"
    porque él mismo lo había dicho, aunque nunca hubiera ocurrido.
    """
    prompt = construir_prompt()

    assert "REGLA DE ESTADO SOBRE MEMORIA" in prompt
    assert "MANDA EL ESTADO" in prompt


def test_deja_claro_que_el_modelo_no_calcula_el_plan() -> None:
    prompt = construir_prompt()

    assert "tú no calculas el plan" in prompt
