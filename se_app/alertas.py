"""Acciones inmediatas de seguridad para los diagnosticos de urgencia
critica (RF03, CU04). Se muestran en el banner rojo antes que cualquier
otra informacion. Dependen de la categoria, no de la regla.
"""

ACCIONES_INMEDIATAS = {
    "GAS": ["Ventile: abra puertas y ventanas",
            "No encienda ni apague interruptores, ni use llamas",
            "Cierre la llave de paso del gas y salga de la vivienda",
            "Llame a la línea de emergencias de su empresa de gas"],
    "ELE": ["Baje el breaker de la zona o el principal",
            "No vuelva a conectar nada en esa zona",
            "Si ve humo o llama, salga y llame al 123"],
    "EST": ["Salga de la zona afectada y no vuelva a entrar",
            "Aleje a las personas de muros y columnas inclinados",
            "Llame al 123 si hay riesgo de colapso"],
}

GENERICAS = ["Aléjese de la zona afectada", "Llame al 123 si hay riesgo para las personas"]


def inmediatas(categoria: str) -> list[str]:
    return ACCIONES_INMEDIATAS.get(categoria, GENERICAS)
