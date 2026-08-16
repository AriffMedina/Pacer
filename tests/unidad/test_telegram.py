from pacer.infrastructure.notificacion.telegram import interpretar_actualizaciones

TEXTO = {
    "result": [
        {
            "update_id": 101,
            "message": {"chat": {"id": 55}, "text": "ayer corrí 12 km"},
        }
    ]
}

VOZ = {
    "result": [
        {
            "update_id": 102,
            "message": {
                "chat": {"id": 55},
                "voice": {"file_id": "AwACAgQ", "duration": 4},
            },
        }
    ]
}

RUIDO = {
    "result": [
        {"update_id": 103, "my_chat_member": {"chat": {"id": 55}}},
        {"update_id": 104, "message": {"chat": {"id": 55}, "sticker": {}}},
    ]
}


def test_extrae_un_mensaje_de_texto() -> None:
    mensajes = interpretar_actualizaciones(TEXTO)

    assert len(mensajes) == 1
    assert mensajes[0].texto == "ayer corrí 12 km"
    assert mensajes[0].chat_id == 55
    assert mensajes[0].id_actualizacion == 101
    assert not mensajes[0].es_voz


def test_extrae_una_nota_de_voz() -> None:
    mensajes = interpretar_actualizaciones(VOZ)

    assert mensajes[0].es_voz
    assert mensajes[0].voz_id == "AwACAgQ"


def test_ignora_lo_que_no_sabe_atender() -> None:
    # Stickers, cambios de permisos y demás no deben llegar al coach ni
    # romper el ciclo de sondeo.
    mensajes = interpretar_actualizaciones(RUIDO)

    assert [m.id_actualizacion for m in mensajes] == [103, 104]
    assert all(not m.tiene_contenido for m in mensajes)


def test_una_respuesta_vacia_no_revienta() -> None:
    assert interpretar_actualizaciones({"result": []}) == []
    assert interpretar_actualizaciones({}) == []
