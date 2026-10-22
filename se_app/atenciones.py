"""Operacion diaria sobre se_transaccional: viviendas, atenciones,
respuestas, diagnosticos, citas e historial.

Toda consulta de un consultante filtra por su id_usuario a traves de la
vivienda, para que solo vea lo suyo (RF06, restriccion del historial).
"""
from . import db

BC = "se_base_conocimiento"

ZONAS = ["Cocina", "Baño", "Habitación", "Sala", "Comedor", "Fachada", "Patio", "Techo", "Garaje", "Otra"]


# ---------------------------------------------------------------- viviendas

def viviendas(id_usuario: int) -> list[dict]:
    return db.consultar(
        "SELECT v.*, COUNT(a.id_atencion) AS atenciones, MAX(a.fecha_inicio) AS ultima "
        "FROM vivienda v LEFT JOIN atencion a ON a.id_vivienda = v.id_vivienda "
        "WHERE v.id_usuario = %s AND v.activa = 1 "
        "GROUP BY v.id_vivienda ORDER BY v.id_vivienda", (id_usuario,))


def crear_vivienda(id_usuario: int, datos: dict) -> int:
    return db.ejecutar(
        "INSERT INTO vivienda (id_usuario, alias, direccion, ciudad, tipo_vivienda, antiguedad_anios) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (id_usuario, datos["alias"], datos["direccion"], datos["ciudad"],
         datos["tipo_vivienda"], datos.get("antiguedad_anios") or None))


# ---------------------------------------------------------------- atenciones

def crear_atencion(id_usuario: int, id_vivienda: int, codigo_categoria: str, zona: str) -> int:
    propia = db.consultar_uno("SELECT 1 AS ok FROM vivienda WHERE id_vivienda = %s AND id_usuario = %s",
                              (id_vivienda, id_usuario))
    if not propia:
        raise PermissionError("La vivienda no pertenece al usuario.")
    return db.ejecutar(
        f"INSERT INTO atencion (id_vivienda, id_categoria, zona_vivienda) "
        f"SELECT %s, id_categoria, %s FROM {BC}.categoria WHERE codigo = %s",
        (id_vivienda, zona, codigo_categoria))


def atencion(id_atencion: int, id_usuario: int) -> dict | None:
    """La atencion, solo si pertenece al usuario."""
    return db.consultar_uno(
        f"SELECT a.*, c.codigo AS categoria, c.nombre AS categoria_nombre, "
        f"       v.alias AS vivienda, v.direccion, v.ciudad "
        f"FROM atencion a "
        f"JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        f"JOIN {BC}.categoria c ON c.id_categoria = a.id_categoria "
        f"WHERE a.id_atencion = %s AND v.id_usuario = %s", (id_atencion, id_usuario))


def respuestas(id_atencion: int) -> list[tuple[str, int]]:
    """Memoria de trabajo de la atencion, en el orden en que se respondio."""
    filas = db.consultar(
        f"SELECT p.codigo, ar.respuesta FROM atencion_respuesta ar "
        f"JOIN {BC}.pregunta p ON p.id_pregunta = ar.id_pregunta "
        f"WHERE ar.id_atencion = %s ORDER BY ar.orden", (id_atencion,))
    return [(f["codigo"], int(f["respuesta"])) for f in filas]


def registrar_respuesta(id_atencion: int, codigo_pregunta: str, valor: int) -> None:
    db.ejecutar(
        f"INSERT INTO atencion_respuesta (id_atencion, id_pregunta, respuesta, orden) "
        f"SELECT %s, p.id_pregunta, %s, "
        f"       (SELECT COALESCE(MAX(orden), 0) + 1 FROM atencion_respuesta WHERE id_atencion = %s) "
        f"FROM {BC}.pregunta p WHERE p.codigo = %s",
        (id_atencion, valor, id_atencion, codigo_pregunta))


def deshacer_respuesta(id_atencion: int) -> None:
    """Borra la ultima respuesta (boton 'Anterior')."""
    db.ejecutar(
        "DELETE FROM atencion_respuesta WHERE id_atencion = %s ORDER BY orden DESC LIMIT 1", (id_atencion,))


def reiniciar(id_atencion: int) -> None:
    db.ejecutar("DELETE FROM atencion_respuesta WHERE id_atencion = %s", (id_atencion,))


def cerrar(id_atencion: int, hipotesis: dict | None) -> None:
    """Guarda el diagnostico como copia historica (RNF20) y cierra la atencion.

    hipotesis = None registra la conclusion por defecto (RNF22).
    """
    with db.conexion() as cnx:
        cur = cnx.cursor()
        cur.execute("DELETE FROM atencion_diagnostico WHERE id_atencion = %s", (id_atencion,))
        if hipotesis:
            cur.execute(
                "INSERT INTO atencion_diagnostico (id_atencion, id_hipotesis, diagnostico_texto, nivel_urgencia, "
                "  especialista_sugerido, accion_recomendada, factor_certeza) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (id_atencion, hipotesis["id_hipotesis"], hipotesis["diagnostico"], hipotesis["nivel_urgencia"],
                 hipotesis["especialista"], hipotesis["accion_recomendada"], hipotesis["factor_certeza"]))
            estado = "DIAGNOSTICADA"
        else:
            cur.execute(
                "INSERT INTO atencion_diagnostico (id_atencion, id_hipotesis, diagnostico_texto) "
                "VALUES (%s, NULL, 'Sin diagnóstico concluyente')", (id_atencion,))
            estado = "SIN_DIAGNOSTICO"
        cur.execute("UPDATE atencion SET estado = %s, fecha_fin = NOW() WHERE id_atencion = %s",
                    (estado, id_atencion))


def reabrir(id_atencion: int) -> None:
    """Permite corregir respuestas de una atencion ya cerrada."""
    with db.conexion() as cnx:
        cur = cnx.cursor()
        cur.execute("DELETE FROM atencion_diagnostico WHERE id_atencion = %s", (id_atencion,))
        cur.execute("UPDATE atencion SET estado = 'EN_CURSO', fecha_fin = NULL WHERE id_atencion = %s",
                    (id_atencion,))


def diagnostico(id_atencion: int) -> dict | None:
    return db.consultar_uno(
        f"SELECT d.*, h.codigo AS codigo_hipotesis, h.validada, h.fuente "
        f"FROM atencion_diagnostico d LEFT JOIN {BC}.hipotesis h ON h.id_hipotesis = d.id_hipotesis "
        f"WHERE d.id_atencion = %s", (id_atencion,))


# ---------------------------------------------------------------- citas

def crear_cita(id_atencion: int, id_usuario: int, fecha: str, observaciones: str | None) -> int:
    d = db.consultar_uno(
        "SELECT d.id_diagnostico, d.especialista_sugerido FROM atencion_diagnostico d "
        "JOIN atencion a ON a.id_atencion = d.id_atencion "
        "JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "WHERE d.id_atencion = %s AND v.id_usuario = %s AND d.id_hipotesis IS NOT NULL",
        (id_atencion, id_usuario))
    if not d:
        raise PermissionError("Solo se agenda a partir de un diagnóstico concluyente propio.")
    return db.ejecutar(
        "INSERT INTO cita (id_diagnostico, tipo_especialista, fecha_programada, observaciones) "
        "VALUES (%s, %s, %s, %s)", (d["id_diagnostico"], d["especialista_sugerido"], fecha, observaciones or None))


def citas(id_usuario: int, id_atencion: int | None = None) -> list[dict]:
    filtro, params = "", [id_usuario]
    if id_atencion:
        filtro, params = " AND a.id_atencion = %s", [id_usuario, id_atencion]
    return db.consultar(
        "SELECT ci.*, d.diagnostico_texto, d.nivel_urgencia, a.id_atencion, a.zona_vivienda, v.alias AS vivienda "
        "FROM cita ci JOIN atencion_diagnostico d ON d.id_diagnostico = ci.id_diagnostico "
        "JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "WHERE v.id_usuario = %s" + filtro + " ORDER BY ci.fecha_programada", tuple(params))


def cancelar_cita(id_cita: int, id_usuario: int) -> None:
    db.ejecutar(
        "UPDATE cita ci JOIN atencion_diagnostico d ON d.id_diagnostico = ci.id_diagnostico "
        "JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "SET ci.estado = 'CANCELADA' WHERE ci.id_cita = %s AND v.id_usuario = %s", (id_cita, id_usuario))


# ---------------------------------------------------------------- historial

def historial(id_usuario: int, categoria: str = "", zona: str = "", limite: int = 200) -> list[dict]:
    """Atenciones cerradas del usuario, de la mas reciente a la mas antigua (RF06)."""
    sql = (f"SELECT a.id_atencion, a.fecha_inicio, a.zona_vivienda, a.estado, c.codigo AS categoria, "
           f"       c.nombre AS categoria_nombre, v.alias AS vivienda, d.diagnostico_texto, d.nivel_urgencia, "
           f"       d.factor_certeza "
           f"FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
           f"JOIN {BC}.categoria c ON c.id_categoria = a.id_categoria "
           f"LEFT JOIN atencion_diagnostico d ON d.id_atencion = a.id_atencion "
           f"WHERE v.id_usuario = %s AND a.estado IN ('DIAGNOSTICADA', 'SIN_DIAGNOSTICO')")
    params = [id_usuario]
    if categoria:
        sql += " AND c.codigo = %s"
        params.append(categoria)
    if zona:
        sql += " AND a.zona_vivienda = %s"
        params.append(zona)
    sql += " ORDER BY a.fecha_inicio DESC LIMIT %s"
    params.append(limite)
    return db.consultar(sql, tuple(params))


def recurrentes(id_usuario: int) -> list[dict]:
    """Categorias que se repiten en una misma vivienda en los ultimos 90 dias (RF03)."""
    return db.consultar(
        f"SELECT v.alias AS vivienda, c.nombre AS categoria, COUNT(*) AS veces "
        f"FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        f"JOIN {BC}.categoria c ON c.id_categoria = a.id_categoria "
        f"WHERE v.id_usuario = %s AND a.estado = 'DIAGNOSTICADA' "
        f"  AND a.fecha_inicio >= NOW() - INTERVAL 90 DAY "
        f"GROUP BY v.id_vivienda, c.id_categoria HAVING COUNT(*) >= 2", (id_usuario,))


def indicadores(id_usuario: int) -> dict:
    return db.consultar_uno(
        "SELECT "
        " (SELECT COUNT(*) FROM atencion a JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "   WHERE v.id_usuario = %s AND a.estado <> 'EN_CURSO' "
        "   AND a.fecha_inicio >= DATE_FORMAT(NOW(), '%%Y-%%m-01')) AS mes, "
        " (SELECT COUNT(*) FROM atencion_diagnostico d JOIN atencion a ON a.id_atencion = d.id_atencion "
        "   JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "   WHERE v.id_usuario = %s AND d.nivel_urgencia = 'Critica') AS criticas, "
        " (SELECT COUNT(*) FROM cita ci JOIN atencion_diagnostico d ON d.id_diagnostico = ci.id_diagnostico "
        "   JOIN atencion a ON a.id_atencion = d.id_atencion JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "   WHERE v.id_usuario = %s AND ci.estado IN ('PROGRAMADA', 'CONFIRMADA') "
        "   AND ci.fecha_programada >= NOW()) AS citas, "
        " (SELECT AVG(TIMESTAMPDIFF(SECOND, a.fecha_inicio, a.fecha_fin)) FROM atencion a "
        "   JOIN vivienda v ON v.id_vivienda = a.id_vivienda "
        "   WHERE v.id_usuario = %s AND a.fecha_fin IS NOT NULL) AS segundos",
        (id_usuario, id_usuario, id_usuario, id_usuario)) or {}
