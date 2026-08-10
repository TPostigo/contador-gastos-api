import sqlite3

DB_PATH = "gastos.db"

def conectar() -> sqlite3.Connection:
    """Abre una conexión a la base de datos."""
    con = sqlite3.connect(DB_PATH)
    # row_factory: las filas se devuelven como diccionarios (fila["campo"])
    # en vez de tuplas (fila[0]), mucho más legible
    con.row_factory = sqlite3.Row
    # Activar claves foráneas (SQLite las trae DESACTIVADAS por defecto, ojo)
    con.execute("PRAGMA foreign_keys = ON")
    return con

def crear_tablas() -> None:
    """Crea las tablas si no existen. Se llama al arrancar la API."""
    con = conectar()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL,
            saldo_inicial REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id          TEXT PRIMARY KEY,
            usuario_id  INTEGER NOT NULL,
            descripcion TEXT NOT NULL,
            importe     REAL NOT NULL CHECK (importe > 0),
            categoria   TEXT NOT NULL,
            fecha       TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );
    """)
    # Usuario demo provisional hasta que llegue el login (Fase 3)
    con.execute("""
        INSERT OR IGNORE INTO usuarios (id, email, password, saldo_inicial)
        VALUES (1, 'demo@demo.com', 'temporal', 0)
    """)
    con.commit()
    con.close()