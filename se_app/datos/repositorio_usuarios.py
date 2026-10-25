"""Acceso a los usuarios del sistema (tabla usuario)."""
from .conexion import BaseDatos


class RepositorioUsuarios:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def por_usuario(self, usuario: str) -> dict | None:
        return self.bd.consultar_uno(
            "SELECT id_usuario, rol, nombres, apellidos, usuario, contrasena_hash, intentos_fallidos, "
            "       bloqueado_hasta, activo FROM usuario WHERE usuario = %s", (usuario,))

    def registrar_intento_fallido(self, id_usuario: int, intentos: int) -> None:
        self.bd.ejecutar("UPDATE usuario SET intentos_fallidos = %s WHERE id_usuario = %s", (intentos, id_usuario))

    def bloquear(self, id_usuario: int, hasta) -> None:
        self.bd.ejecutar("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = %s WHERE id_usuario = %s",
                         (hasta, id_usuario))

    def desbloquear(self, id_usuario: int) -> None:
        self.bd.ejecutar("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = %s",
                         (id_usuario,))

    def existe(self, campo: str, valor: str, tipo_documento: str | None = None) -> bool:
        """Comprueba los mismos indices UNIQUE de la tabla: usuario, correo o documento."""
        if campo == "numero_documento":
            return bool(self.bd.consultar_uno(
                "SELECT 1 AS x FROM usuario WHERE tipo_documento = %s AND numero_documento = %s", (tipo_documento, valor)))
        columna = {"usuario": "usuario", "correo": "correo"}[campo]
        return bool(self.bd.consultar_uno(f"SELECT 1 AS x FROM usuario WHERE {columna} = %s", (valor,)))

    def crear(self, datos: dict, rol: str, contrasena_hash: str) -> int:
        return self.bd.ejecutar(
            "INSERT INTO usuario (rol, tipo_documento, numero_documento, nombres, apellidos, correo, telefono, "
            "usuario, contrasena_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (rol, datos["tipo_documento"], datos["numero_documento"], datos["nombres"], datos["apellidos"],
             datos["correo"].lower(), datos.get("telefono") or None, datos["usuario"], contrasena_hash))

    def actualizar_contrasena(self, id_usuario: int, contrasena_hash: str) -> None:
        self.bd.ejecutar("UPDATE usuario SET contrasena_hash = %s, intentos_fallidos = 0, bloqueado_hasta = NULL, "
                         "activo = 1 WHERE id_usuario = %s", (contrasena_hash, id_usuario))

    def listar(self) -> list[dict]:
        return self.bd.consultar(
            "SELECT id_usuario, rol, tipo_documento, numero_documento, nombres, apellidos, correo, telefono, "
            "       usuario, activo, bloqueado_hasta, intentos_fallidos, fecha_registro, bloqueado_hasta > NOW() AS bloqueado "
            "FROM usuario ORDER BY rol, usuario")

    def cambiar_rol(self, id_usuario: int, rol: str) -> None:
        self.bd.ejecutar("UPDATE usuario SET rol = %s WHERE id_usuario = %s", (rol, id_usuario))

    def alternar_activo(self, id_usuario: int) -> None:
        self.bd.ejecutar("UPDATE usuario SET activo = 1 - activo WHERE id_usuario = %s", (id_usuario,))

    def tiene_vivienda(self, id_usuario: int) -> bool:
        return bool(self.bd.consultar_uno("SELECT 1 AS ok FROM vivienda WHERE id_usuario = %s", (id_usuario,)))
