"""Controladores HTTP. Cada clase registra sus rutas en su propio APIRouter."""
from fastapi import APIRouter

from ...contenedor import Contenedor
from ..vistas import Vistas


class Controlador:
    """Base de los controladores: acceso a los servicios de negocio y a las vistas."""

    def __init__(self, servicios: Contenedor, vistas: Vistas):
        self.servicios = servicios
        self.vistas = vistas
        self.router = APIRouter()
        self.registrar_rutas()

    def registrar_rutas(self) -> None:
        raise NotImplementedError

    def ruta(self, metodo: str, camino: str, accion, **opciones) -> None:
        self.router.add_api_route(camino, accion, methods=[metodo], **opciones)
