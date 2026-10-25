# Sistema experto de diagnóstico de vivienda · Aplicación web

Capa de presentación y motor de inferencia del proyecto de Sistemas Expertos
(UMB, 2026). El código está orientado a objetos y organizado en tres capas:

```
Navegador ──HTMX──▶ presentacion/   Controladores FastAPI y vistas Jinja2
                        │
                        ▼
                    negocio/        MotorBayesiano · MotorProlog (SWI-Prolog vía Janus) · servicios
                        │
                        ▼
                    datos/          Repositorios ──▶ MySQL 8: se_base_conocimiento + se_transaccional
```

- **La base de conocimiento no está en el código** (RNF19). Las reglas, sus antecedentes If/And y
  sus factores de certeza se leen de MySQL; si el experto cambia una regla, el motor razona con el
  cambio desde la siguiente consulta.
- **Inferencia bayesiana con consultas granulares.** Tras cada respuesta, `MotorBayesiano` consulta
  el gránulo de la pregunta respondida (qué reglas la usan y qué respuesta espera cada una),
  actualiza la probabilidad de cada hipótesis con el teorema de Bayes y elige la siguiente pregunta
  por ganancia de información. Al concluir reporta las 5 hipótesis más probables con su peso y la
  hipótesis H0, «sin falla identificable» (conclusión por defecto, RNF22). El código no tiene
  condicionales por regla.
- **Prolog sigue en el sistema**: genera el árbol de decisión, verifica la coherencia de la base y
  confirma lógicamente la regla ganadora (`prolog/motor.pl`).
- **Diseño B · Centro de diagnóstico** (ver `../.21st/design.json`). El consultante ve un flujo sencillo;
  el experto y el administrador ven además las probabilidades en vivo.

El diseño del sistema de inferencia (diagramas de caja negra, de flujo de datos y de clases, y el
documento del avance en Word y PDF) está en `../entrega_inferencia_bayesiana/`.

## Requisitos

| Herramienta | Versión probada |
|---|---|
| Python | 3.13 |
| SWI-Prolog | 10.0.2 (en `C:\Program Files\swipl`) |
| MySQL | 8.4 en Docker (contenedor `se-mysql`) |
| Node.js | solo para recompilar los estilos |

## Puesta en marcha

Todos los comandos se ejecutan desde la carpeta `aplicacion`.

1. **Encender MySQL.** Abra Docker Desktop y verifique que el contenedor `se-mysql` esté en verde.
   Si las bases no existen, ejecute en orden los scripts `01` a `04` de la carpeta del proyecto.
   Después ejecute una vez `06_inferencia_bayesiana.sql`, que crea la tabla de hipótesis ponderadas.

2. **Crear el entorno de Python** (solo la primera vez):

   ```bash
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

3. **Configurar la conexión** (opcional). Se usa `../mysql_local_prueba.env`. Para cambiar algo,
   cree `.env` en esta carpeta y llene solo lo que quiera cambiar; los valores vacíos se ignoran.

4. **Crear los usuarios de prueba** (`admin`, `experto`, `consulta`) con contraseña cifrada.
   La contraseña de prueba es el valor `SEED_PASSWORD` de `.env` (o de la variable de entorno
   del mismo nombre).

   ```bash
   .venv\Scripts\python -m scripts.semilla
   ```

5. **Iniciar la aplicación:**

   ```bash
   .venv\Scripts\python -m uvicorn se_app.main:app --reload --port 8000
   ```

   Abra http://127.0.0.1:8000 e inicie sesión.

## Pruebas

```bash
.venv\Scripts\python -m pytest -q tests
```

Son 23 pruebas. Las unitarias del motor bayesiano y del motor Prolog no necesitan MySQL: usan
`RepositorioEnMemoria`, que reemplaza a la capa de datos. Con MySQL encendido, además recorren la
ruta de **cada una de las 49 reglas**, la conclusión por defecto en las 7 categorías y los casos de
la Tabla 52 del manual.

## Estilos

Tailwind se compila a un archivo local (la red no siempre alcanza el CDN):

```bash
npx tailwindcss@3.4.16 -i estilos/app.css -o se_app/presentacion/static/css/app.css --minify
```

Recompile después de agregar clases nuevas en las plantillas. HTMX 2.0.4 está en
`se_app/presentacion/static/js/htmx.min.js`.

## Estructura

```
aplicacion/
├── prolog/motor.pl                  Motor de reglas (SWI-Prolog): árbol, coherencia y confirmación
├── se_app/
│   ├── main.py                      Punto de entrada (uvicorn se_app.main:app)
│   ├── config.py                    Configuración leída de los archivos .env
│   ├── contenedor.py                Raíz de composición: crea e inyecta las tres capas
│   ├── presentacion/                CAPA DE PRESENTACIÓN
│   │   ├── app.py                   Crea FastAPI, registra los controladores y los errores
│   │   ├── vistas.py                Render de plantillas y redirecciones HTMX
│   │   ├── seguridad_web.py         Sesión y control de acceso por rol
│   │   ├── controladores/           Controlador base y sus cinco subclases
│   │   ├── templates/               Pantallas Jinja2 (diseño B)
│   │   └── static/                  CSS compilado y HTMX
│   ├── negocio/                     CAPA DE NEGOCIO
│   │   ├── modelos.py               Entidades: Hipotesis, Pregunta, Evidencia, Distribucion, Decision
│   │   ├── inferencia_bayesiana.py  MotorBayesiano
│   │   ├── motor_prolog.py          MotorProlog (puente Janus)
│   │   ├── servicio_*.py            Diagnóstico, conocimiento, usuarios y viviendas
│   │   └── errores.py               Excepciones de negocio
│   └── datos/                       CAPA DE DATOS
│       ├── conexion.py              BaseDatos: pool de conexiones y transacciones
│       └── repositorio_*.py         Conocimiento (consultas granulares), atenciones y usuarios
├── scripts/semilla.py               Usuarios de prueba
├── scripts/capturas.py              Capturas para la documentación (../mockups/capturas)
├── tests/                           Motor bayesiano, motor Prolog y usuarios (23 pruebas)
└── estilos/app.css                  Fuente de Tailwind
```

## Casos de uso cubiertos

| CU | Pantalla |
|---|---|
| CU01 Iniciar sesión | `/login` (bloqueo tras 5 intentos) |
| Registro de cuenta | `/registro` (público, siempre crea consultantes) |
| CU02 Registrar vivienda | `/viviendas` |
| CU03 Diagnosticar falla | `/diagnostico/nuevo` → preguntas Sí/No elegidas por ganancia de información |
| CU04 Alerta de riesgo crítico | Banner rojo en el reporte |
| CU05 Reporte de diagnóstico | `/diagnostico/{id}/reporte` con las 5 hipótesis ponderadas (Descargar PDF = imprimir) |
| CU06 Agendar cita | Reporte y `/citas` |
| CU07 Consultar historial | `/historial` con filtros |
| CU08 / CU09 Gestionar y validar reglas | `/conocimiento` (experto) |
| Árbol de decisión | `/arbol` (experto y administrador; generado por el motor, con chequeo de coherencia) |
| CU10 Usuarios y roles | `/usuarios` (administrador: crear usuarios con cualquier rol, cambiar rol, bloquear) |
| CU11 Bitácora | `/bitacora` (administrador) |
