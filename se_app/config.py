"""Configuracion de la aplicacion.

Lee las variables de ../mysql_local_prueba.env, de aplicacion/.env (que
lo complementa) y del entorno, en ese orden de prioridad creciente.
"""
import os
from pathlib import Path

RAIZ_APP = Path(__file__).resolve().parent.parent      # carpeta aplicacion/
RAIZ_PROYECTO = RAIZ_APP.parent


def _leer_env(ruta: Path) -> dict:
    valores = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


# Base: el .env de prueba del proyecto. Encima, aplicacion/.env; un valor
# vacio alli no borra el de la base (p. ej. una copia sin editar de
# .env.example). Por ultimo, las variables del entorno.
_env = _leer_env(RAIZ_PROYECTO / "mysql_local_prueba.env")
_env.update({k: v for k, v in _leer_env(RAIZ_APP / ".env").items() if v})
_env.update(os.environ)

MYSQL_HOST = _env.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(_env.get("MYSQL_PORT", "3306"))
MYSQL_USER = _env.get("MYSQL_USER", "root")
MYSQL_PASSWORD = _env.get("MYSQL_PASSWORD", "")

ESQUEMA_CONOCIMIENTO = "se_base_conocimiento"
ESQUEMA_TRANSACCIONAL = "se_transaccional"

# Clave para firmar la cookie de sesion. En produccion debe venir del entorno.
SECRET_KEY = _env.get("SECRET_KEY", "cambiar-esta-clave-en-produccion")

# Carpeta de instalacion de SWI-Prolog (para que Janus encuentre libswipl).
SWIPL_HOME = _env.get("SWIPL_HOME", r"C:\Program Files\swipl")

# RF01: bloqueo por intentos fallidos.
MAX_INTENTOS = int(_env.get("MAX_INTENTOS", "5"))
MINUTOS_BLOQUEO = int(_env.get("MINUTOS_BLOQUEO", "15"))

MOTOR_PL = RAIZ_APP / "prolog" / "motor.pl"
