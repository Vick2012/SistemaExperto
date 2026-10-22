"""Lectura y mantenimiento de la base de conocimiento (se_base_conocimiento).

Este modulo solo habla con MySQL. El razonamiento lo hace el motor en
Prolog (motor.py), que recibe lo que aqui se lee.
"""
from . import db

BC = "se_base_conocimiento"


def leer_base() -> dict:
    """Base de conocimiento activa, lista para cargar en el motor."""
    categorias = db.consultar(
        f"SELECT id_categoria, codigo, nombre, descripcion FROM {BC}.categoria "
        "WHERE activa = 1 ORDER BY orden")
    preguntas = db.consultar(
        f"SELECT p.id_pregunta, p.codigo, c.codigo AS categoria, p.texto_pregunta, "
        f"       p.enunciado_positivo, p.enunciado_negativo "
        f"FROM {BC}.pregunta p JOIN {BC}.categoria c ON c.id_categoria = p.id_categoria "
        f"WHERE p.activa = 1")
    hipotesis = db.consultar(
        f"SELECT h.id_hipotesis, h.codigo, c.codigo AS categoria, h.diagnostico, h.nivel_urgencia, "
        f"       h.factor_certeza, h.especialista, h.accion_recomendada, h.fuente, h.validada "
        f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
        f"WHERE h.activa = 1")
    condiciones = db.consultar(
        f"SELECT h.codigo AS hipotesis, p.codigo AS pregunta, r.valor_respuesta, r.orden "
        f"FROM {BC}.respuesta r "
        f"JOIN {BC}.hipotesis h ON h.id_hipotesis = r.id_hipotesis "
        f"JOIN {BC}.pregunta  p ON p.id_pregunta  = r.id_pregunta "
        f"WHERE h.activa = 1")
    return {"categorias": categorias, "preguntas": preguntas,
            "hipotesis": hipotesis, "condiciones": condiciones}


def resumen() -> dict:
    fila = db.consultar_uno(
        f"SELECT (SELECT COUNT(*) FROM {BC}.pregunta  WHERE activa = 1) AS preguntas, "
        f"       (SELECT COUNT(*) FROM {BC}.hipotesis WHERE activa = 1) AS hipotesis, "
        f"       (SELECT COUNT(*) FROM {BC}.hipotesis WHERE activa = 1 AND validada = 0) AS pendientes, "
        f"       (SELECT COUNT(*) FROM {BC}.hipotesis WHERE activa = 1 AND nivel_urgencia = 'Critica') AS criticas")
    return fila or {}


def hipotesis_de_categoria(codigo_categoria: str) -> list[dict]:
    """Todas las hipotesis de la categoria, activas o no, con su numero de condiciones."""
    return db.consultar(
        f"SELECT h.id_hipotesis, h.codigo, h.diagnostico, h.nivel_urgencia, h.factor_certeza, "
        f"       h.especialista, h.accion_recomendada, h.fuente, h.validada, h.activa, "
        f"       COUNT(r.id_respuesta) AS condiciones "
        f"FROM {BC}.hipotesis h "
        f"JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
        f"LEFT JOIN {BC}.respuesta r ON r.id_hipotesis = h.id_hipotesis "
        f"WHERE c.codigo = %s "
        f"GROUP BY h.id_hipotesis ORDER BY h.codigo", (codigo_categoria,))


def hipotesis_por_codigo(codigo: str) -> dict | None:
    return db.consultar_uno(
        f"SELECT h.*, c.codigo AS categoria, c.nombre AS categoria_nombre "
        f"FROM {BC}.hipotesis h JOIN {BC}.categoria c ON c.id_categoria = h.id_categoria "
        f"WHERE h.codigo = %s", (codigo,))


def granulo(codigo: str) -> list[dict]:
    """Condiciones If/And de una hipotesis, en orden."""
    return db.consultar(
        f"SELECT r.orden, r.valor_respuesta, p.codigo, p.texto_pregunta, "
        f"       IF(r.valor_respuesta = 1, p.enunciado_positivo, p.enunciado_negativo) AS enunciado "
        f"FROM {BC}.respuesta r "
        f"JOIN {BC}.hipotesis h ON h.id_hipotesis = r.id_hipotesis "
        f"JOIN {BC}.pregunta  p ON p.id_pregunta  = r.id_pregunta "
        f"WHERE h.codigo = %s ORDER BY r.orden", (codigo,))


# Campos que el experto puede editar desde el panel (CU08, CU09).
CAMPOS_EDITABLES = ("diagnostico", "nivel_urgencia", "factor_certeza", "especialista",
                    "accion_recomendada", "validada", "activa")


def actualizar_hipotesis(codigo: str, cambios: dict, id_usuario: int) -> list[str]:
    """Aplica los cambios y registra cada uno en la bitacora (RF07, RNF04).

    Devuelve la lista de campos que cambiaron.
    """
    actual = hipotesis_por_codigo(codigo)
    if actual is None:
        raise ValueError(f"No existe la hipotesis {codigo}")
    distintos = {k: v for k, v in cambios.items()
                 if k in CAMPOS_EDITABLES and str(actual[k]) != str(v)}
    if not distintos:
        return []

    with db.conexion() as cnx:
        cur = cnx.cursor()
        asignaciones = ", ".join(f"{k} = %s" for k in distintos)
        cur.execute(f"UPDATE {BC}.hipotesis SET {asignaciones} WHERE codigo = %s",
                    (*distintos.values(), codigo))
        for campo, nuevo in distintos.items():
            if campo == "activa":
                accion = "ACTIVAR" if int(nuevo) else "DESACTIVAR"
            else:
                accion = "MODIFICAR"
            detalle = f"{campo}: {actual[campo]} -> {nuevo}"[:500]
            cur.execute(
                "INSERT INTO bitacora_conocimiento (id_usuario, tabla_afectada, codigo_registro, accion, detalle) "
                "VALUES (%s, 'hipotesis', %s, %s, %s)", (id_usuario, codigo, accion, detalle))
    return list(distintos)
