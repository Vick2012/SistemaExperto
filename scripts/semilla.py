"""Crea o actualiza los usuarios de prueba con contrasenas cifradas reales.

El script 04_consultas_granulos.sql inserta los usuarios admin, experto y
consulta con resumenes de ejemplo que no sirven para iniciar sesion. Este
script les asigna la contrasena de prueba SEED_PASSWORD (ver .env.example),
cifrada con scrypt (RNF02), y les crea una vivienda si no tienen.

Uso (desde la carpeta aplicacion):
    .venv\\Scripts\\python -m scripts.semilla
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from se_app import config, db, seguridad  # noqa: E402

USUARIOS = [
    ("ADMINISTRADOR", "1000000001", "Usuario", "Administrador", "admin@ejemplo.test", "admin"),
    ("EXPERTO", "1000000002", "Usuario", "Experto", "experto@ejemplo.test", "experto"),
    ("CONSULTANTE", "1000000003", "Usuario", "Consultante", "consulta@ejemplo.test", "consulta"),
]


def contrasena_de_prueba() -> str:
    valor = os.environ.get("SEED_PASSWORD")
    if not valor:
        ejemplo = config.RAIZ_APP / ".env.example"
        for linea in ejemplo.read_text(encoding="utf-8").splitlines():
            if linea.startswith("SEED_PASSWORD="):
                valor = linea.split("=", 1)[1].strip()
    return valor


def main():
    clave = contrasena_de_prueba()
    for rol, documento, nombres, apellidos, correo, usuario in USUARIOS:
        resumen = seguridad.cifrar(clave)
        existe = db.consultar_uno("SELECT id_usuario FROM usuario WHERE usuario = %s", (usuario,))
        if existe:
            db.ejecutar("UPDATE usuario SET contrasena_hash = %s, intentos_fallidos = 0, bloqueado_hasta = NULL, "
                        "activo = 1 WHERE id_usuario = %s", (resumen, existe["id_usuario"]))
            id_usuario = existe["id_usuario"]
        else:
            id_usuario = db.ejecutar(
                "INSERT INTO usuario (rol, tipo_documento, numero_documento, nombres, apellidos, correo, usuario, "
                "contrasena_hash) VALUES (%s, 'CC', %s, %s, %s, %s, %s, %s)",
                (rol, documento, nombres, apellidos, correo, usuario, resumen))
        if not db.consultar_uno("SELECT 1 AS ok FROM vivienda WHERE id_usuario = %s", (id_usuario,)):
            db.ejecutar("INSERT INTO vivienda (id_usuario, alias, direccion, ciudad, tipo_vivienda, antiguedad_anios) "
                        "VALUES (%s, 'Casa principal', 'Calle 00 # 00-00', 'Bogotá', 'Casa', 25)", (id_usuario,))
        print(f"  {usuario:<10} {rol}")
    print("Usuarios de prueba listos. La contraseña es SEED_PASSWORD (ver .env.example).")


if __name__ == "__main__":
    main()
