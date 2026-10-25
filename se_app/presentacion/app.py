"""Aplicacion web: crea FastAPI, registra los controladores y traduce los errores a pantallas."""
import logging

import mysql.connector
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .. import config
from ..contenedor import contenedor
from .controladores.administracion import ControladorAdministracion
from .controladores.conocimiento import ControladorConocimiento
from .controladores.diagnostico import ControladorDiagnostico
from .controladores.sesion import ControladorSesion
from .controladores.viviendas import ControladorViviendas
from .seguridad_web import NoAutenticado, SinPermiso
from .vistas import CARPETA, Vistas

log = logging.getLogger("se_app")


def crear_app() -> FastAPI:
    app = FastAPI(title="Sistema experto de diagnóstico de vivienda")
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=60 * 60 * 8, same_site="lax")
    app.mount("/static", StaticFiles(directory=CARPETA / "static"), name="static")
    vistas = Vistas(contenedor.motor_prolog)

    for clase in (ControladorSesion, ControladorViviendas, ControladorDiagnostico, ControladorConocimiento,
                  ControladorAdministracion):
        app.include_router(clase(contenedor, vistas).router)

    def cargar_motor_reglas() -> None:
        try:
            log.info("Motor de reglas cargado con %s reglas", contenedor.motor_prolog.recargar())
        except mysql.connector.Error as e:
            log.error("No se pudo cargar la base de conocimiento: %s", e)

    app.add_event_handler("startup", cargar_motor_reglas)

    @app.middleware("http")
    async def motor_cargado(request: Request, call_next):
        # Si MySQL no estaba listo al arrancar, la base se carga en la primera peticion.
        if not contenedor.motor_prolog.cargado and not request.url.path.startswith("/static"):
            cargar_motor_reglas()
        return await call_next(request)

    @app.exception_handler(NoAutenticado)
    def _no_autenticado(request: Request, _):
        return vistas.redirigir(request, "/login")

    @app.exception_handler(SinPermiso)
    def _sin_permiso(request: Request, _):
        return vistas.pagina(request, "error.html", titulo="Acceso restringido",
                             mensaje="Esta sección no existe o es solo para expertos de dominio y administradores (RNF01).")

    @app.exception_handler(mysql.connector.Error)
    def _sin_base(request: Request, exc):
        log.exception("Error de base de datos", exc_info=exc)
        return vistas.pagina(request, "error.html", titulo="La base de datos no responde",
                             mensaje="Verifique que el contenedor de MySQL esté encendido y vuelva a intentarlo.")

    return app


app = crear_app()
