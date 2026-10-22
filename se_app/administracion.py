"""Gestion de usuarios y consulta de la bitacora (CU10, CU11)."""
import re

from . import db, seguridad

ROLES = ("CONSULTANTE", "EXPERTO", "ADMINISTRADOR")
TIPOS_DOCUMENTO = (("CC", "Cédula de ciudadanía"), ("CE", "Cédula de extranjería"),
                   ("TI", "Tarjeta de identidad"), ("PAS", "Pasaporte"))
MIN_CONTRASENA = 8


def validar_usuario(d: dict) -> dict:
    """Devuelve {campo: mensaje} con los errores del formulario de registro."""
    errores = {}
    for campo, nombre in (("nombres", "los nombres"), ("apellidos", "los apellidos"),
                          ("numero_documento", "el número de documento"), ("correo", "el correo"),
                          ("usuario", "el usuario")):
        if not d.get(campo):
            errores[campo] = f"Escriba {nombre}."
    if d.get("tipo_documento") not in dict(TIPOS_DOCUMENTO):
        errores["tipo_documento"] = "Elija un tipo de documento."
    if d.get("numero_documento") and not re.fullmatch(r"[A-Za-z0-9]{4,20}", d["numero_documento"]):
        errores["numero_documento"] = "Use entre 4 y 20 letras o números, sin puntos ni espacios."
    if d.get("correo") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", d["correo"]):
        errores["correo"] = "El correo no tiene un formato válido."
    if d.get("usuario") and not re.fullmatch(r"[a-zA-Z0-9._-]{3,40}", d["usuario"]):
        errores["usuario"] = "Use entre 3 y 40 letras, números, punto, guion o guion bajo."
    if d.get("telefono") and not re.fullmatch(r"[0-9 +()-]{7,20}", d["telefono"]):
        errores["telefono"] = "El teléfono no es válido."
    if len(d.get("contrasena", "")) < MIN_CONTRASENA:
        errores["contrasena"] = f"La contraseña debe tener al menos {MIN_CONTRASENA} caracteres."
    elif d.get("contrasena") != d.get("confirmacion"):
        errores["confirmacion"] = "Las contraseñas no coinciden."

    # Unicidad (los mismos indices UNIQUE de la tabla usuario).
    if not errores.get("usuario") and db.consultar_uno("SELECT 1 AS x FROM usuario WHERE usuario = %s", (d["usuario"],)):
        errores["usuario"] = "Ese nombre de usuario ya está en uso."
    if not errores.get("correo") and db.consultar_uno("SELECT 1 AS x FROM usuario WHERE correo = %s", (d["correo"],)):
        errores["correo"] = "Ya existe una cuenta con ese correo."
    if not errores.get("numero_documento") and db.consultar_uno(
            "SELECT 1 AS x FROM usuario WHERE tipo_documento = %s AND numero_documento = %s",
            (d.get("tipo_documento"), d["numero_documento"])):
        errores["numero_documento"] = "Ya existe una cuenta con ese documento."
    return errores


def crear_usuario(d: dict, rol: str = "CONSULTANTE") -> int:
    """Crea el usuario con la contrasena cifrada (RNF02). Validar antes con validar_usuario."""
    if rol not in ROLES:
        raise ValueError("Rol no válido")
    return db.ejecutar(
        "INSERT INTO usuario (rol, tipo_documento, numero_documento, nombres, apellidos, correo, telefono, "
        "usuario, contrasena_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (rol, d["tipo_documento"], d["numero_documento"], d["nombres"], d["apellidos"], d["correo"].lower(),
         d.get("telefono") or None, d["usuario"], seguridad.cifrar(d["contrasena"])))


def usuarios() -> list[dict]:
    return db.consultar(
        "SELECT id_usuario, rol, tipo_documento, numero_documento, nombres, apellidos, correo, telefono, "
        "       usuario, activo, bloqueado_hasta, "
        "       intentos_fallidos, fecha_registro, bloqueado_hasta > NOW() AS bloqueado "
        "FROM usuario ORDER BY rol, usuario")


def cambiar_rol(id_usuario: int, rol: str) -> None:
    if rol not in ROLES:
        raise ValueError("Rol no válido")
    db.ejecutar("UPDATE usuario SET rol = %s WHERE id_usuario = %s", (rol, id_usuario))


def desbloquear(id_usuario: int) -> None:
    db.ejecutar("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = %s",
                (id_usuario,))


def alternar_activo(id_usuario: int) -> None:
    db.ejecutar("UPDATE usuario SET activo = 1 - activo WHERE id_usuario = %s", (id_usuario,))


def bitacora(limite: int = 200) -> list[dict]:
    return db.consultar(
        "SELECT b.*, u.usuario, u.nombres, u.apellidos FROM bitacora_conocimiento b "
        "JOIN usuario u ON u.id_usuario = b.id_usuario ORDER BY b.fecha_cambio DESC LIMIT %s", (limite,))


def ultimos_cambios(limite: int = 5) -> list[dict]:
    return bitacora(limite)
