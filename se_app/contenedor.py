"""Raiz de composicion: crea las instancias de las tres capas y las conecta.

    presentacion (controladores)  ->  negocio (servicios, motores)  ->  datos (repositorios)

Cada capa recibe la siguiente por constructor; ninguna crea sus
dependencias por su cuenta, lo que permite probarlas por separado.
"""
from .datos.conexion import crear_base_datos
from .datos.repositorio_atenciones import RepositorioAtenciones
from .datos.repositorio_conocimiento import RepositorioConocimiento
from .datos.repositorio_usuarios import RepositorioUsuarios
from .negocio.inferencia_bayesiana import MotorBayesiano
from .negocio.motor_prolog import MotorProlog
from .negocio.servicio_conocimiento import ServicioConocimiento
from .negocio.servicio_diagnostico import ServicioDiagnostico
from .negocio.servicio_usuarios import ServicioUsuarios
from .negocio.servicio_viviendas import ServicioViviendas


class Contenedor:
    def __init__(self):
        # Capa de datos
        self.bd = crear_base_datos()
        self.repo_conocimiento = RepositorioConocimiento(self.bd)
        self.repo_atenciones = RepositorioAtenciones(self.bd)
        self.repo_usuarios = RepositorioUsuarios(self.bd)
        # Capa de negocio
        self.motor_bayesiano = MotorBayesiano(self.repo_conocimiento)
        self.motor_prolog = MotorProlog(self.repo_conocimiento)
        self.diagnostico = ServicioDiagnostico(self.repo_atenciones, self.repo_conocimiento,
                                               self.motor_bayesiano, self.motor_prolog)
        self.conocimiento = ServicioConocimiento(self.repo_conocimiento, self.motor_prolog)
        self.usuarios = ServicioUsuarios(self.repo_usuarios)
        self.viviendas = ServicioViviendas(self.repo_atenciones)


contenedor = Contenedor()
