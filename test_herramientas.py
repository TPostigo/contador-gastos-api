import os

import pytest

# conftest.py ya apunta db.DB_PATH a una base de pruebas antes de importar nada
import db
import herramientas


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


# ---------- total_por_categoria ----------

def test_total_comida_sin_fechas_suma_todos_los_gastos(datos):
    resultado = herramientas.total_por_categoria(1, "comida")

    assert resultado["total"] == 75.50
    assert resultado["num_gastos"] == 2


def test_total_comida_en_rango_solo_cuenta_las_fechas_indicadas(datos):
    resultado = herramientas.total_por_categoria(
        1, "comida", desde="2026-08-01", hasta="2026-08-10"
    )

    assert resultado["total"] == 45.00
    assert resultado["num_gastos"] == 1


def test_categoria_sin_gastos_devuelve_cero(datos):
    resultado = herramientas.total_por_categoria(1, "transporte")

    assert resultado["total"] == 0
    assert resultado["num_gastos"] == 0


def test_categoria_invalida_lanza_error(datos):
    with pytest.raises(ValueError):
        herramientas.total_por_categoria(1, "viajes")


def test_fecha_con_formato_incorrecto_lanza_error(datos):
    with pytest.raises(ValueError):
        herramientas.total_por_categoria(1, "comida", desde="01/08/2026")


# ---------- gastos_en_rango ----------

def test_gastos_en_rango_van_del_mas_reciente_al_mas_antiguo(datos):
    gastos = herramientas.gastos_en_rango(1)

    fechas = [g["fecha"] for g in gastos]
    assert fechas == sorted(fechas, reverse=True)


def test_gastos_en_rango_filtra_por_categoria(datos):
    gastos = herramientas.gastos_en_rango(1, categoria="comida")

    assert len(gastos) == 2
    assert all(g["categoria"] == "comida" for g in gastos)


def test_gastos_en_rango_respeta_el_limite_maximo(datos):
    gastos = herramientas.gastos_en_rango(1, limite=9999)

    assert len(gastos) == 4  # hay 4 gastos, el límite no los corta


# ---------- mayor_gasto ----------

def test_mayor_gasto_devuelve_el_alquiler(datos):
    gasto = herramientas.mayor_gasto(1)

    assert gasto["descripcion"] == "Alquiler"
    assert gasto["importe"] == 600.00


def test_mayor_gasto_en_rango_sin_gastos_devuelve_none(datos):
    assert herramientas.mayor_gasto(1, desde="2025-01-01", hasta="2025-12-31") is None


# ---------- total_general ----------

def test_total_general_suma_todas_las_categorias(datos):
    resultado = herramientas.total_general(1)

    assert resultado["total"] == 687.50
    assert resultado["num_gastos"] == 4


def test_total_general_en_rango(datos):
    resultado = herramientas.total_general(1, desde="2026-08-01", hasta="2026-08-31")

    assert resultado["total"] == 675.50  # 45 + 30.50 + 600
    assert resultado["num_gastos"] == 3


def test_total_general_con_fecha_invalida_lanza_error(datos):
    with pytest.raises(ValueError):
        herramientas.total_general(1, desde="agosto")


# ---------- resumen_por_categoria ----------

def test_resumen_por_categoria_ordena_de_mayor_a_menor(datos):
    resultado = herramientas.resumen_por_categoria(1)

    categorias = [c["categoria"] for c in resultado["categorias"]]
    assert categorias == ["casa", "comida", "ocio"]
    assert resultado["categorias"][0]["total"] == 600.00
    assert resultado["total"] == 687.50


def test_resumen_por_categoria_sin_gastos_devuelve_lista_vacia(datos):
    resultado = herramientas.resumen_por_categoria(2)

    assert resultado["categorias"] == []
    assert resultado["total"] == 0


# ---------- aislamiento entre usuarios ----------

def test_otro_usuario_no_ve_los_gastos_del_primero(datos):
    resultado = herramientas.total_por_categoria(2, "comida")

    assert resultado["total"] == 0
    assert herramientas.gastos_en_rango(2) == []