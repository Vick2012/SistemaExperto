"""CU10 y CU11: usuarios, roles y bitacora (administrador)."""
from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...negocio.errores import ErrorValidacion
from ..seguridad_web import requiere_admin
from . import Controlador
from .sesion import datos_formulario_usuario


class ControladorAdministracion(Controlador):
    def registrar_rutas(self):
        self.ruta("GET", "/bitacora", self.ver_bitacora, response_class=HTMLResponse)
        self.ruta("GET", "/usuarios", self.ver_usuarios, response_class=HTMLResponse)
        self.ruta("POST", "/usuarios", self.crear_usuario, response_class=HTMLResponse)
        self.ruta("POST", "/usuarios/{id_usuario}/{accion}", self.accion_usuario)

    def ver_bitacora(self, request: Request, u: dict = Depends(requiere_admin)):
        return self.vistas.pagina(request, "bitacora.html", filas=self.servicios.conocimiento.bitacora())

    def _pagina(self, request: Request, datos=None, errores=None, creado=""):
        usuarios = self.servicios.usuarios
        return self.vistas.pagina(request, "usuarios.html", filas=usuarios.listar(), roles=usuarios.ROLES,
                                  tipos_documento=usuarios.TIPOS_DOCUMENTO, datos=datos or {}, errores=errores or {},
                                  creado=creado)

    def ver_usuarios(self, request: Request, creado: str = "", u: dict = Depends(requiere_admin)):
        return self._pagina(request, creado=creado)

    async def crear_usuario(self, request: Request, u: dict = Depends(requiere_admin)):
        datos = await datos_formulario_usuario(request)
        try:
            self.servicios.usuarios.crear(datos, datos["rol"])
        except ErrorValidacion as e:
            return self._pagina(request, datos, e.errores)
        return RedirectResponse(f"/usuarios?creado={datos['usuario']}", status_code=303)

    def accion_usuario(self, id_usuario: int, accion: str, rol: str = Form(""), u: dict = Depends(requiere_admin)):
        usuarios = self.servicios.usuarios
        if accion == "rol":
            usuarios.cambiar_rol(id_usuario, rol)
        elif accion == "desbloquear":
            usuarios.desbloquear(id_usuario)
        elif accion == "activo":
            usuarios.alternar_activo(id_usuario, u)
        return RedirectResponse("/usuarios", status_code=303)
