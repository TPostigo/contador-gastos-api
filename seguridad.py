import os
from dotenv import load_dotenv
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv()  # lee el archivo .env y carga sus variables

# Leemos la clave del entorno. Si no existe, fallamos alto y claro
# en vez de arrancar con un valor por defecto inseguro.
CLAVE_SECRETA = os.environ["CLAVE_SECRETA"]
ALGORITMO = "HS256"
DURACION_TOKEN_HORAS = 24


def hashear_password(password: str) -> str:
    """Convierte la contraseña en un hash irreversible."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, hash_guardado: str) -> bool:
    """Comprueba si una contraseña coincide con el hash guardado."""
    return bcrypt.checkpw(password.encode(), hash_guardado.encode())


def crear_token(usuario_id: int) -> str:
    """Genera un JWT firmado con el id del usuario y su caducidad."""
    datos = {
        "sub": str(usuario_id),  # "subject": a quién identifica el token
        "exp": datetime.now(timezone.utc) + timedelta(hours=DURACION_TOKEN_HORAS),
    }
    return jwt.encode(datos, CLAVE_SECRETA, algorithm=ALGORITMO)


def decodificar_token(token: str) -> int:
    """Verifica el token y devuelve el id de usuario. Lanza excepción si no es válido."""
    datos = jwt.decode(token, CLAVE_SECRETA, algorithms=[ALGORITMO])
    return int(datos["sub"])