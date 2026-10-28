from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from enum import Enum
import pandas as pd
import numpy as np
import jwt
import urllib.error
import uuid
import db
import seguridad
import asistente

# ============================================
# Configuración de la aplicación
# ============================================

app = FastAPI(title="API Análisis de Gastos")

# CORS: permiso para que la web (localhost:5173) pueda llamarnos
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://contador-gastos-web.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear las tablas al arrancar la API
db.crear_tablas()

# ============================================
# Cuenta de demostración
# ============================================

EMAIL_DEMO = "demo@demo.com"
PASSWORD_DEMO = "demo1234"
SALDO_DEMO = 2000.0

# (descripción, importe, categoría, fecha) — tres meses de ejemplo
GASTOS_DEMO = [
    ("Supermercado", 62.40, "comida", "2026-08-03"),
    ("Gasolina", 48.10, "transporte", "2026-08-05"),
    ("Cine", 14.50, "ocio", "2026-08-09"),
    ("Restaurante", 36.80, "comida", "2026-08-12"),
    ("Abono transporte", 54.00, "transporte", "2026-08-01"),
    ("Luz", 58.20, "casa", "2026-08-15"),
    ("Internet", 39.90, "casa", "2026-08-16"),
    ("Farmacia", 12.35, "otros", "2026-08-20"),
    ("Concierto", 45.00, "ocio", "2026-08-22"),
    ("Supermercado", 71.25, "comida", "2026-09-02"),
    ("Abono transporte", 54.00, "transporte", "2026-09-01"),
    ("Taxi", 18.60, "transporte", "2026-09-07"),
    ("Cena de cumpleaños", 58.90, "comida", "2026-09-13"),
    ("Librería", 27.40, "otros", "2026-09-14"),
    ("Luz", 61.75, "casa", "2026-09-15"),
    ("Internet", 39.90, "casa", "2026-09-16"),
    ("Gimnasio", 35.00, "ocio", "2026-09-18"),
    ("Gasolina", 52.30, "transporte", "2026-09-21"),
    ("Supermercado", 66.80, "comida", "2026-10-04"),
    ("Abono transporte", 54.00, "transporte", "2026-10-01"),
    ("Ropa", 89.95, "otros", "2026-10-11"),
    ("Cafetería", 6.80, "comida", "2026-10-17"),
    ("Escapada fin de semana", 120.00, "ocio", "2026-10-19"),
]

def preparar_demo() -> None:
    """Deja la cuenta de demostración en su estado de ejemplo.

    Se ejecuta al arrancar la API: crea la cuenta si no existe y restablece
    su contraseña, su saldo y sus gastos, así que los cambios de los datos
    de ejemplo llegan también a bases de datos antiguas.
    """
    con = db.conectar()
    existe = con.execute(
        "SELECT id FROM usuarios WHERE email = ?", (EMAIL_DEMO,)
    ).fetchone()
    hash_demo = seguridad.hashear_password(PASSWORD_DEMO)
    if existe:
        usuario_id = existe["id"]
        con.execute(
            "UPDATE usuarios SET password = ?, saldo_inicial = ? WHERE id = ?",
            (hash_demo, SALDO_DEMO, usuario_id),
        )
        con.execute("DELETE FROM gastos WHERE usuario_id = ?", (usuario_id,))
    else:
        cursor = con.execute(
            "INSERT INTO usuarios (email, password, saldo_inicial) VALUES (?, ?, ?)",
            (EMAIL_DEMO, hash_demo, SALDO_DEMO),
        )
        usuario_id = cursor.lastrowid
    for descripcion, importe, categoria, fecha in GASTOS_DEMO:
        con.execute(
            "INSERT INTO gastos (id, usuario_id, descripcion, importe, categoria, fecha) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), usuario_id, descripcion, importe, categoria, fecha),
        )
    con.commit()
    con.close()

preparar_demo()

# ============================================
# Modelos de datos (Pydantic)
# ============================================

class CategoriaEnum(str, Enum):
    comida = "comida"
    casa = "casa"
    ocio = "ocio"
    transporte = "transporte"
    otros = "otros"

class Gasto(BaseModel):
    id: str
    descripcion: str = Field(min_length=1, max_length=200)
    importe: float = Field(gt=0)  # gt = "greater than": estrictamente mayor que 0
    categoria: CategoriaEnum
    fecha: str

class DatosRegistro(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4, max_length=72)
    saldo_inicial: float = Field(default=0, ge=0)

class DatosLogin(BaseModel):
    email: EmailStr
    password: str

class DatosSaldo(BaseModel):
    saldo_inicial: float = Field(ge=0)

# ============================================
# Autenticación
# ============================================

esquema_token = HTTPBearer()

def usuario_actual(
    credenciales: HTTPAuthorizationCredentials = Depends(esquema_token),
) -> int:
    """Dependencia: extrae y verifica el token, devuelve el id del usuario."""
    try:
        return seguridad.decodificar_token(credenciales.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token caducado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token no válido")

@app.post("/registro", status_code=201)
def registrar(datos: DatosRegistro):
    con = db.conectar()
    existe = con.execute(
        "SELECT id FROM usuarios WHERE email = ?", (datos.email,)
    ).fetchone()
    if existe:
        con.close()
        raise HTTPException(status_code=409, detail="Ese email ya está registrado")

    cursor = con.execute(
        "INSERT INTO usuarios (email, password, saldo_inicial) VALUES (?, ?, ?)",
        (datos.email, seguridad.hashear_password(datos.password), datos.saldo_inicial),
    )
    con.commit()
    usuario_id = cursor.lastrowid
    con.close()
    # Devolvemos un token ya: registrarse = quedar logueado
    return {"token": seguridad.crear_token(usuario_id)}

@app.post("/login")
def login(datos: DatosLogin):
    con = db.conectar()
    fila = con.execute(
        "SELECT id, password FROM usuarios WHERE email = ?", (datos.email,)
    ).fetchone()
    con.close()
    # Mismo error si el email no existe o la contraseña falla:
    # no damos pistas de cuál de los dos es (buena práctica de seguridad)
    if fila is None or not seguridad.verificar_password(datos.password, fila["password"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    return {"token": seguridad.crear_token(fila["id"])}

@app.get("/yo")
def mis_datos(usuario_id: int = Depends(usuario_actual)):
    con = db.conectar()
    fila = con.execute(
        "SELECT email, saldo_inicial FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    con.close()
    return dict(fila)

@app.put("/saldo")
def cambiar_saldo(datos: DatosSaldo, usuario_id: int = Depends(usuario_actual)):
    con = db.conectar()
    con.execute(
        "UPDATE usuarios SET saldo_inicial = ? WHERE id = ?",
        (datos.saldo_inicial, usuario_id),
    )
    con.commit()
    con.close()
    return {"saldo_inicial": datos.saldo_inicial}

# ============================================
# Endpoints CRUD de gastos (protegidos)
# ============================================

@app.get("/gastos")
def listar_gastos(usuario_id: int = Depends(usuario_actual)):
    con = db.conectar()
    filas = con.execute(
        "SELECT id, descripcion, importe, categoria, fecha "
        "FROM gastos WHERE usuario_id = ? ORDER BY fecha DESC",
        (usuario_id,),
    ).fetchall()
    con.close()
    # sqlite3.Row → dict para que FastAPI lo convierta a JSON
    return [dict(fila) for fila in filas]

@app.post("/gastos", status_code=201)
def crear_gasto(gasto: Gasto, usuario_id: int = Depends(usuario_actual)):
    con = db.conectar()
    con.execute(
        "INSERT INTO gastos (id, usuario_id, descripcion, importe, categoria, fecha) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (gasto.id, usuario_id, gasto.descripcion, gasto.importe,
         gasto.categoria.value, gasto.fecha),
    )
    con.commit()
    con.close()
    return gasto

@app.put("/gastos/{gasto_id}")
def actualizar_gasto(gasto_id: str, gasto: Gasto, usuario_id: int = Depends(usuario_actual)):
    con = db.conectar()
    cursor = con.execute(
        "UPDATE gastos SET descripcion = ?, importe = ?, categoria = ?, fecha = ? "
        "WHERE id = ? AND usuario_id = ?",
        (gasto.descripcion, gasto.importe, gasto.categoria.value, gasto.fecha,
         gasto_id, usuario_id),
    )
    con.commit()
    con.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return gasto

@app.delete("/gastos/{gasto_id}", status_code=204)
def borrar_gasto(gasto_id: str, usuario_id: int = Depends(usuario_actual)):
    con = db.conectar()
    cursor = con.execute(
        "DELETE FROM gastos WHERE id = ? AND usuario_id = ?",
        (gasto_id, usuario_id),
    )
    con.commit()
    con.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

# ============================================
# Endpoint del asistente de IA (protegido)
# ============================================

class DatosPregunta(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)

@app.post("/asistente")
def preguntar_asistente(datos: DatosPregunta, usuario_id: int = Depends(usuario_actual)):
    try:
        respuesta = asistente.responder(usuario_id, datos.pregunta)
    except RuntimeError as error:
        # Falta la clave de Groq en la configuración
        raise HTTPException(status_code=503, detail=str(error))
    except (urllib.error.URLError, KeyError, ValueError):
        # Groq no responde o devuelve algo inesperado
        raise HTTPException(status_code=502, detail="El asistente no está disponible ahora")
    return {"respuesta": respuesta}

# ============================================
# Endpoint de análisis (pandas)
# ============================================

@app.post("/analisis")
def analizar(gastos: list[Gasto]):
    # Si no hay gastos, devolvemos análisis vacío
    if not gastos:
        return {"total": 0, "num_gastos": 0}

    # Convertimos la lista de objetos Pydantic en DataFrame
    df = pd.DataFrame([g.model_dump(mode="json") for g in gastos])
    df["fecha"] = pd.to_datetime(df["fecha"])

    # Análisis básicos
    por_categoria = df.groupby("categoria")["importe"].agg(["sum", "mean", "count"])
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    por_mes = df.groupby("mes")["importe"].sum()
    df["dia_semana"] = df["fecha"].dt.day_name()
    por_dia = df.groupby("dia_semana")["importe"].mean()
    top3 = df.nlargest(3, "importe")[["descripcion", "importe"]]

    # ¿Qué % del total se lleva cada categoría?
    porcentajes = (df.groupby("categoria")["importe"].sum() / df["importe"].sum() * 100)

    # Fin de semana vs entre semana (dayofweek: 0=lunes ... 6=domingo)
    df["es_finde"] = df["fecha"].dt.dayofweek >= 5
    finde = df[df["es_finde"]]["importe"].sum()
    entre_semana = df[~df["es_finde"]]["importe"].sum()

    # La categoría dominante
    cat_top = por_categoria["sum"].idxmax()

    # Ritmo de gasto diario en el periodo
    dias_periodo = (df["fecha"].max() - df["fecha"].min()).days + 1
    ritmo_diario = df["importe"].sum() / dias_periodo

    # Predicción del mes siguiente (regresión lineal)
    if len(por_mes) >= 2:
        x = np.arange(len(por_mes))
        y = por_mes.values
        a, b = np.polyfit(x, y, 1)
        prediccion = a * len(por_mes) + b
        prediccion = max(0.0, float(prediccion))
        tendencia = "subiendo" if a > 0 else "bajando"
    else:
        prediccion = None
        tendencia = None

    return {
        "total": round(float(df["importe"].sum()), 2),
        "num_gastos": len(df),
        "gasto_medio": round(float(df["importe"].mean()), 2),
        "por_categoria": {
            cat: {
                "total": round(float(fila["sum"]), 2),
                "media": round(float(fila["mean"]), 2),
                "cuantos": int(fila["count"]),
            }
            for cat, fila in por_categoria.iterrows()
        },
        "por_mes": {mes: round(float(v), 2) for mes, v in por_mes.items()},
        "media_por_dia": {dia: round(float(v), 2) for dia, v in por_dia.items()},
        "top3": top3.to_dict(orient="records"),
        "porcentajes": {cat: round(float(v), 1) for cat, v in porcentajes.items()},
        "finde_vs_semana": {
            "fin_de_semana": round(float(finde), 2),
            "entre_semana": round(float(entre_semana), 2),
        },
        "categoria_top": str(cat_top),
        "ritmo_diario": round(float(ritmo_diario), 2),
        "prediccion_mes_siguiente": round(prediccion, 2) if prediccion is not None else None,
        "tendencia": tendencia,
    }