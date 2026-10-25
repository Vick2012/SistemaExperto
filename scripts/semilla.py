"""Crea o actualiza los usuarios de prueba con contrasenas cifradas reales.

El script 04_consultas_granulos.sql inserta los usuarios admin, experto y
consulta con resumenes de ejemplo que no sirven para iniciar sesion. Este
script les asigna la contrasena de prueba SEED_PASSWORD (aplicacion/.env),
cifrada con scrypt (RNF02), y les crea una vivienda si no tienen.

Uso (desde la carpeta aplicacion):
    .venv\\Scripts\\python -m scripts.semilla
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from se_app import config  # noqa: E402
from se_app.datos.conexion import crear_base_datos  # noqa: E402
from se_app.datos.repositorio_atenciones import RepositorioAtenciones  # noqa: E402
from se_app.datos.repositorio_usuarios import RepositorioUsuarios  # noqa: E402
from se_app.negocio.servicio_usuarios import ServicioUsuarios  # noqa: E402

USUARIOS = [
    ("ADMINISTRADOR", "1000000001", "Usuario", "Administrador", "admin@ejemplo.test", "admin"),
    ("EXPERTO", "1000000002", "Usuario", "Experto", "experto@ejemplo.test", "experto"),
    ("CONSULTANTE", "1000000003", "Usuario", "Consultante", "consulta@ejemplo.test", "consulta"),
]


def contrasena_de_prueba() -> str:
    """SEED_PASSWORD del entorno, de aplicacion/.env o de .env.example, en ese orden."""
    if os.environ.get("SEED_PASSWORD"):
        return os.environ["SEED_PASSWORD"]
    for nombre in (".env", ".env.example"):
        archivo = config.RAIZ_APP / nombre
        if not archivo.exists():
            continue
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if linea.startswith("SEED_PASSWORD=") and linea.split("=", 1)[1].strip():
                return linea.split("=", 1)[1].strip()
    raise SystemExit("Defina SEED_PASSWORD en aplicacion/.env (contraseña de prueba de los usuarios).")


def main():
    clave = contrasena_de_prueba()
    bd = crear_base_datos()
    usuarios, atenciones = RepositorioUsuarios(bd), RepositorioAtenciones(bd)
    for rol, documento, nombres, apellidos, correo, usuario in USUARIOS:
        resumen = ServicioUsuarios.cifrar(clave)
        existe = usuarios.por_usuario(usuario)
        if existe:
            usuarios.actualizar_contrasena(existe["id_usuario"], resumen)
            id_usuario = existe["id_usuario"]
        else:
            id_usuario = usuarios.crear({"tipo_documento": "CC", "numero_documento": documento, "nombres": nombres,
                                         "apellidos": apellidos, "correo": correo, "usuario": usuario}, rol, resumen)
        if not usuarios.tiene_vivienda(id_usuario):
            atenciones.crear_vivienda(id_usuario, {"alias": "Casa principal", "direccion": "Calle 00 # 00-00",
                                                   "ciudad": "Bogotá", "tipo_vivienda": "Casa", "antiguedad_anios": 25})
        print(f"  {usuario:<10} {rol}")
    print("Usuarios de prueba listos. La contraseña es SEED_PASSWORD de aplicacion/.env.")


if __name__ == "__main__":
    main()
