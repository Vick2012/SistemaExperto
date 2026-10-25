"""Control de acceso por rol en la web (RNF01): dependencias de FastAPI sobre la sesion."""
from fastapi import Request

from ..negocio.servicio_usuarios import ServicioUsuarios


class NoAutenticado(Exception):
    pass


class SinPermiso(Exception):
    pass


def usuario_actual(request: Request) -> dict:
    u = request.session.get("usuario")
    if not u:
        raise NoAutenticado()
    return u


def requiere_experto(request: Request) -> dict:
    u = usuario_actual(request)
    if not ServicioUsuarios.es_experto(u):
        raise SinPermiso()
    return u


def requiere_admin(request: Request) -> dict:
    u = usuario_actual(request)
    if u["rol"] != "ADMINISTRADOR":
        raise SinPermiso()
    return u
