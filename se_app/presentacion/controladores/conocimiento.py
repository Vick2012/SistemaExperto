"""CU08 y CU09: base de conocimiento, editor de granulos y arbol de decision (experto y administrador)."""
from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse

from ...negocio.errores import ErrorValidacion
from ..seguridad_web import requiere_experto
from . import Controlador


class ControladorConocimiento(Controlador):
    def registrar_rutas(self):
        self.ruta("GET", "/conocimiento", self.ver, response_class=HTMLResponse)
        self.ruta("GET", "/conocimiento/hipotesis/{codigo}", self.ver_granulo, response_class=HTMLResponse)
        self.ruta("POST", "/conocimiento/hipotesis/{codigo}", self.guardar_granulo, response_class=HTMLResponse)
        self.ruta("POST", "/conocimiento/recargar", self.recargar)
        self.ruta("GET", "/arbol", self.ver_arbol, response_class=HTMLResponse)

    @property
    def servicio(self):
        return self.servicios.conocimiento

    def ver(self, request: Request, categoria: str = "ELE", hipotesis: str = "", pendientes: int = 0,
            u: dict = Depends(requiere_experto)):
        filas = self.servicio.reglas_de_categoria(categoria, bool(pendientes))
        elegida = hipotesis or (filas[0]["codigo"] if filas else "")
        return self.vistas.pagina(request, "conocimiento.html", filas=filas, categoria=categoria, pendientes=pendientes,
                                  resumen=self.servicio.resumen(), cambios=self.servicio.ultimos_cambios(),
                                  guardado=None, error=None, **self.servicio.granulo(elegida, u))

    def ver_granulo(self, request: Request, codigo: str, u: dict = Depends(requiere_experto)):
        return self.vistas.pagina(request, "_granulo.html", guardado=None, error=None, **self.servicio.granulo(codigo, u))

    def guardar_granulo(self, request: Request, codigo: str, diagnostico: str = Form(...), nivel_urgencia: str = Form(...),
                        factor_certeza: int = Form(...), especialista: str = Form(...),
                        accion_recomendada: str = Form(...), validada: int = Form(0), activa: int = Form(0),
                        u: dict = Depends(requiere_experto)):
        cambios = {"diagnostico": diagnostico.strip(), "nivel_urgencia": nivel_urgencia, "factor_certeza": factor_certeza,
                   "especialista": especialista.strip(), "accion_recomendada": accion_recomendada.strip(),
                   "validada": validada, "activa": activa}
        try:
            guardado, error = self.servicio.guardar_regla(codigo, cambios, u), None
        except ErrorValidacion as e:
            guardado, error = None, str(e)
        return self.vistas.pagina(request, "_granulo.html", guardado=guardado, error=error,
                                  **self.servicio.granulo(codigo, u))

    def recargar(self, request: Request, u: dict = Depends(requiere_experto)):
        self.servicio.recargar()
        return self.vistas.redirigir(request, "/conocimiento")

    def ver_arbol(self, request: Request, categoria: str = "ELE", u: dict = Depends(requiere_experto)):
        return self.vistas.pagina(request, "arbol.html", **self.servicio.arbol(categoria))
