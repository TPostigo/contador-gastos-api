import os
import pytest

# IMPORTANTE: esto tiene que ejecutarse ANTES de importar db o api_gastos,
# para que usen esta base de datos de pruebas y no la real
os.environ["CLAVE_SECRETA"] = "clave-de-pruebas-no-usar-en-produccion"

import db
db.DB_PATH = "test_gastos.db"  # sustituimos la ruta de la BD por una de pruebas

from fastapi.testclient import TestClient
from api_gastos import app


@pytest.fixture
def client():
    """
    Un 'fixture' es preparación reutilizable para los tests.
    Cada test que lo pida recibe un cliente con base de datos limpia.
    """
    # Aseguramos tablas frescas antes de cada test
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.crear_tablas()

    yield TestClient(app)  # aquí se "pausa" y se ejecuta el test

    # Esto se ejecuta después del test, sea cual sea el resultado
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)