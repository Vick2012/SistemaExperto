"""Vistas: render de plantillas Jinja2 con el contexto comun de la aplicacion."""
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..negocio.modelos import URGENCIAS
from ..negocio.servicio_usuarios import ServicioUsuarios

CARPETA = Path(__file__).parent
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


class Vistas:
    ETIQUETA_URGENCIA = {"Critica": "Crítica", "Alta": "Alta", "Media": "Media", "Baja": "Baja"}

    def __init__(self, motor_reglas):
        # motor_reglas: MotorProlog, de donde salen las categorias del menu.
        self.motor_reglas = motor_reglas
        self.plantillas = Jinja2Templates(directory=CARPETA / "templates")
        self.plantillas.env.globals.update(ETIQUETA_URGENCIA=self.ETIQUETA_URGENCIA, URGENCIAS=URGENCIAS)
        self.plantillas.env.filters["fecha"] = self.fecha
        self.plantillas.env.filters["pct"] = lambda p: f"{float(p) * 100:.1f}".replace(".", ",")

    @staticmethod
    def fecha(valor, formato="%d %b %Y") -> str:
        if not valor:
            return ""
        return valor.strftime(formato).replace(valor.strftime("%b"), MESES[valor.month - 1])

    def pagina(self, request: Request, nombre: str, **ctx) -> HTMLResponse:
        u = request.session.get("usuario")
        ctx.update(request=request, usuario=u, experto=bool(u and ServicioUsuarios.es_experto(u)),
                   ruta_actual=request.url.path, categorias=self.motor_reglas.categorias)
        return self.plantillas.TemplateResponse(request, nombre, ctx)

    @staticmethod
    def redirigir(request: Request, url: str) -> Response:
        """Redireccion que tambien funciona en peticiones HTMX."""
        if request.headers.get("HX-Request"):
            return Response(status_code=204, headers={"HX-Redirect": url})
        return RedirectResponse(url, status_code=303)

    @staticmethod
    def es_htmx(request: Request) -> bool:
        return bool(request.headers.get("HX-Request"))
