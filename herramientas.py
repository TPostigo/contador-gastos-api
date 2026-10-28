"""
Funciones de consulta que usará el asistente de IA.

Regla clave: el número lo calcula siempre la base de datos, nunca el modelo.
El asistente solo elige cuál de estas funciones llamar y con qué parámetros,
y después redacta la respuesta con el resultado que devuelven.
"""
import datetime

import db

CATEGORIAS_VALIDAS = {"comida", "casa", "ocio", "transporte", "otros"}
LIMITE_MAXIMO = 50


def _validar_fecha(valor, nombre):
    """Acepta None o una fecha AAAA-MM-DD. Lanza ValueError si no es válida."""
    if valor is None:
        return None
    try:
        datetime.date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nombre} debe tener formato AAAA-MM-DD, recibido: {valor!r}")
    return valor


def _validar_categoria(categoria):
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(f"Categoría no válida: {categoria!r}")
    return categoria


def total_por_categoria(usuario_id, categoria, desde=None, hasta=None):
    """Suma de gastos de una categoría, opcionalmente entre dos fechas (ambas incluidas)."""
    _validar_categoria(categoria)
    desde = _validar_fecha(desde, "desde")
    hasta = _validar_fecha(hasta, "hasta")

    con = db.conectar()
    fila = con.execute(
        """
        SELECT COALESCE(SUM(importe), 0) AS total, COUNT(*) AS num_gastos
        FROM gastos
        WHERE usuario_id = ? AND categoria = ?
          AND (? IS NULL OR fecha >= ?)
          AND (? IS NULL OR fecha <= ?)
        """,
        (usuario_id, categoria, desde, desde, hasta, hasta),
    ).fetchone()
    con.close()

    return {
        "categoria": categoria,
        "total": round(fila["total"], 2),
        "num_gastos": fila["num_gastos"],
        "desde": desde,
        "hasta": hasta,
    }


def total_general(usuario_id, desde=None, hasta=None):
    """Suma de todos los gastos, de todas las categorías, entre dos fechas (ambas incluidas)."""
    desde = _validar_fecha(desde, "desde")
    hasta = _validar_fecha(hasta, "hasta")

    con = db.conectar()
    fila = con.execute(
        """
        SELECT COALESCE(SUM(importe), 0) AS total, COUNT(*) AS num_gastos
        FROM gastos
        WHERE usuario_id = ?
          AND (? IS NULL OR fecha >= ?)
          AND (? IS NULL OR fecha <= ?)
        """,
        (usuario_id, desde, desde, hasta, hasta),
    ).fetchone()
    con.close()

    return {
        "total": round(fila["total"], 2),
        "num_gastos": fila["num_gastos"],
        "desde": desde,
        "hasta": hasta,
    }


def resumen_por_categoria(usuario_id, desde=None, hasta=None):
    """Total de cada categoría entre dos fechas, de mayor a menor importe."""
    desde = _validar_fecha(desde, "desde")
    hasta = _validar_fecha(hasta, "hasta")

    con = db.conectar()
    filas = con.execute(
        """
        SELECT categoria, SUM(importe) AS total, COUNT(*) AS num_gastos
        FROM gastos
        WHERE usuario_id = ?
          AND (? IS NULL OR fecha >= ?)
          AND (? IS NULL OR fecha <= ?)
        GROUP BY categoria
        ORDER BY total DESC
        """,
        (usuario_id, desde, desde, hasta, hasta),
    ).fetchall()
    con.close()

    categorias = [
        {"categoria": f["categoria"], "total": round(f["total"], 2), "num_gastos": f["num_gastos"]}
        for f in filas
    ]
    return {
        "categorias": categorias,
        "total": round(sum(c["total"] for c in categorias), 2),
        "desde": desde,
        "hasta": hasta,
    }


def gastos_en_rango(usuario_id, desde=None, hasta=None, categoria=None, limite=20):
    """Lista de gastos entre dos fechas, del más reciente al más antiguo."""
    desde = _validar_fecha(desde, "desde")
    hasta = _validar_fecha(hasta, "hasta")
    if categoria is not None:
        _validar_categoria(categoria)
    limite = max(1, min(int(limite), LIMITE_MAXIMO))

    con = db.conectar()
    filas = con.execute(
        """
        SELECT id, descripcion, importe, categoria, fecha
        FROM gastos
        WHERE usuario_id = ?
          AND (? IS NULL OR fecha >= ?)
          AND (? IS NULL OR fecha <= ?)
          AND (? IS NULL OR categoria = ?)
        ORDER BY fecha DESC
        LIMIT ?
        """,
        (usuario_id, desde, desde, hasta, hasta, categoria, categoria, limite),
    ).fetchall()
    con.close()

    return [dict(fila) for fila in filas]


def mayor_gasto(usuario_id, desde=None, hasta=None):
    """El gasto de mayor importe en el rango indicado, o None si no hay ninguno."""
    desde = _validar_fecha(desde, "desde")
    hasta = _validar_fecha(hasta, "hasta")

    con = db.conectar()
    fila = con.execute(
        """
        SELECT id, descripcion, importe, categoria, fecha
        FROM gastos
        WHERE usuario_id = ?
          AND (? IS NULL OR fecha >= ?)
          AND (? IS NULL OR fecha <= ?)
        ORDER BY importe DESC
        LIMIT 1
        """,
        (usuario_id, desde, desde, hasta, hasta),
    ).fetchone()
    con.close()

    return dict(fila) if fila is not None else None