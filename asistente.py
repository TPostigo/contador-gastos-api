"""
Asistente de IA: el modelo (Groq) decide qué consulta hacer sobre los gastos
y redacta la respuesta. Las cifras siempre salen de herramientas.py, nunca
del modelo.
"""
import datetime
import json
import os
import urllib.request

import herramientas

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
MODELO = os.environ.get("GROQ_MODELO", "llama-3.3-70b-versatile")
MAX_VUELTAS = 5  # cuántas veces como máximo puede pedir datos antes de contestar

# Descripción de las herramientas tal como las ve el modelo
HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "total_por_categoria",
            "description": "Suma los gastos de una categoría, opcionalmente entre dos fechas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "enum": sorted(herramientas.CATEGORIAS_VALIDAS)},
                    "desde": {"type": "string", "description": "Fecha inicial, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                    "hasta": {"type": "string", "description": "Fecha final, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                },
                "required": ["categoria"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gastos_en_rango",
            "description": "Lista los gastos entre dos fechas, del más reciente al más antiguo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "desde": {"type": "string", "description": "Fecha inicial, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                    "hasta": {"type": "string", "description": "Fecha final, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                    "categoria": {"type": "string", "enum": sorted(herramientas.CATEGORIAS_VALIDAS)},
                    "limite": {"type": "integer", "description": "Número máximo de gastos, de 1 a 50"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mayor_gasto",
            "description": "Devuelve el gasto de mayor importe entre dos fechas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "desde": {"type": "string", "description": "Fecha inicial, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                    "hasta": {"type": "string", "description": "Fecha final, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "total_general",
            "description": "Suma todos los gastos de todas las categorías, opcionalmente entre dos fechas. Úsala para «cuánto gasté en total».",
            "parameters": {
                "type": "object",
                "properties": {
                    "desde": {"type": "string", "description": "Fecha inicial, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                    "hasta": {"type": "string", "description": "Fecha final, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_por_categoria",
            "description": "Devuelve el total de cada categoría, de mayor a menor, opcionalmente entre dos fechas. Úsala para «en qué gasto más» o «cuál es la categoría con más gastos».",
            "parameters": {
                "type": "object",
                "properties": {
                    "desde": {"type": "string", "description": "Fecha inicial, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                    "hasta": {"type": "string", "description": "Fecha final, AAAA-MM-DD. Si no hay fecha, omite el campo; nunca envíes null"},
                },
            },
        },
    },
]

FUNCIONES = {
    "total_general": herramientas.total_general,
    "resumen_por_categoria": herramientas.resumen_por_categoria,
    "total_por_categoria": herramientas.total_por_categoria,
    "gastos_en_rango": herramientas.gastos_en_rango,
    "mayor_gasto": herramientas.mayor_gasto,
}


def _mensaje_sistema(hoy):
    return (
        "Eres un asistente que responde preguntas sobre los gastos del usuario. "
        f"Hoy es {hoy}. Para cualquier cifra o lista, usa las herramientas: "
        "nunca calcules ni inventes importes. Si la pregunta no indica fechas, "
        "no inventes un periodo: consulta todos los gastos sin desde ni hasta. "
        "Al llamar a las herramientas, omite los parámetros que no uses; nunca envíes null. "
        "Responde en español, de forma breve."
    )


def llamar_groq(mensajes):
    """Llama al modelo de Groq y devuelve el mensaje de la respuesta."""
    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        raise RuntimeError("Falta GROQ_API_KEY en el archivo .env")

    cuerpo = json.dumps({
        "model": MODELO,
        "messages": mensajes,
        "tools": HERRAMIENTAS,
        "tool_choice": "auto",
        "temperature": 0,
    }).encode("utf-8")

    peticion = urllib.request.Request(
        URL_GROQ,
        data=cuerpo,
        headers={
            "Authorization": f"Bearer {clave}",
            "Content-Type": "application/json",
            # Groq (detrás de Cloudflare) rechaza el User-Agent por defecto de urllib con 403
            "User-Agent": "contador-gastos/1.0",
        },
    )
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        datos = json.loads(respuesta.read())
    return datos["choices"][0]["message"]


def _ejecutar(usuario_id, llamada):
    """Ejecuta una herramienta pedida por el modelo. Los errores se devuelven al modelo, no se lanzan."""
    nombre = llamada["function"]["name"]
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        return {"error": f"Herramienta desconocida: {nombre}"}
    try:
        argumentos = json.loads(llamada["function"].get("arguments") or "{}")
        return funcion(usuario_id, **argumentos)
    except (ValueError, TypeError) as error:
        return {"error": str(error)}


def responder(usuario_id, pregunta, modelo=None, hoy=None):
    """Responde a una pregunta sobre los gastos del usuario."""
    modelo = modelo or llamar_groq  # se resuelve al llamar, para poder sustituirlo en tests
    hoy = hoy or datetime.date.today().isoformat()

    mensajes = [
        {"role": "system", "content": _mensaje_sistema(hoy)},
        {"role": "user", "content": pregunta},
    ]

    for _ in range(MAX_VUELTAS):
        mensaje = modelo(mensajes)
        llamadas = mensaje.get("tool_calls")
        if not llamadas:
            return mensaje.get("content") or ""

        mensajes.append({
            "role": "assistant",
            "content": mensaje.get("content") or "",
            "tool_calls": llamadas,
        })
        for llamada in llamadas:
            resultado = _ejecutar(usuario_id, llamada)
            mensajes.append({
                "role": "tool",
                "tool_call_id": llamada["id"],
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })

    return "No he podido responder a esa pregunta con los datos disponibles."