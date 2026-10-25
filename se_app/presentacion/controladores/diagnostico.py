"""CU03-CU06: diagnostico guiado, reporte con las hipotesis ponderadas y cita."""
from datetime import datetime

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...negocio.errores import AccesoDenegado, ErrorValidacion
from ..seguridad_web import SinPermiso, usuario_actual
from . import Controlador


class ControladorDiagnostico(Controlador):
    def registrar_rutas(self):
        self.ruta("GET", "/diagnostico/nuevo", self.nuevo, response_class=HTMLResponse)
        self.ruta("POST", "/diagnostico", self.iniciar, response_class=HTMLResponse)
        self.ruta("GET", "/diagnostico/{id_atencion}", self.ver, response_class=HTMLResponse)
        self.ruta("POST", "/diagnostico/{id_atencion}/responder", self.responder, response_class=HTMLResponse)
        self.ruta("POST", "/diagnostico/{id_atencion}/anterior", self.anterior, response_class=HTMLResponse)
        self.ruta("POST", "/diagnostico/{id_atencion}/reiniciar", self.reiniciar, response_class=HTMLResponse)
        self.ruta("POST", "/diagnostico/{id_atencion}/corregir", self.corregir)
        self.ruta("GET", "/diagnostico/{id_atencion}/reporte", self.reporte, response_class=HTMLResponse)
        self.ruta("POST", "/diagnostico/{id_atencion}/cita", self.agendar, response_class=HTMLResponse)

    @property
    def servicio(self):
        return self.servicios.diagnostico

    def _atencion(self, id_atencion: int, u: dict) -> dict:
        try:
            return self.servicio.atencion(id_atencion, u["id"])
        except AccesoDenegado:
            raise SinPermiso()

    def nuevo(self, request: Request, categoria: str = "", u: dict = Depends(usuario_actual)):
        return self._formulario(request, u, categoria, None)

    def _formulario(self, request: Request, u: dict, categoria: str, error: str | None):
        return self.vistas.pagina(request, "diagnostico_nuevo.html", viviendas=self.servicios.viviendas.viviendas(u["id"]),
                                  zonas=self.servicio.ZONAS, elegida=categoria, error=error)

    def iniciar(self, request: Request, id_vivienda: int = Form(0), zona: str = Form(""), categoria: str = Form(""),
                u: dict = Depends(usuario_actual)):
        try:
            id_atencion = self.servicio.iniciar(u["id"], id_vivienda, categoria, zona)
        except ErrorValidacion as e:
            return self._formulario(request, u, categoria, str(e))
        except AccesoDenegado:
            raise SinPermiso()
        return RedirectResponse(f"/diagnostico/{id_atencion}", status_code=303)

    def _avanzar(self, request: Request, atencion: dict):
        """Ciclo del motor: muestra la siguiente pregunta o lleva al reporte si ya concluyo."""
        if atencion["estado"] != "EN_CURSO":
            return self.vistas.redirigir(request, f"/diagnostico/{atencion['id_atencion']}/reporte")
        decision = self.servicio.avanzar(atencion)
        if decision.concluye:
            return self.vistas.redirigir(request, f"/diagnostico/{atencion['id_atencion']}/reporte")
        plantilla = "_pregunta.html" if self.vistas.es_htmx(request) else "diagnostico.html"
        return self.vistas.pagina(request, plantilla, **self.servicio.contexto_pregunta(atencion, decision))

    def ver(self, request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
        return self._avanzar(request, self._atencion(id_atencion, u))

    def responder(self, request: Request, id_atencion: int, pregunta: str = Form(...), valor: int = Form(...),
                  u: dict = Depends(usuario_actual)):
        self.servicio.responder(self._atencion(id_atencion, u), pregunta, valor)
        return self._avanzar(request, self._atencion(id_atencion, u))

    def anterior(self, request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
        atencion = self._atencion(id_atencion, u)
        self.servicio.anterior(atencion)
        return self._avanzar(request, atencion)

    def reiniciar(self, request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
        atencion = self._atencion(id_atencion, u)
        self.servicio.reiniciar(atencion)
        return self._avanzar(request, atencion)

    def corregir(self, id_atencion: int, u: dict = Depends(usuario_actual)):
        self.servicio.corregir(self._atencion(id_atencion, u))
        return RedirectResponse(f"/diagnostico/{id_atencion}", status_code=303)

    def reporte(self, request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
        atencion = self._atencion(id_atencion, u)
        datos = self.servicio.reporte(atencion)
        if not datos:
            return RedirectResponse(f"/diagnostico/{id_atencion}", status_code=303)
        return self.vistas.pagina(request, "reporte.html", atencion=atencion, ahora=datetime.now(), cita_ok=False,
                                  citas=self.servicios.viviendas.citas(u["id"], id_atencion), **datos)

    def agendar(self, request: Request, id_atencion: int, fecha: str = Form(...), observaciones: str = Form(""),
                u: dict = Depends(usuario_actual)):
        self._atencion(id_atencion, u)
        try:
            self.servicios.viviendas.agendar(id_atencion, u["id"], fecha, observaciones)
        except AccesoDenegado:
            raise SinPermiso()
        if self.vistas.es_htmx(request):
            return self.vistas.pagina(request, "_citas.html", citas=self.servicios.viviendas.citas(u["id"], id_atencion),
                                      atencion={"id_atencion": id_atencion}, cita_ok=True, ahora=datetime.now())
        return RedirectResponse(f"/diagnostico/{id_atencion}/reporte", status_code=303)
