import json
import os

import pytest

# conftest.py ya apunta db.DB_PATH a una base de pruebas antes de importar nada
import db
import asistente


@pytest.fixture
def datos():
    """Base de pruebas limpia con cuatro gastos del usuario 1."""
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.crear_tablas()

    con = db.conectar()
    con.execute(
        "INSERT INTO usuarios (id, email, password, saldo_inicial) VALUES (1, 'u1@test.com', 'x', 0)"
    )
    con.executemany(
        "INSERT INTO gastos (id, usuario_id, descripcion, importe, categoria, fecha) "
        "VALUES (?, 1, ?, ?, ?, ?)",
        [
            ("1", "Mercadona", 45.00, "comida", "2026-08-03"),
            ("2", "Restaurante", 30.50, "comida", "2026-08-20"),
            ("3", "Alquiler", 600.00, "casa", "2026-08-01"),
            ("4", "Cine", 12.00, "ocio", "2026-09-05"),
        ],
    )
    con.commit()
    con.close()

    yield

    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)


def llamada(nombre, argumentos, id_llamada="c1"):
    """Construye una llamada a herramienta con el mismo formato que devuelve Groq."""
    return {
        "id": id_llamada,
        "type": "function",
        "function": {"name": nombre, "arguments": json.dumps(argumentos)},
    }


def modelo_que_pide_y_luego_responde(llamadas_pedidas, texto_final):
    """Simula al modelo: primera respuesta pide herramientas, segunda contesta."""
    turnos = []

    def modelo(mensajes):
        turnos.append(list(mensajes))
        if len(turnos) == 1:
            return {"role": "assistant", "content": "", "tool_calls": llamadas_pedidas}
        return {"role": "assistant", "content": texto_final}

    modelo.turnos = turnos
    return modelo


# ---------- flujo básico ----------

def test_sin_herramientas_devuelve_la_respuesta_directa(datos):
    def modelo(mensajes):
        return {"role": "assistant", "content": "Hola"}

    assert asistente.responder(1, "hola", modelo=modelo) == "Hola"


def test_ejecuta_la_herramienta_y_pasa_el_resultado_al_modelo(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("total_por_categoria", {"categoria": "comida"})],
        "Has gastado 75.5 € en comida.",
    )

    respuesta = asistente.responder(1, "¿cuánto gasté en comida?", modelo=modelo)

    assert respuesta == "Has gastado 75.5 € en comida."
    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert json.loads(mensaje_tool["content"])["total"] == 75.5


def test_el_mensaje_del_sistema_no_permite_inventar_periodos(datos):
    capturados = {}

    def modelo_captura(mensajes):
        capturados["sistema"] = mensajes[0]["content"]
        return {"role": "assistant", "content": "ok"}

    asistente.responder(1, "hola", modelo=modelo_captura, hoy="2026-10-23")

    assert "no inventes un periodo" in capturados["sistema"]


def test_el_mensaje_del_sistema_incluye_la_fecha_de_hoy(datos):
    capturados = {}

    def modelo_captura(mensajes):
        capturados["mensajes"] = mensajes
        return {"role": "assistant", "content": "ok"}

    asistente.responder(1, "hola", modelo=modelo_captura, hoy="2026-10-23")

    assert "2026-10-23" in capturados["mensajes"][0]["content"]


# ---------- errores que se devuelven al modelo ----------

def test_herramienta_inexistente_se_devuelve_como_error(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("borrar_todo", {})], "No puedo hacer eso."
    )

    respuesta = asistente.responder(1, "borra todo", modelo=modelo)

    assert respuesta == "No puedo hacer eso."
    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert "error" in json.loads(mensaje_tool["content"])


def test_fecha_invalida_se_devuelve_como_error(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("total_por_categoria", {"categoria": "comida", "desde": "agosto"})],
        "No he entendido la fecha.",
    )

    asistente.responder(1, "comida en agosto", modelo=modelo)

    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert "error" in json.loads(mensaje_tool["content"])


def test_argumentos_desconocidos_se_devuelven_como_error(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("mayor_gasto", {"moneda": "EUR"})], "Ok."
    )

    asistente.responder(1, "mayor gasto", modelo=modelo)

    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert "error" in json.loads(mensaje_tool["content"])


# ---------- parámetros nulos ----------

def test_las_herramientas_indican_que_no_se_envien_nulls():
    # Groq rechaza las llamadas con null en campos de texto (error 400 tool_use_failed)
    for herramienta in asistente.HERRAMIENTAS:
        propiedades = herramienta["function"]["parameters"].get("properties", {})
        for nombre in ("desde", "hasta"):
            if nombre in propiedades:
                assert "nunca envíes null" in propiedades[nombre]["description"]


def test_el_mensaje_del_sistema_pide_no_enviar_nulls(datos):
    capturados = {}

    def modelo_captura(mensajes):
        capturados["sistema"] = mensajes[0]["content"]
        return {"role": "assistant", "content": "ok"}

    asistente.responder(1, "hola", modelo=modelo_captura)

    assert "nunca envíes null" in capturados["sistema"]


# ---------- herramientas de resumen ----------

def test_el_asistente_puede_usar_el_resumen_por_categoria(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("resumen_por_categoria", {})], "La categoría con más gastos es casa."
    )

    respuesta = asistente.responder(1, "¿en qué gasto más?", modelo=modelo)

    assert respuesta == "La categoría con más gastos es casa."
    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert json.loads(mensaje_tool["content"])["categorias"][0]["categoria"] == "casa"


def test_el_asistente_puede_usar_el_total_general(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("total_general", {"desde": "2026-08-01", "hasta": "2026-08-31"})], "ok"
    )

    asistente.responder(1, "¿cuánto gasté en agosto?", modelo=modelo)

    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert json.loads(mensaje_tool["content"])["total"] == 675.50


# ---------- límite de vueltas ----------

def test_si_el_modelo_no_para_de_pedir_datos_se_corta(datos):
    veces = {"n": 0}

    def modelo_infinito(mensajes):
        veces["n"] += 1
        return {"role": "assistant", "content": "", "tool_calls": [
            llamada("mayor_gasto", {}, id_llamada=f"c{veces['n']}")
        ]}

    respuesta = asistente.responder(1, "bucle", modelo=modelo_infinito)

    assert veces["n"] == asistente.MAX_VUELTAS
    assert "No he podido responder" in respuesta


# ---------- aislamiento entre usuarios ----------

def test_el_asistente_solo_consulta_los_gastos_del_usuario_que_pregunta(datos):
    modelo = modelo_que_pide_y_luego_responde(
        [llamada("total_por_categoria", {"categoria": "comida"})], "ok"
    )

    asistente.responder(2, "comida", modelo=modelo)

    mensaje_tool = [m for m in modelo.turnos[1] if m["role"] == "tool"][0]
    assert json.loads(mensaje_tool["content"])["total"] == 0


# ---------- endpoint /asistente ----------

def registrar_y_obtener_cabecera(client):
    token = client.post("/registro", json={
        "email": "ana@test.com", "password": "1234", "saldo_inicial": 0,
    }).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_endpoint_asistente_sin_clave_devuelve_503(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cabecera = registrar_y_obtener_cabecera(client)

    respuesta = client.post("/asistente", json={"pregunta": "¿cuánto gasté?"}, headers=cabecera)

    assert respuesta.status_code == 503


def test_endpoint_asistente_devuelve_la_respuesta(client, monkeypatch):
    def modelo_falso(mensajes):
        return {"role": "assistant", "content": "Respuesta de prueba"}

    monkeypatch.setattr(asistente, "llamar_groq", modelo_falso)
    cabecera = registrar_y_obtener_cabecera(client)

    respuesta = client.post("/asistente", json={"pregunta": "hola"}, headers=cabecera)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"respuesta": "Respuesta de prueba"}


def test_endpoint_asistente_exige_token(client):
    respuesta = client.post("/asistente", json={"pregunta": "hola"})

    assert respuesta.status_code in (401, 403)