"""Aplicacion web del sistema experto (capa de presentacion).

FastAPI + Jinja2 + HTMX. Las rutas solo coordinan: los datos vienen de
MySQL (atenciones, conocimiento, administracion) y las conclusiones del
motor en Prolog (motor).
"""
import logging
from datetime import datetime
from pathlib import Path

import mysql.connector
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import administracion, alertas, atenciones, config, conocimiento, motor, seguridad
from .seguridad import NoAutenticado, SinPermiso, es_experto, requiere_admin, requiere_experto, usuario_actual

log = logging.getLogger("se_app")
CARPETA = Path(__file__).parent

app = FastAPI(title="Sistema experto de diagnóstico de vivienda")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=60 * 60 * 8, same_site="lax")
app.mount("/static", StaticFiles(directory=CARPETA / "static"), name="static")
plantillas = Jinja2Templates(directory=CARPETA / "templates")

URGENCIAS = ("Critica", "Alta", "Media", "Baja")
ETIQUETA_URGENCIA = {"Critica": "Crítica", "Alta": "Alta", "Media": "Media", "Baja": "Baja"}
plantillas.env.globals.update(ETIQUETA_URGENCIA=ETIQUETA_URGENCIA, URGENCIAS=URGENCIAS)


def _fecha(valor, formato="%d %b %Y"):
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    if not valor:
        return ""
    texto = valor.strftime(formato)
    return texto.replace(valor.strftime("%b"), meses[valor.month - 1])


plantillas.env.filters["fecha"] = _fecha


# ------------------------------------------------------------------ arranque

@app.on_event("startup")
def iniciar_motor():
    try:
        reglas = motor.recargar()
        log.info("Motor de inferencia cargado con %s reglas", reglas)
    except mysql.connector.Error as e:
        log.error("No se pudo cargar la base de conocimiento: %s", e)


@app.middleware("http")
async def motor_cargado(request: Request, call_next):
    # Si MySQL no estaba listo al arrancar, se carga la base en la primera peticion.
    if not motor.base.categorias and not request.url.path.startswith("/static"):
        try:
            motor.recargar()
        except mysql.connector.Error:
            pass
    return await call_next(request)


# ------------------------------------------------------------------ utilidades

def pagina(request: Request, nombre: str, **ctx) -> HTMLResponse:
    u = request.session.get("usuario")
    ctx.update(request=request, usuario=u, experto=bool(u and es_experto(u)),
               ruta_actual=request.url.path, categorias=motor.base.categorias)
    return plantillas.TemplateResponse(request, nombre, ctx)


def redirigir(request: Request, url: str) -> Response:
    """Redireccion que tambien funciona en peticiones HTMX."""
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


@app.exception_handler(NoAutenticado)
def _no_autenticado(request: Request, _):
    return redirigir(request, "/login")


@app.exception_handler(SinPermiso)
def _sin_permiso(request: Request, _):
    return pagina(request, "error.html", titulo="Acceso restringido",
                  mensaje="Esta sección es solo para expertos de dominio y administradores (RNF01).")


@app.exception_handler(mysql.connector.Error)
def _sin_base(request: Request, exc):
    log.exception("Error de base de datos", exc_info=exc)
    return pagina(request, "error.html", titulo="La base de datos no responde",
                  mensaje="Verifique que el contenedor de MySQL esté encendido y vuelva a intentarlo.")


# ------------------------------------------------------------------ sesion (CU01)

@app.get("/login", response_class=HTMLResponse)
def ver_login(request: Request):
    return pagina(request, "login.html", error=None)


@app.post("/login")
def iniciar_sesion(request: Request, usuario: str = Form(...), contrasena: str = Form(...)):
    try:
        request.session["usuario"] = seguridad.autenticar(usuario.strip(), contrasena)
    except seguridad.ErrorAcceso as e:
        return pagina(request, "login.html", error=str(e), usuario_ingresado=usuario)
    return RedirectResponse("/", status_code=303)


CAMPOS_USUARIO = ("nombres", "apellidos", "tipo_documento", "numero_documento", "correo", "telefono",
                  "usuario", "contrasena", "confirmacion", "rol")


async def _datos_usuario(request: Request) -> dict:
    form = await request.form()
    datos = {c: str(form.get(c, "")).strip() for c in CAMPOS_USUARIO}
    datos["contrasena"], datos["confirmacion"] = form.get("contrasena", ""), form.get("confirmacion", "")
    return datos


@app.get("/registro", response_class=HTMLResponse)
def ver_registro(request: Request):
    if request.session.get("usuario"):
        return RedirectResponse("/", status_code=303)
    return pagina(request, "registro.html", datos={}, errores={}, tipos_documento=administracion.TIPOS_DOCUMENTO)


@app.post("/registro", response_class=HTMLResponse)
async def registrar(request: Request):
    """Registro publico: siempre crea consultantes (los demas roles los asigna el administrador)."""
    datos = await _datos_usuario(request)
    errores = administracion.validar_usuario(datos)
    if errores:
        return pagina(request, "registro.html", datos=datos, errores=errores,
                      tipos_documento=administracion.TIPOS_DOCUMENTO)
    administracion.crear_usuario(datos, "CONSULTANTE")
    request.session["usuario"] = seguridad.autenticar(datos["usuario"], datos["contrasena"])
    return RedirectResponse("/viviendas?bienvenida=1", status_code=303)


@app.get("/salir")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ------------------------------------------------------------------ tablero y viviendas (CU02)

@app.get("/", response_class=HTMLResponse)
def tablero(request: Request, u: dict = Depends(usuario_actual)):
    viviendas = atenciones.viviendas(u["id"])
    return pagina(request, "tablero.html", viviendas=viviendas,
                  indicadores=atenciones.indicadores(u["id"]),
                  recientes=atenciones.historial(u["id"], limite=5),
                  recurrentes=atenciones.recurrentes(u["id"]),
                  resumen=conocimiento.resumen() if es_experto(u) else None)


@app.get("/viviendas", response_class=HTMLResponse)
def ver_viviendas(request: Request, bienvenida: int = 0, u: dict = Depends(usuario_actual)):
    return pagina(request, "viviendas.html", viviendas=atenciones.viviendas(u["id"]), bienvenida=bienvenida)


@app.post("/viviendas")
def crear_vivienda(request: Request, alias: str = Form(...), direccion: str = Form(...),
                   ciudad: str = Form(...), tipo_vivienda: str = Form("Casa"),
                   antiguedad_anios: str = Form(""), siguiente: str = Form("/viviendas"),
                   u: dict = Depends(usuario_actual)):
    atenciones.crear_vivienda(u["id"], {
        "alias": alias.strip(), "direccion": direccion.strip(), "ciudad": ciudad.strip(),
        "tipo_vivienda": tipo_vivienda, "antiguedad_anios": int(antiguedad_anios) if antiguedad_anios.isdigit() else None})
    return RedirectResponse(siguiente if siguiente.startswith("/") else "/viviendas", status_code=303)


# ------------------------------------------------------------------ diagnostico (CU03, CU04, CU05)

@app.get("/diagnostico/nuevo", response_class=HTMLResponse)
def nuevo_diagnostico(request: Request, categoria: str = "", u: dict = Depends(usuario_actual)):
    return pagina(request, "diagnostico_nuevo.html", viviendas=atenciones.viviendas(u["id"]),
                  zonas=atenciones.ZONAS, elegida=categoria, error=None)


@app.post("/diagnostico")
def iniciar_diagnostico(request: Request, id_vivienda: int = Form(0), zona: str = Form(""),
                        categoria: str = Form(""), u: dict = Depends(usuario_actual)):
    # RF01: validar la informacion minima antes de iniciar la inferencia.
    faltan = [n for n, v in (("la vivienda", id_vivienda), ("la zona", zona), ("el tipo de problema", categoria)) if not v]
    if faltan or not motor.base.categoria(categoria):
        return pagina(request, "diagnostico_nuevo.html", viviendas=atenciones.viviendas(u["id"]),
                      zonas=atenciones.ZONAS, elegida=categoria,
                      error="Para continuar elija " + ", ".join(faltan or ["un tipo de problema válido"]) + ".")
    id_atencion = atenciones.crear_atencion(u["id"], id_vivienda, categoria, zona)
    return RedirectResponse(f"/diagnostico/{id_atencion}", status_code=303)


def _atencion_o_404(id_atencion: int, u: dict) -> dict:
    a = atenciones.atencion(id_atencion, u["id"])
    if not a:
        raise SinPermiso()
    return a


def _contexto_pregunta(a: dict, u: dict, codigo_pregunta: str) -> dict:
    """Datos para la pantalla de pregunta y, si es experto, el panel de razonamiento."""
    resp = atenciones.respuestas(a["id_atencion"])
    textos = motor.base.preguntas
    ctx = {
        "atencion": a,
        "pregunta": textos[codigo_pregunta],
        "numero": len(resp) + 1,
        "total": sum(1 for p in textos.values() if p["categoria"] == a["categoria"]),
        "dadas": [{"texto": textos[c]["texto_pregunta"], "valor": v} for c, v in resp],
    }
    estados = motor.estados(a["categoria"], resp)
    ctx["vivas"] = sum(1 for e in estados.values() if e != "descartada")
    if es_experto(u):
        orden = {"en_evaluacion": 0, "confirmada": 0, "descartada": 1}
        ctx["candidatas"] = sorted(
            ({"codigo": h, "estado": e, **motor.base.hipotesis[h]} for h, e in estados.items()),
            key=lambda c: (orden[c["estado"]], URGENCIAS.index(c["nivel_urgencia"]), c["codigo"]))
        ctx["memoria"] = resp
    return ctx


def _avanzar(request: Request, a: dict, u: dict) -> Response:
    """Ciclo del motor: formula la siguiente pregunta o cierra con el diagnostico."""
    if a["estado"] != "EN_CURSO":
        return redirigir(request, f"/diagnostico/{a['id_atencion']}/reporte")
    paso =motor.paso(a["categoria"], atenciones.respuestas(a["id_atencion"]))
    if paso.tipo == "pregunta":
        nombre = "_pregunta.html" if request.headers.get("HX-Request") else "diagnostico.html"
        return pagina(request, nombre, **_contexto_pregunta(a, u, paso.codigo))
    h = conocimiento.hipotesis_por_codigo(paso.codigo) if paso.tipo == "diagnostico" else None
    atenciones.cerrar(a["id_atencion"], h)
    return redirigir(request, f"/diagnostico/{a['id_atencion']}/reporte")


@app.get("/diagnostico/{id_atencion}", response_class=HTMLResponse)
def ver_diagnostico(request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
    a = _atencion_o_404(id_atencion, u)
    if a["estado"] != "EN_CURSO":
        return RedirectResponse(f"/diagnostico/{id_atencion}/reporte", status_code=303)
    return _avanzar(request, a, u)


@app.post("/diagnostico/{id_atencion}/responder")
def responder(request: Request, id_atencion: int, pregunta: str = Form(...), valor: int = Form(...),
              u: dict = Depends(usuario_actual)):
    a = _atencion_o_404(id_atencion, u)
    esperada = motor.paso(a["categoria"], atenciones.respuestas(id_atencion))
    # Solo se acepta la respuesta a la pregunta que el motor formulo (evita dobles envios).
    if a["estado"] == "EN_CURSO" and esperada.tipo == "pregunta" and esperada.codigo == pregunta:
        atenciones.registrar_respuesta(id_atencion, pregunta, 1 if valor else 0)
    return _avanzar(request, atenciones.atencion(id_atencion, u["id"]), u)


@app.post("/diagnostico/{id_atencion}/anterior")
def anterior(request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
    a = _atencion_o_404(id_atencion, u)
    atenciones.deshacer_respuesta(id_atencion)
    return _avanzar(request, a, u)


@app.post("/diagnostico/{id_atencion}/reiniciar")
def reiniciar(request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
    a = _atencion_o_404(id_atencion, u)
    atenciones.reiniciar(id_atencion)
    return _avanzar(request, a, u)


@app.post("/diagnostico/{id_atencion}/corregir")
def corregir(request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
    _atencion_o_404(id_atencion, u)
    atenciones.reabrir(id_atencion)
    atenciones.deshacer_respuesta(id_atencion)
    return RedirectResponse(f"/diagnostico/{id_atencion}", status_code=303)


@app.get("/diagnostico/{id_atencion}/reporte", response_class=HTMLResponse)
def reporte(request: Request, id_atencion: int, u: dict = Depends(usuario_actual)):
    a = _atencion_o_404(id_atencion, u)
    d = atenciones.diagnostico(id_atencion)
    if not d:
        return RedirectResponse(f"/diagnostico/{id_atencion}", status_code=303)
    textos = motor.base.preguntas
    ruta = [{"conector": "If" if i == 0 else "And", "valor": v,
             "texto": textos[c]["enunciado_positivo" if v else "enunciado_negativo"] if c in textos else c}
            for i, (c, v) in enumerate(atenciones.respuestas(id_atencion))]
    return pagina(request, "reporte.html", atencion=a, d=d, ruta=ruta, concluyente=d["id_hipotesis"] is not None,
                  inmediatas=alertas.inmediatas(a["categoria"]) if d["nivel_urgencia"] == "Critica" else [],
                  citas=atenciones.citas(u["id"], id_atencion), ahora=datetime.now(), cita_ok=False)


@app.post("/diagnostico/{id_atencion}/cita")
def agendar(request: Request, id_atencion: int, fecha: str = Form(...), observaciones: str = Form(""),
            u: dict = Depends(usuario_actual)):
    _atencion_o_404(id_atencion, u)
    atenciones.crear_cita(id_atencion, u["id"], fecha.replace("T", " "), observaciones.strip())
    if request.headers.get("HX-Request"):
        return pagina(request, "_citas.html", citas=atenciones.citas(u["id"], id_atencion),
                      atencion={"id_atencion": id_atencion}, cita_ok=True, ahora=datetime.now())
    return RedirectResponse(f"/diagnostico/{id_atencion}/reporte", status_code=303)


# ------------------------------------------------------------------ historial y citas (CU06, CU07)

@app.get("/historial", response_class=HTMLResponse)
def ver_historial(request: Request, categoria: str = "", zona: str = "", u: dict = Depends(usuario_actual)):
    filas = atenciones.historial(u["id"], categoria, zona)
    if request.headers.get("HX-Request"):
        return pagina(request, "_historial_tabla.html", filas=filas)
    return pagina(request, "historial.html", filas=filas, zonas=atenciones.ZONAS, categoria=categoria,
                  zona=zona, recurrentes=atenciones.recurrentes(u["id"]))


@app.get("/citas", response_class=HTMLResponse)
def ver_citas(request: Request, u: dict = Depends(usuario_actual)):
    return pagina(request, "citas.html", citas=atenciones.citas(u["id"]), ahora=datetime.now())


@app.post("/citas/{id_cita}/cancelar")
def cancelar_cita(id_cita: int, u: dict = Depends(usuario_actual)):
    atenciones.cancelar_cita(id_cita, u["id"])
    return RedirectResponse("/citas", status_code=303)


# ------------------------------------------------------------------ base de conocimiento (CU08, CU09)

@app.get("/conocimiento", response_class=HTMLResponse)
def ver_conocimiento(request: Request, categoria: str = "ELE", hipotesis: str = "",
                     pendientes: int = 0, u: dict = Depends(requiere_experto)):
    filas = conocimiento.hipotesis_de_categoria(categoria)
    if pendientes:
        filas = [f for f in filas if not f["validada"]]
    elegida = hipotesis or (filas[0]["codigo"] if filas else "")
    return pagina(request, "conocimiento.html", filas=filas, categoria=categoria, pendientes=pendientes,
                  resumen=conocimiento.resumen(), cambios=administracion.ultimos_cambios(),
                  **_contexto_granulo(elegida, u))


def _contexto_granulo(codigo: str, u: dict, guardado: list | None = None, error: str | None = None) -> dict:
    h = conocimiento.hipotesis_por_codigo(codigo) if codigo else None
    return {"h": h, "condiciones": conocimiento.granulo(codigo) if h else [],
            "puede_desactivar": bool(h) and (h["nivel_urgencia"] != "Critica" or u["rol"] == "ADMINISTRADOR"),
            "guardado": guardado, "error": error}


@app.get("/conocimiento/hipotesis/{codigo}", response_class=HTMLResponse)
def ver_granulo(request: Request, codigo: str, u: dict = Depends(requiere_experto)):
    return pagina(request, "_granulo.html", **_contexto_granulo(codigo, u))


@app.post("/conocimiento/hipotesis/{codigo}", response_class=HTMLResponse)
def guardar_granulo(request: Request, codigo: str, diagnostico: str = Form(...), nivel_urgencia: str = Form(...),
                    factor_certeza: int = Form(...), especialista: str = Form(...),
                    accion_recomendada: str = Form(...), validada: int = Form(0), activa: int = Form(0),
                    u: dict = Depends(requiere_experto)):
    actual = conocimiento.hipotesis_por_codigo(codigo)
    error = None
    if not 0 <= factor_certeza <= 100:
        error = "El factor de certeza debe estar entre 0 y 100."
    elif nivel_urgencia not in URGENCIAS:
        error = "Nivel de urgencia no válido."
    elif actual and not activa and actual["activa"] and actual["nivel_urgencia"] == "Critica" \
            and u["rol"] != "ADMINISTRADOR":
        error = "Solo un administrador puede desactivar reglas de urgencia crítica (RF03)."
    if error:
        return pagina(request, "_granulo.html", **_contexto_granulo(codigo, u, error=error))
    cambios = conocimiento.actualizar_hipotesis(codigo, {
        "diagnostico": diagnostico.strip(), "nivel_urgencia": nivel_urgencia, "factor_certeza": factor_certeza,
        "especialista": especialista.strip(), "accion_recomendada": accion_recomendada.strip(),
        "validada": validada, "activa": activa}, u["id"])
    if cambios:
        motor.recargar()       # el motor razona desde ya con la regla actualizada
    return pagina(request, "_granulo.html", **_contexto_granulo(codigo, u, guardado=cambios))


def _medir(nodo: dict, nivel: int = 1) -> tuple[list, int]:
    """Hojas del arbol (codigos; None = conclusion por defecto) y profundidad maxima."""
    if nodo["tipo"] != "pregunta":
        return [nodo["codigo"]], nivel
    hs, ps = _medir(nodo["si"], nivel + 1)
    hn, pn = _medir(nodo["no"], nivel + 1)
    return hs + hn, max(ps, pn)


@app.get("/arbol", response_class=HTMLResponse)
def ver_arbol(request: Request, categoria: str = "ELE", u: dict = Depends(requiere_experto)):
    if not motor.base.categoria(categoria):
        categoria = motor.base.categorias[0]["codigo"]
    raiz = motor.arbol(categoria)
    hojas, profundidad = _medir(raiz)
    reglas = {c for c, h in motor.base.hipotesis.items() if h["categoria"] == categoria}
    alcanzadas = [h for h in hojas if h]
    return pagina(request, "arbol.html", raiz=raiz, categoria=categoria,
                  categoria_nombre=motor.base.categoria(categoria)["nombre"],
                  preguntas=motor.base.preguntas, hipotesis=motor.base.hipotesis,
                  total_hojas=len(hojas), profundidad=profundidad, reglas=len(reglas),
                  inalcanzables=sorted(reglas - set(alcanzadas)),
                  repetidas=len(alcanzadas) - len(set(alcanzadas)))


@app.post("/conocimiento/recargar")
def recargar_motor(request: Request, u: dict = Depends(requiere_experto)):
    motor.recargar()
    return redirigir(request, "/conocimiento")


# ------------------------------------------------------------------ administracion (CU10, CU11)

@app.get("/bitacora", response_class=HTMLResponse)
def ver_bitacora(request: Request, u: dict = Depends(requiere_admin)):
    return pagina(request, "bitacora.html", filas=administracion.bitacora())


def _pagina_usuarios(request: Request, datos=None, errores=None, creado=""):
    return pagina(request, "usuarios.html", filas=administracion.usuarios(), roles=administracion.ROLES,
                  tipos_documento=administracion.TIPOS_DOCUMENTO, datos=datos or {}, errores=errores or {},
                  creado=creado)


@app.get("/usuarios", response_class=HTMLResponse)
def ver_usuarios(request: Request, creado: str = "", u: dict = Depends(requiere_admin)):
    return _pagina_usuarios(request, creado=creado)


@app.post("/usuarios", response_class=HTMLResponse)
async def crear_usuario(request: Request, u: dict = Depends(requiere_admin)):
    datos = await _datos_usuario(request)
    errores = administracion.validar_usuario(datos)
    if datos["rol"] not in administracion.ROLES:
        errores["rol"] = "Elija un rol."
    if errores:
        return _pagina_usuarios(request, datos, errores)
    administracion.crear_usuario(datos, datos["rol"])
    return RedirectResponse(f"/usuarios?creado={datos['usuario']}", status_code=303)


@app.post("/usuarios/{id_usuario}/{accion}")
def accion_usuario(id_usuario: int, accion: str, rol: str = Form(""), u: dict = Depends(requiere_admin)):
    if accion == "rol":
        administracion.cambiar_rol(id_usuario, rol)
    elif accion == "desbloquear":
        administracion.desbloquear(id_usuario)
    elif accion == "activo" and id_usuario != u["id"]:
        administracion.alternar_activo(id_usuario)
    return RedirectResponse("/usuarios", status_code=303)
