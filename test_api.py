def test_registro_crea_usuario_y_devuelve_token(client):
    respuesta = client.post("/registro", json={
        "email": "ana@test.com",
        "password": "1234",
        "saldo_inicial": 100,
    })

    assert respuesta.status_code == 201
    assert "token" in respuesta.json()


def test_no_se_puede_registrar_el_mismo_email_dos_veces(client):
    datos = {"email": "ana@test.com", "password": "1234", "saldo_inicial": 0}
    client.post("/registro", json=datos)  # primera vez, ok

    respuesta = client.post("/registro", json=datos)  # segunda vez

    assert respuesta.status_code == 409


def test_registro_rechaza_email_invalido(client):
    respuesta = client.post("/registro", json={
        "email": "esto-no-es-un-email",
        "password": "1234",
        "saldo_inicial": 0,
    })

    assert respuesta.status_code == 422


def test_login_correcto_devuelve_token(client):
    client.post("/registro", json={
        "email": "ana@test.com", "password": "1234", "saldo_inicial": 0,
    })

    respuesta = client.post("/login", json={
        "email": "ana@test.com", "password": "1234",
    })

    assert respuesta.status_code == 200
    assert "token" in respuesta.json()


def test_login_con_password_incorrecta_falla(client):
    client.post("/registro", json={
        "email": "ana@test.com", "password": "1234", "saldo_inicial": 0,
    })

    respuesta = client.post("/login", json={
        "email": "ana@test.com", "password": "otra-cosa",
    })

    assert respuesta.status_code == 401


def test_gastos_sin_token_esta_prohibido(client):
    respuesta = client.get("/gastos")

    # HTTPBearer devuelve 401 cuando falta la cabecera Authorization por completo,
    # y reservaría 401 para un token presente pero inválido/caducado
    assert respuesta.status_code == 401





def test_un_usuario_no_ve_los_gastos_de_otro(client):
    # Usuario 1 se registra y crea un gasto
    r1 = client.post("/registro", json={
        "email": "ana@test.com", "password": "1234", "saldo_inicial": 0,
    })
    token1 = r1.json()["token"]

    client.post(
        "/gastos",
        json={"id": "g1", "descripcion": "Café", "importe": 2.5,
              "categoria": "comida", "fecha": "2026-07-20"},
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Usuario 2 se registra
    r2 = client.post("/registro", json={
        "email": "bea@test.com", "password": "5678", "saldo_inicial": 0,
    })
    token2 = r2.json()["token"]

    # Usuario 2 pide SUS gastos
    respuesta = client.get("/gastos", headers={"Authorization": f"Bearer {token2}"})

    assert respuesta.status_code == 200
    assert respuesta.json() == []  # no debe ver el gasto de ana






def _token_de_prueba(client) -> str:
    """Ayudante: registra un usuario y devuelve su token, para no repetir esto en cada test."""
    r = client.post("/registro", json={
        "email": "test@test.com", "password": "1234", "saldo_inicial": 0,
    })
    return r.json()["token"]


def test_no_se_puede_crear_gasto_con_importe_negativo(client):
    token = _token_de_prueba(client)

    respuesta = client.post(
        "/gastos",
        json={"id": "g1", "descripcion": "trampa", "importe": -20,
              "categoria": "comida", "fecha": "2026-07-20"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert respuesta.status_code == 422


def test_no_se_puede_crear_gasto_con_categoria_inventada(client):
    token = _token_de_prueba(client)

    respuesta = client.post(
        "/gastos",
        json={"id": "g1", "descripcion": "trampa", "importe": 20,
              "categoria": "vacaciones", "fecha": "2026-07-20"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert respuesta.status_code == 422