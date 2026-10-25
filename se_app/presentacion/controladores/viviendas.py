"""CU02, CU06 y CU07: tablero, viviendas, historial y citas del consultante."""
from datetime import datetime

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..seguridad_web import usuario_actual
from . import Controlador


class ControladorViviendas(Controlador):
    def registrar_rutas(self):
        self.ruta("GET", "/", self.tablero, response_class=HTMLResponse)
        self.ruta("GET", "/viviendas", self.ver_viviendas, response_class=HTMLResponse)
        self.ruta("POST", "/viviendas", self.crear_vivienda)
        self.ruta("GET", "/historial", self.ver_historial, response_class=HTMLResponse)
        self.ruta("GET", "/citas", self.ver_citas, response_class=HTMLResponse)
        self.ruta("POST", "/citas/{id_cita}/cancelar", self.cancelar_cita)

    def tablero(self, request: Request, u: dict = Depends(usuario_actual)):
        datos = self.servicios.viviendas.tablero(u["id"])
        resumen = self.servicios.conocimiento.resumen() if self.servicios.usuarios.es_experto(u) else None
        return self.vistas.pagina(request, "tablero.html", resumen=resumen, **datos)

    def ver_viviendas(self, request: Request, bienvenida: int = 0, u: dict = Depends(usuario_actual)):
        return self.vistas.pagina(request, "viviendas.html", viviendas=self.servicios.viviendas.viviendas(u["id"]),
                                  bienvenida=bienvenida)

    def crear_vivienda(self, alias: str = Form(...), direccion: str = Form(...), ciudad: str = Form(...),
                       tipo_vivienda: str = Form("Casa"), antiguedad_anios: str = Form(""),
                       siguiente: str = Form("/viviendas"), u: dict = Depends(usuario_actual)):
        self.servicios.viviendas.crear_vivienda(u["id"], alias, direccion, ciudad, tipo_vivienda, antiguedad_anios)
        return RedirectResponse(siguiente if siguiente.startswith("/") else "/viviendas", status_code=303)

    def ver_historial(self, request: Request, categoria: str = "", zona: str = "", u: dict = Depends(usuario_actual)):
        filas = self.servicios.viviendas.historial(u["id"], categoria, zona)
        if self.vistas.es_htmx(request):
            return self.vistas.pagina(request, "_historial_tabla.html", filas=filas)
        return self.vistas.pagina(request, "historial.html", filas=filas, zonas=self.servicios.diagnostico.ZONAS,
                                  categoria=categoria, zona=zona,
                                  recurrentes=self.servicios.viviendas.recurrentes(u["id"]))

    def ver_citas(self, request: Request, u: dict = Depends(usuario_actual)):
        return self.vistas.pagina(request, "citas.html", citas=self.servicios.viviendas.citas(u["id"]),
                                  ahora=datetime.now())

    def cancelar_cita(self, id_cita: int, u: dict = Depends(usuario_actual)):
        self.servicios.viviendas.cancelar_cita(id_cita, u["id"])
        return RedirectResponse("/citas", status_code=303)
