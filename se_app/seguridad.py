"""Autenticacion y autorizacion (RF01, RNF01, RNF02).

Las contrasenas se guardan como resumen scrypt con sal aleatoria; nunca
en texto plano. El usuario se bloquea durante MINUTOS_BLOQUEO tras
MAX_INTENTOS intentos fallidos.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import Request

from . import config, db

_N, _R, _P = 2 ** 14, 8, 1

ROLES_EXPERTO = ("EXPERTO", "ADMINISTRADOR")


def cifrar(contrasena: str) -> str:
    sal = secrets.token_bytes(16)
    resumen = hashlib.scrypt(contrasena.encode(), salt=sal, n=_N, r=_R, p=_P)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(sal).decode(), base64.b64encode(resumen).decode())


def verificar(contrasena: str, almacenado: str) -> bool:
    try:
        esquema, n, r, p, sal, resumen = almacenado.split("$")
    except ValueError:
        return False          # hashes de ejemplo del script 04 u otro formato
    if esquema != "scrypt":
        return False
    calculado = hashlib.scrypt(contrasena.encode(), salt=base64.b64decode(sal),
                               n=int(n), r=int(r), p=int(p))
    return hmac.compare_digest(calculado, base64.b64decode(resumen))


class ErrorAcceso(Exception):
    pass


def autenticar(usuario: str, contrasena: str) -> dict:
    """Valida las credenciales y aplica el bloqueo por intentos (RF01)."""
    fila = db.consultar_uno(
        "SELECT id_usuario, rol, nombres, apellidos, usuario, contrasena_hash, "
        "       intentos_fallidos, bloqueado_hasta, activo "
        "FROM usuario WHERE usuario = %s", (usuario,))
    if fila is None or not fila["activo"]:
        raise ErrorAcceso("Usuario o contraseña incorrectos.")

    ahora = datetime.now()
    if fila["bloqueado_hasta"] and fila["bloqueado_hasta"] > ahora:
        minutos = int((fila["bloqueado_hasta"] - ahora).total_seconds() // 60) + 1
        raise ErrorAcceso(f"Cuenta bloqueada por intentos fallidos. Intente de nuevo en {minutos} min.")

    if not verificar(contrasena, fila["contrasena_hash"]):
        intentos = fila["intentos_fallidos"] + 1
        if intentos >= config.MAX_INTENTOS:
            db.ejecutar("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = %s WHERE id_usuario = %s",
                        (ahora + timedelta(minutes=config.MINUTOS_BLOQUEO), fila["id_usuario"]))
            raise ErrorAcceso(f"Demasiados intentos fallidos. La cuenta queda bloqueada {config.MINUTOS_BLOQUEO} min.")
        db.ejecutar("UPDATE usuario SET intentos_fallidos = %s WHERE id_usuario = %s",
                    (intentos, fila["id_usuario"]))
        restantes = config.MAX_INTENTOS - intentos
        raise ErrorAcceso(f"Usuario o contraseña incorrectos. Le quedan {restantes} intento(s).")

    db.ejecutar("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = %s",
                (fila["id_usuario"],))
    return {"id": fila["id_usuario"], "rol": fila["rol"], "usuario": fila["usuario"],
            "nombre": f'{fila["nombres"]} {fila["apellidos"]}'}


class NoAutenticado(Exception):
    pass


class SinPermiso(Exception):
    pass


def usuario_actual(request: Request) -> dict:
    u = request.session.get("usuario")
    if not u:
        raise NoAutenticado()
    return u


def es_experto(u: dict) -> bool:
    return u["rol"] in ROLES_EXPERTO


def requiere_experto(request: Request) -> dict:
    u = usuario_actual(request)
    if not es_experto(u):
        raise SinPermiso()
    return u


def requiere_admin(request: Request) -> dict:
    u = usuario_actual(request)
    if u["rol"] != "ADMINISTRADOR":
        raise SinPermiso()
    return u
