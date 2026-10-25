"""Genera las capturas de pantalla para la documentacion del proyecto.

Toma dos grupos de imagenes en ../mockups/capturas/:
  prototipos/  las tres direcciones visuales (A, B y C) con datos de ejemplo
  aplicacion/  la aplicacion real, con los tres roles

Usa Playwright con el Microsoft Edge instalado (no descarga navegadores).
Requiere MySQL encendido y la aplicacion corriendo.

Uso (desde la carpeta aplicacion):
    .venv\\Scripts\\python -m scripts.capturas [--url http://127.0.0.1:8000]

La primera vez agrega al usuario 'consulta' unos diagnosticos de ejemplo
(electrico, hidraulico y humedad) para que el tablero y el historial no
salgan vacios. Las atenciones que crea solo para fotografiar una
pregunta o un reporte se borran al final.
"""
import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.semilla import contrasena_de_prueba  # noqa: E402
from se_app.contenedor import contenedor  # noqa: E402

db = contenedor.bd

PROYECTO = Path(__file__).resolve().parents[2]
PROTOTIPOS = PROYECTO / "mockups" / "prototipos"
SALIDA = PROYECTO / "mockups" / "capturas"
ESCRITORIO = {"width": 1440, "height": 900}
MOVIL = {"width": 390, "height": 844}

# Diagnosticos de ejemplo: (categoria, zona, regla a la que se llega)
DEMO = [("ELE", "Habitación", "E01"), ("HID", "Baño", "H08"), ("HUM", "Habitación", "M05"), ("HUM", "Sala", "M05")]


def foto(page, carpeta, nombre, completa=False):
    page.wait_for_timeout(450)          # deja terminar la animacion de entrada
    ruta = SALIDA / carpeta / f"{nombre}.png"
    page.screenshot(path=str(ruta), full_page=completa)
    print("  ", ruta.relative_to(PROYECTO))


# ------------------------------------------------------------------ prototipos

def prototipos(navegador):
    print("Prototipos")
    url = lambda archivo: (PROTOTIPOS / archivo).as_uri()

    pagina = navegador.new_page(viewport=ESCRITORIO)
    pagina.goto(url("index.html"))
    foto(pagina, "prototipos", "00-indice-direcciones")
    pagina.close()

    # A · Guia paso a paso: pensada para celular.
    a = navegador.new_page(viewport=MOVIL, device_scale_factor=2)
    a.goto(url("a-guia.html"))
    for n, (pantalla, guion) in enumerate([
            ("inicio", ""), ("nuevo", ""), ("pregunta", "S.resp={};"), ("critica", "S.resp={olor_quemado:1,sobrecalentamiento:1};S.fin=SE.hipotesis.E05;"),
            ("resultado", "S.resp={olor_quemado:1,sobrecalentamiento:1};S.fin=SE.hipotesis.E05;"), ("historial", ""), ("experto", "")], 1):
        a.evaluate(f"{guion} ir('{pantalla}')")
        foto(a, "prototipos", f"A{n:02d}-guia-{pantalla}")
    a.close()

    # B · Centro de diagnostico: la direccion elegida, con los dos roles.
    b = navegador.new_page(viewport=ESCRITORIO)
    b.goto(url("b-centro.html"))
    pasos_b = [
        ("login", "", "ir('login')"),
        ("tablero", "", "ir('inicio')"),
        ("pregunta-consultante", "S.rol='CONSULTANTE';S.resp={olor_quemado:1};", "ir('diagnostico')"),
        ("pregunta-experto-razonamiento", "S.rol='EXPERTO';S.resp={olor_quemado:1};", "ir('diagnostico')"),
        ("reporte-consultante-alerta", "S.rol='CONSULTANTE';S.resp={olor_quemado:1,sobrecalentamiento:1};S.fin=SE.hipotesis.E05;", "ir('resultado');S.alerta=true;render()"),
        ("reporte-experto-regla", "S.rol='EXPERTO';", "ir('resultado');S.alerta=true;render()"),
        ("historial", "", "ir('historial')"),
        ("base-conocimiento", "S.rol='EXPERTO';", "ir('experto')"),
    ]
    for n, (nombre, estado, accion) in enumerate(pasos_b, 1):
        b.evaluate(estado + accion)
        foto(b, "prototipos", f"B{n:02d}-centro-{nombre}")
    b.close()

    # C · Plano de la casa.
    c = navegador.new_page(viewport=ESCRITORIO)
    c.goto(url("c-plano.html"))
    pasos_c = [
        ("login", "ir('login')"),
        ("plano-zonas", "ir('inicio')"),
        ("inspeccion", "S.resp={};ir('inspeccion');responder('olor_quemado',1)"),
        ("ficha-alerta", "S.resp={olor_quemado:1,sobrecalentamiento:1};S.fin=SE.hipotesis.E05;S.pantalla='resultado';S.modal=true;render()"),
        ("ficha", "S.modal=false;render()"),
        ("linea-de-tiempo", "ir('historial')"),
        ("arbol-experto", "ir('experto')"),
    ]
    for n, (nombre, accion) in enumerate(pasos_c, 1):
        c.evaluate(accion)
        foto(c, "prototipos", f"C{n:02d}-plano-{nombre}")
    c.close()


# ------------------------------------------------------------------ aplicacion

def ingresar(pagina, base, usuario, clave):
    pagina.goto(f"{base}/salir")
    pagina.fill("#usuario", usuario)
    pagina.fill("#contrasena", clave)
    pagina.click("button:has-text('Ingresar')")
    pagina.wait_for_url(f"{base}/")


def nueva_atencion(pagina, base, categoria, zona) -> int:
    """Abre una atencion en la primera vivienda del usuario y devuelve su id."""
    return pagina.evaluate("""async ([cat, zona]) => {
        const t = await (await fetch('/diagnostico/nuevo')).text();
        const f = new FormData();
        f.append('id_vivienda', t.match(/name="id_vivienda" value="(\\d+)"/)[1]);
        f.append('zona', zona); f.append('categoria', cat);
        const r = await fetch('/diagnostico', {method: 'POST', body: f});
        return Number(r.url.split('/').pop());
    }""", [categoria, zona])


def responder_hasta(pagina, id_atencion, respuestas: dict, maximo=40):
    """Responde lo que el motor pregunte (1 o 0 segun 'respuestas', 0 si no esta)."""
    for _ in range(maximo):
        html = pagina.evaluate(f"async () => (await fetch('/diagnostico/{id_atencion}')).text()")
        m = re.search(r'name="pregunta" value="([^"]+)"', html)
        if not m:
            return
        valor = respuestas.get(m.group(1), 0)
        pagina.evaluate("""async ([id, p, v]) => { const f = new FormData(); f.append('pregunta', p); f.append('valor', v);
            await fetch(`/diagnostico/${id}/responder`, {method: 'POST', body: f}); }""", [id_atencion, m.group(1), str(valor)])


def datos_demo(pagina, base):
    """Agrega diagnosticos de ejemplo al consultante, una sola vez."""
    cerradas = db.consultar_uno(
        "SELECT COUNT(*) AS n FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "JOIN usuario u ON u.id_usuario = v.id_usuario WHERE u.usuario = 'consulta' AND a.estado <> 'EN_CURSO'")["n"]
    if cerradas >= 6:
        return
    print("  agregando diagnosticos de ejemplo al usuario consulta")
    reglas = {}
    for c in contenedor.repo_conocimiento.leer_base()["condiciones"]:
        reglas.setdefault(c["hipotesis"], {})[c["pregunta"]] = c["valor_respuesta"]
    for categoria, zona, regla in DEMO:
        id_atencion = nueva_atencion(pagina, base, categoria, zona)
        responder_hasta(pagina, id_atencion, reglas[regla])
    # Una cita para que la pantalla de citas tenga contenido.
    ultima = db.consultar_uno(
        "SELECT a.id_atencion FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "JOIN usuario u ON u.id_usuario = v.id_usuario JOIN atencion_diagnostico d ON d.id_atencion = a.id_atencion "
        "WHERE u.usuario = 'consulta' AND d.id_hipotesis IS NOT NULL ORDER BY a.id_atencion DESC LIMIT 1")
    pagina.evaluate("""async (id) => { const f = new FormData(); f.append('fecha', '2026-11-05T09:00'); f.append('observaciones', 'Llamar antes de llegar');
        await fetch(`/diagnostico/${id}/cita`, {method: 'POST', body: f}); }""", ultima["id_atencion"])


def aplicacion(navegador, base, clave):
    print("Aplicacion")
    temporales = []
    p = navegador.new_page(viewport=ESCRITORIO)

    # Publico
    p.goto(f"{base}/salir")
    foto(p, "aplicacion", "01-login")
    p.goto(f"{base}/registro")
    foto(p, "aplicacion", "02-registro", completa=True)
    p.fill("#f-nombres", "Ana"); p.fill("#f-apellidos", "Ejemplo"); p.fill("#f-numero_documento", "12")
    p.fill("#f-correo", "ana@"); p.fill("#f-usuario", "consulta"); p.fill("#f-contrasena", "corta"); p.fill("#f-confirmacion", "otra")
    p.click("button:has-text('Crear cuenta')")
    foto(p, "aplicacion", "03-registro-validaciones", completa=True)

    # Consultante
    ingresar(p, base, "consulta", clave)
    datos_demo(p, base)
    p.goto(f"{base}/")
    foto(p, "aplicacion", "04-consultante-tablero", completa=True)
    p.goto(f"{base}/viviendas")
    foto(p, "aplicacion", "05-consultante-viviendas")
    p.goto(f"{base}/diagnostico/nuevo?categoria=ELE")
    foto(p, "aplicacion", "06-consultante-nuevo-diagnostico", completa=True)
    id_ele = nueva_atencion(p, base, "ELE", "Cocina")
    temporales.append(id_ele)
    p.goto(f"{base}/diagnostico/{id_ele}")
    foto(p, "aplicacion", "07-consultante-primera-pregunta")
    responder_hasta(p, id_ele, {"olor_quemado": 1}, maximo=1)
    p.goto(f"{base}/diagnostico/{id_ele}")
    p.click("summary:has-text('Por qué')")
    foto(p, "aplicacion", "08-consultante-pregunta-con-explicacion")
    # Diagnosticos recien calculados por el motor bayesiano (se borran al final):
    # uno critico de gas, uno hidraulico y uno sin sintomas (conclusion por defecto).
    reglas = {}
    for c in contenedor.repo_conocimiento.leer_base()["condiciones"]:
        reglas.setdefault(c["hipotesis"], {})[c["pregunta"]] = c["valor_respuesta"]
    critica = nueva_atencion(p, base, "GAS", "Cocina")
    alta = nueva_atencion(p, base, "HID", "Baño")
    defecto = nueva_atencion(p, base, "CAC", "Sala")
    temporales.extend([critica, alta, defecto])
    responder_hasta(p, critica, reglas["G04"])
    responder_hasta(p, alta, reglas["H08"])
    responder_hasta(p, defecto, {})
    p.goto(f"{base}/diagnostico/{critica}/reporte")
    foto(p, "aplicacion", "09-consultante-reporte-alerta-critica", completa=True)
    p.goto(f"{base}/diagnostico/{alta}/reporte")
    foto(p, "aplicacion", "10-consultante-reporte", completa=True)
    p.goto(f"{base}/diagnostico/{defecto}/reporte")
    foto(p, "aplicacion", "11-consultante-sin-diagnostico", completa=True)
    p.goto(f"{base}/historial")
    foto(p, "aplicacion", "12-consultante-historial", completa=True)
    p.goto(f"{base}/citas")
    foto(p, "aplicacion", "13-consultante-citas")
    p.goto(f"{base}/conocimiento")
    foto(p, "aplicacion", "14-consultante-acceso-restringido")

    # Celular (consultante)
    m = navegador.new_page(viewport=MOVIL, device_scale_factor=2)
    m.context.add_cookies(p.context.cookies())
    m.goto(f"{base}/")
    foto(m, "aplicacion", "15-movil-tablero")
    m.goto(f"{base}/diagnostico/{id_ele}")
    foto(m, "aplicacion", "16-movil-pregunta")
    m.goto(f"{base}/diagnostico/{critica}/reporte")
    foto(m, "aplicacion", "17-movil-reporte-alerta")
    m.close()

    # Experto
    ingresar(p, base, "experto", clave)
    p.goto(f"{base}/")
    foto(p, "aplicacion", "18-experto-tablero", completa=True)
    id_exp = nueva_atencion(p, base, "ELE", "Cocina")
    temporales.append(id_exp)
    responder_hasta(p, id_exp, {"olor_quemado": 1}, maximo=1)
    p.goto(f"{base}/diagnostico/{id_exp}")
    foto(p, "aplicacion", "19-experto-pregunta-inferencia-bayesiana")
    responder_hasta(p, id_exp, {"olor_quemado": 1, "sobrecalentamiento": 1})
    p.goto(f"{base}/diagnostico/{id_exp}/reporte")
    foto(p, "aplicacion", "20-experto-reporte-hipotesis-ponderadas", completa=True)
    p.goto(f"{base}/conocimiento?categoria=ELE&hipotesis=E05")
    foto(p, "aplicacion", "21-experto-base-conocimiento", completa=True)
    # El arbol se muestra completo, sin el limite de alto de su area de desplazamiento.
    for numero, categoria, nombre in (("22", "ELE", "electrica"), ("23", "GAS", "gas")):
        p.goto(f"{base}/arbol?categoria={categoria}")
        p.evaluate("document.getElementById('lienzo').style.maxHeight = 'none'")
        foto(p, "aplicacion", f"{numero}-experto-arbol-{nombre}", completa=True)

    # Administrador
    ingresar(p, base, "admin", clave)
    p.goto(f"{base}/usuarios")
    foto(p, "aplicacion", "24-admin-usuarios")
    p.click("button:has-text('Nuevo usuario')")
    foto(p, "aplicacion", "25-admin-nuevo-usuario")
    p.goto(f"{base}/bitacora")
    foto(p, "aplicacion", "26-admin-bitacora")
    p.close()

    # Las atenciones creadas solo para fotografiar se borran (con sus respuestas y diagnostico).
    for id_atencion in temporales:
        db.ejecutar("DELETE FROM atencion WHERE id_atencion = %s", (id_atencion,))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--solo", choices=["prototipos", "aplicacion"])
    args = parser.parse_args()
    for carpeta in ("prototipos", "aplicacion"):
        (SALIDA / carpeta).mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(channel="msedge")
        if args.solo != "aplicacion":
            prototipos(navegador)
        if args.solo != "prototipos":
            aplicacion(navegador, args.url.rstrip("/"), contrasena_de_prueba())
        navegador.close()


if __name__ == "__main__":
    main()
