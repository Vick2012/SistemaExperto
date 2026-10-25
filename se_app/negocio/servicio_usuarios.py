"""Casos de uso CU01 y CU10: autenticacion, registro y gestion de usuarios (RF01, RNF01, RNF02)."""
import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from .. import config
from .errores import ErrorAcceso, ErrorValidacion


class ServicioUsuarios:
    ROLES = ("CONSULTANTE", "EXPERTO", "ADMINISTRADOR")
    ROLES_EXPERTO = ("EXPERTO", "ADMINISTRADOR")
    TIPOS_DOCUMENTO = (("CC", "Cédula de ciudadanía"), ("CE", "Cédula de extranjería"),
                       ("TI", "Tarjeta de identidad"), ("PAS", "Pasaporte"))
    MIN_CONTRASENA = 8
    _N, _R, _P = 2 ** 14, 8, 1        # parametros de scrypt

    def __init__(self, usuarios):
        # usuarios: RepositorioUsuarios (capa de datos).
        self.usuarios = usuarios

    # ------------------------------------------------------------ contrasenas (RNF02)

    @classmethod
    def cifrar(cls, contrasena: str) -> str:
        """Resumen scrypt con sal aleatoria; nunca se guarda la contrasena en texto plano."""
        sal = secrets.token_bytes(16)
        resumen = hashlib.scrypt(contrasena.encode(), salt=sal, n=cls._N, r=cls._R, p=cls._P)
        return "scrypt${}${}${}${}${}".format(cls._N, cls._R, cls._P, base64.b64encode(sal).decode(),
                                              base64.b64encode(resumen).decode())

    @staticmethod
    def verificar(contrasena: str, almacenado: str) -> bool:
        try:
            esquema, n, r, p, sal, resumen = almacenado.split("$")
        except ValueError:
            return False          # resumenes de ejemplo del script 04 u otro formato
        if esquema != "scrypt":
            return False
        calculado = hashlib.scrypt(contrasena.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(calculado, base64.b64decode(resumen))

    @classmethod
    def es_experto(cls, usuario: dict) -> bool:
        return usuario["rol"] in cls.ROLES_EXPERTO

    # ------------------------------------------------------------ autenticacion (RF01)

    def autenticar(self, usuario: str, contrasena: str) -> dict:
        """Valida las credenciales y bloquea la cuenta tras MAX_INTENTOS intentos fallidos."""
        fila = self.usuarios.por_usuario(usuario)
        if fila is None or not fila["activo"]:
            raise ErrorAcceso("Usuario o contraseña incorrectos.")
        ahora = datetime.now()
        if fila["bloqueado_hasta"] and fila["bloqueado_hasta"] > ahora:
            minutos = int((fila["bloqueado_hasta"] - ahora).total_seconds() // 60) + 1
            raise ErrorAcceso(f"Cuenta bloqueada por intentos fallidos. Intente de nuevo en {minutos} min.")
        if not self.verificar(contrasena, fila["contrasena_hash"]):
            intentos = fila["intentos_fallidos"] + 1
            if intentos >= config.MAX_INTENTOS:
                self.usuarios.bloquear(fila["id_usuario"], ahora + timedelta(minutes=config.MINUTOS_BLOQUEO))
                raise ErrorAcceso(f"Demasiados intentos fallidos. La cuenta queda bloqueada {config.MINUTOS_BLOQUEO} min.")
            self.usuarios.registrar_intento_fallido(fila["id_usuario"], intentos)
            raise ErrorAcceso(f"Usuario o contraseña incorrectos. Le quedan {config.MAX_INTENTOS - intentos} intento(s).")
        self.usuarios.desbloquear(fila["id_usuario"])
        return {"id": fila["id_usuario"], "rol": fila["rol"], "usuario": fila["usuario"],
                "nombre": f'{fila["nombres"]} {fila["apellidos"]}'}

    # ------------------------------------------------------------ registro y alta (CU01, CU10)

    def validar(self, d: dict) -> dict:
        """Devuelve {campo: mensaje} con los errores del formulario de usuario."""
        errores = {}
        for campo, nombre in (("nombres", "los nombres"), ("apellidos", "los apellidos"),
                              ("numero_documento", "el número de documento"), ("correo", "el correo"),
                              ("usuario", "el usuario")):
            if not d.get(campo):
                errores[campo] = f"Escriba {nombre}."
        if d.get("tipo_documento") not in dict(self.TIPOS_DOCUMENTO):
            errores["tipo_documento"] = "Elija un tipo de documento."
        if d.get("numero_documento") and not re.fullmatch(r"[A-Za-z0-9]{4,20}", d["numero_documento"]):
            errores["numero_documento"] = "Use entre 4 y 20 letras o números, sin puntos ni espacios."
        if d.get("correo") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", d["correo"]):
            errores["correo"] = "El correo no tiene un formato válido."
        if d.get("usuario") and not re.fullmatch(r"[a-zA-Z0-9._-]{3,40}", d["usuario"]):
            errores["usuario"] = "Use entre 3 y 40 letras, números, punto, guion o guion bajo."
        if d.get("telefono") and not re.fullmatch(r"[0-9 +()-]{7,20}", d["telefono"]):
            errores["telefono"] = "El teléfono no es válido."
        if len(d.get("contrasena", "")) < self.MIN_CONTRASENA:
            errores["contrasena"] = f"La contraseña debe tener al menos {self.MIN_CONTRASENA} caracteres."
        elif d.get("contrasena") != d.get("confirmacion"):
            errores["confirmacion"] = "Las contraseñas no coinciden."
        if not errores.get("usuario") and self.usuarios.existe("usuario", d["usuario"]):
            errores["usuario"] = "Ese nombre de usuario ya está en uso."
        if not errores.get("correo") and self.usuarios.existe("correo", d["correo"]):
            errores["correo"] = "Ya existe una cuenta con ese correo."
        if not errores.get("numero_documento") and self.usuarios.existe(
                "numero_documento", d["numero_documento"], d.get("tipo_documento")):
            errores["numero_documento"] = "Ya existe una cuenta con ese documento."
        return errores

    def registrar(self, datos: dict) -> dict:
        """Registro publico: siempre crea consultantes, e inicia sesion."""
        self.crear(datos, "CONSULTANTE")
        return self.autenticar(datos["usuario"], datos["contrasena"])

    def crear(self, datos: dict, rol: str) -> int:
        errores = self.validar(datos)
        if rol not in self.ROLES:
            errores["rol"] = "Elija un rol."
        if errores:
            raise ErrorValidacion("Revise los campos marcados.", errores)
        return self.usuarios.crear(datos, rol, self.cifrar(datos["contrasena"]))

    # ------------------------------------------------------------ administracion (CU10)

    def listar(self) -> list[dict]:
        return self.usuarios.listar()

    def cambiar_rol(self, id_usuario: int, rol: str) -> None:
        if rol not in self.ROLES:
            raise ErrorValidacion("Rol no válido")
        self.usuarios.cambiar_rol(id_usuario, rol)

    def desbloquear(self, id_usuario: int) -> None:
        self.usuarios.desbloquear(id_usuario)

    def alternar_activo(self, id_usuario: int, solicitante: dict) -> None:
        if id_usuario != solicitante["id"]:
            self.usuarios.alternar_activo(id_usuario)
