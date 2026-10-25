/* Fondo animado del inicio de sesión: esqueleto en 3D de una vivienda y de un edificio que giran
   sobre una plataforma. Los colores siguen a los cuatro especialistas del sistema: estructura
   (ingeniero civil), eléctrica, hidráulica y gas. Sin librerías: canvas 2D y proyección propia. */
(() => {
  "use strict";
  const lienzo = document.getElementById("estructura");
  if (!lienzo || !lienzo.getContext) return;
  const ctx = lienzo.getContext("2d");

  // ------------------------------------------------------------------ parámetros
  const RADIO = 10;          // plataforma circular, en metros
  const PISO = 2.8;          // altura de un piso
  const ALTO = 12.6;         // altura total, para hacer aparecer la estructura de abajo hacia arriba
  const TIEMPO_COMPLETO = 8; // segundos tras los cuales todo está construido
  const DISTANCIA = 40;      // cámara
  const INCLINACION = 0.34;  // la cámara mira desde arriba (rad)
  const GIRO = 0.17;         // rad/s: una vuelta cada 37 s
  const ANGULO_INICIAL = -0.55;
  const Y_CENTRO = 5.6;      // altura de la escena que queda en el centro de la pantalla

  const ESTILOS = {
    suelo:      { rgb: "129,140,248", alfa: 0.55 },
    cuadricula: { rgb: "129,140,248", alfa: 0.22 },
    columna:    { rgb: "199,210,254", alfa: 0.90 },
    viga:       { rgb: "165,180,252", alfa: 0.72 },
    techo:      { rgb: "224,231,255", alfa: 0.88 },
    arriostre:  { rgb: "129,140,248", alfa: 0.60 },
    envolvente: { rgb: "148,163,184", alfa: 0.46 },
    electrica:  { rgb: "251,191,36",  alfa: 0.95 },
    agua:       { rgb: "34,211,238",  alfa: 0.95 },
    gas:        { rgb: "251,146,60",  alfa: 0.95 },
  };
  const SERVICIOS = new Set(["electrica", "agua", "gas"]);
  for (const e of Object.values(ESTILOS)) e.color = `rgb(${e.rgb})`;

  // ------------------------------------------------------------------ modelo
  const segmentos = [];   // { a, b, tipo, grosor, ini, dur }
  const nodos = [];       // uniones de la estructura: { p, ini }
  const rutas = [];       // recorrido de los pulsos por cada instalación

  const seg = (a, b, tipo, grosor = 1, ini, dur) => segmentos.push({ a, b, tipo, grosor, ini, dur });
  const poli = (pts, tipo, grosor, ini, dur) => { for (let i = 1; i < pts.length; i++) seg(pts[i - 1], pts[i], tipo, grosor, ini, dur); };
  const rect = (x0, x1, y, z0, z1, tipo, grosor) =>
    poli([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1], [x0, y, z0]], tipo, grosor);
  const ventanaZ = (x0, x1, y0, y1, z) => {   // marco con travesaño y montante, en un muro perpendicular a z
    poli([[x0, y0, z], [x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]], "envolvente", 0.8);
    seg([(x0 + x1) / 2, y0, z], [(x0 + x1) / 2, y1, z], "envolvente", 0.6);
    seg([x0, (y0 + y1) / 2, z], [x1, (y0 + y1) / 2, z], "envolvente", 0.6);
  };
  const ventanaX = (z0, z1, y0, y1, x) => {
    poli([[x, y0, z0], [x, y1, z0], [x, y1, z1], [x, y0, z1], [x, y0, z0]], "envolvente", 0.8);
    seg([x, y0, (z0 + z1) / 2], [x, y1, (z0 + z1) / 2], "envolvente", 0.6);
  };
  const equis = (a, b, c, d, tipo = "arriostre") => { seg(a, c, tipo, 0.9); seg(b, d, tipo, 0.9); };

  // Instalación con pulsos que la recorren (pulsos = 0: solo la línea).
  function instalacion(pts, tipo, pulsos = 0, velocidad = 2) {
    const desde = segmentos.length;
    poli(pts, tipo, 1.5);
    if (!pulsos) return;
    const acumulado = [0];
    for (let i = 1; i < pts.length; i++) acumulado.push(acumulado[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]));
    rutas.push({ pts, acumulado, total: acumulado[acumulado.length - 1], tipo, pulsos, velocidad, desde, hasta: segmentos.length });
  }

  function vivienda(cx, cz) {
    const X = [cx - 3.5, cx, cx + 3.5], z0 = cz - 2.5, z1 = cz + 2.5;
    const niveles = [0, PISO, 2 * PISO], aleroY = niveles[2], cumbreraY = aleroY + 2.3;
    for (const x of X) for (const z of [z0, z1]) {
      for (let n = 0; n < 2; n++) seg([x, niveles[n], z], [x, niveles[n + 1], z], "columna", 1.5);
      for (const y of niveles) nodos.push({ p: [x, y, z], y });
    }
    rect(X[0] - 0.5, X[2] + 0.5, 0, z0 - 0.5, z1 + 0.5, "viga", 0.8);            // zapata
    for (const y of niveles) {                                                    // losas y vigas
      rect(X[0], X[2], y, z0, z1, "viga", 1.2);
      seg([X[1], y, z0], [X[1], y, z1], "viga", 1.1);
      if (!y) continue;
      for (const x of [X[0] + 1.75, X[2] - 1.75]) seg([x, y, z0], [x, y, z1], "viga", 0.7);
      seg([X[0], y, cz], [X[2], y, cz], "viga", 0.7);
    }
    for (const x of [X[0], X[0] + 1.75, X[1], X[2] - 1.75, X[2]]) {               // cerchas del techo
      const g = x === X[0] || x === X[1] || x === X[2] ? 1.3 : 0.8;
      seg([x, aleroY - 0.55, cz - 3.1], [x, cumbreraY, cz], "techo", g);
      seg([x, aleroY - 0.55, cz + 3.1], [x, cumbreraY, cz], "techo", g);
      seg([x, aleroY, cz], [x, cumbreraY, cz], "techo", g * 0.8);
      seg([x, aleroY, cz], [x, aleroY + 1.15, cz - 1.25], "techo", 0.8);
      seg([x, aleroY, cz], [x, aleroY + 1.15, cz + 1.25], "techo", 0.8);
    }
    seg([X[0] - 0.4, cumbreraY, cz], [X[2] + 0.4, cumbreraY, cz], "techo", 1.5);  // cumbrera, aleros y correas
    for (const s of [-1, 1]) {
      seg([X[0] - 0.4, aleroY - 0.55, cz + 3.1 * s], [X[2] + 0.4, aleroY - 0.55, cz + 3.1 * s], "techo", 1.1);
      seg([X[0] - 0.4, aleroY + 1.15, cz + 1.25 * s], [X[2] + 0.4, aleroY + 1.15, cz + 1.25 * s], "techo", 0.9);
      seg([X[0] - 0.4, aleroY + 0.28, cz + 2.2 * s], [X[2] + 0.4, aleroY + 0.28, cz + 2.2 * s], "techo", 0.7);
    }
    nodos.push({ p: [X[1], cumbreraY, cz], y: cumbreraY });
    equis([X[0], 0, z1], [X[1], 0, z1], [X[1], PISO, z1], [X[0], PISO, z1]);      // arriostres
    equis([X[2], PISO, z0], [X[2], PISO, z1], [X[2], aleroY, z1], [X[2], aleroY, z0]);
    equis([X[1], PISO, z0], [X[2], PISO, z0], [X[2], aleroY, z0], [X[1], aleroY, z0]);
    poli([[cx + 1.1, 0, z1], [cx + 1.1, 2.1, z1], [cx + 2.2, 2.1, z1], [cx + 2.2, 0, z1]], "envolvente", 0.9);   // puerta
    ventanaZ(cx - 2.8, cx - 0.9, 3.6, 4.9, z1);
    ventanaZ(cx + 0.9, cx + 2.8, 3.6, 4.9, z1);
    ventanaZ(cx - 2.6, cx - 1.0, 0.9, 1.9, z1);
    ventanaX(cz - 1.0, cz + 1.0, 0.9, 1.9, X[2]);
    ventanaX(cz - 1.0, cz + 1.0, 3.6, 4.7, X[0]);

    instalacion([[cx - 3.0, 1.2, cz - 2.2], [cx - 3.0, PISO - 0.25, cz - 2.2], [cx + 3.0, PISO - 0.25, cz - 2.2],
                 [cx + 3.0, aleroY - 0.25, cz - 2.2], [cx - 3.0, aleroY - 0.25, cz - 2.2]], "electrica", 3, 2.4);
    instalacion([[cx - 3.9, -0.35, cz + 1.0], [cx + 2.0, -0.35, cz + 1.0], [cx + 2.0, aleroY - 0.5, cz + 1.0]], "agua", 3, 1.8);
    instalacion([[cx + 2.0, PISO - 0.35, cz + 1.0], [cx - 0.2, PISO - 0.35, cz + 1.0], [cx - 0.2, PISO - 0.35, cz - 1.6]], "agua");
    instalacion([[cx + 2.0, 0.7, cz + 1.0], [cx + 2.0, 0.7, cz - 1.8]], "agua");
    instalacion([[cx + 4.8, 0.3, cz + 2.0], [cx - 1.8, 0.3, cz + 2.0], [cx - 1.8, 1.05, cz + 2.0]], "gas", 2, 1.5);
  }

  function edificio(cx, cz) {
    const X = [cx - 2.4, cx, cx + 2.4], Z = [cz - 2.4, cz, cz + 2.4], pisos = 4, alto = pisos * PISO;
    for (const x of X) for (const z of Z) {
      for (let n = 0; n < pisos; n++) seg([x, n * PISO, z], [x, (n + 1) * PISO, z], "columna", 1.4);
      if ((x === X[1]) !== (z === Z[1])) continue;                                // nodos: esquinas y centro
      for (let n = 0; n <= pisos; n++) nodos.push({ p: [x, n * PISO, z], y: n * PISO });
    }
    rect(X[0] - 0.5, X[2] + 0.5, 0, Z[0] - 0.5, Z[2] + 0.5, "viga", 0.8);         // zapata
    for (let n = 0; n <= pisos; n++) {                                            // losas y vigas
      const y = n * PISO;
      rect(X[0], X[2], y, Z[0], Z[2], "viga", 1.1);
      seg([X[1], y, Z[0]], [X[1], y, Z[2]], "viga", 0.8);
      seg([X[0], y, Z[1]], [X[2], y, Z[1]], "viga", 0.8);
    }
    rect(X[0] - 0.2, X[2] + 0.2, alto + 0.7, Z[0] - 0.2, Z[2] + 0.2, "techo", 1.1);   // pretil
    for (const x of [X[0] - 0.2, X[2] + 0.2]) for (const z of [Z[0] - 0.2, Z[2] + 0.2]) seg([x, alto, z], [x, alto + 0.7, z], "techo", 0.8);
    const m = 0.8;                                                                // casa de máquinas
    rect(cx - m, cx + m, alto, cz - m, cz + m, "techo", 1);
    rect(cx - m, cx + m, alto + 1.3, cz - m, cz + m, "techo", 1);
    for (const x of [cx - m, cx + m]) for (const z of [cz - m, cz + m]) seg([x, alto, z], [x, alto + 1.3, z], "techo", 1);
    for (const n of [0, 2]) equis([X[0], n * PISO, Z[2]], [X[1], n * PISO, Z[2]], [X[1], (n + 1) * PISO, Z[2]], [X[0], (n + 1) * PISO, Z[2]]);
    for (const n of [1, 3]) equis([X[1], n * PISO, Z[2]], [X[2], n * PISO, Z[2]], [X[2], (n + 1) * PISO, Z[2]], [X[1], (n + 1) * PISO, Z[2]]);
    for (const n of [0, 2]) equis([X[2], n * PISO, Z[0]], [X[2], n * PISO, Z[1]], [X[2], (n + 1) * PISO, Z[1]], [X[2], (n + 1) * PISO, Z[0]]);

    instalacion([[cx - 1.6, -0.3, cz - 1.2], [cx - 1.6, alto + 0.3, cz - 1.2]], "electrica", 4, 3.2);
    instalacion([[cx + 1.6, -0.3, cz + 1.2], [cx + 1.6, alto + 0.3, cz + 1.2]], "agua", 4, 2.6);
    for (let n = 1; n <= pisos; n++) {                                            // derivaciones por piso
      instalacion([[cx - 1.6, n * PISO - 0.25, cz - 1.2], [cx - 0.2, n * PISO - 0.25, cz - 1.2]], "electrica");
      instalacion([[cx + 1.6, n * PISO - 0.35, cz + 1.2], [cx + 0.2, n * PISO - 0.35, cz + 1.2]], "agua");
    }
  }

  function suelo() {
    const pasos = 90, marcas = 72, paso = (2 * Math.PI) / pasos;
    for (let i = 0; i < pasos; i++) {                                             // aro de la plataforma
      const a = i * paso, b = (i + 1) * paso, ini = 0.1 + (i / pasos) * 1.3;
      seg([RADIO * Math.cos(a), 0, RADIO * Math.sin(a)], [RADIO * Math.cos(b), 0, RADIO * Math.sin(b)], "suelo", 1.2, ini, 0.4);
    }
    for (let i = 0; i < marcas; i++) {                                            // graduación, para que se note el giro
      const a = (i / marcas) * 2 * Math.PI, mayor = i % 6 === 0, largo = mayor ? 0.9 : 0.35;
      seg([RADIO * Math.cos(a), 0, RADIO * Math.sin(a)], [(RADIO + largo) * Math.cos(a), 0, (RADIO + largo) * Math.sin(a)],
          "suelo", mayor ? 1.1 : 0.6, 0.3 + (i / marcas) * 1.3, 0.3);
    }
    poli([[RADIO + 1.0, 0, 0.4], [RADIO + 1.0, 0, -0.4], [RADIO + 1.9, 0, 0], [RADIO + 1.0, 0, 0.4]], "suelo", 1.4, 1.6, 0.4);   // norte
    for (let c = -7.5; c <= 7.5; c += 2.5) {                                      // cuadrícula de plano
      const h = Math.sqrt((RADIO - 0.5) ** 2 - c * c), ini = 0.2 + Math.abs(c) / RADIO * 0.9;
      seg([c, 0, -h], [c, 0, h], "cuadricula", 0.8, ini, 1.0);
      seg([-h, 0, c], [h, 0, c], "cuadricula", 0.8, ini, 1.0);
    }
  }

  suelo();
  vivienda(-3.4, 1.6);
  edificio(4.3, -3.0);

  // Orden de aparición: el suelo, luego la estructura de abajo hacia arriba y al final las instalaciones.
  const azar = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  segmentos.forEach((s, i) => {
    if (s.ini !== undefined) return;
    const ymed = (s.a[1] + s.b[1]) / 2;
    s.ini = (SERVICIOS.has(s.tipo) ? 2.6 + Math.max(ymed, 0) / ALTO * 1.0 : 0.5 + Math.max(ymed, 0) / ALTO * 2.0) + azar(i) * 0.35;
    s.dur = 0.8;
  });
  nodos.forEach((n) => { n.ini = 0.5 + n.y / ALTO * 2.0 + 0.55; });
  for (const r of rutas) {
    r.listo = 0;
    for (let i = r.desde; i < r.hasta; i++) r.listo = Math.max(r.listo, segmentos[i].ini + segmentos[i].dur);
  }

  // ------------------------------------------------------------------ proyección
  let ancho = 0, alto = 0, dpr = 1, foco = 1, cx = 0, cy = 0;
  let cosT = 1, sinT = 0;
  const cosF = Math.cos(INCLINACION), sinF = Math.sin(INCLINACION);
  const A = { x: 0, y: 0, k: 0, t: 0 }, B = { x: 0, y: 0, k: 0, t: 0 };

  function medir() {
    const r = lienzo.getBoundingClientRect();
    ancho = Math.round(r.width);
    alto = Math.round(r.height);
    if (!ancho || !alto) return false;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    lienzo.width = ancho * dpr;
    lienzo.height = alto * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    foco = Math.min(ancho / 25, alto / 21.5) * DISTANCIA;   // la plataforma entera cabe en el panel
    cx = ancho * 0.54;
    cy = alto * 0.46;
    return true;
  }

  // Gira la escena alrededor del centro de la plataforma y la proyecta con perspectiva.
  // o.t: 0 = lejos, 1 = cerca; sirve para atenuar lo que está atrás.
  function proyectar(x, y, z, o) {
    const xr = x * cosT + z * sinT, zr = -x * sinT + z * cosT;
    const yr = y * cosF - zr * sinF, zc = y * sinF + zr * cosF;
    const k = foco / (DISTANCIA - zc);
    o.x = cx + xr * k;
    o.y = cy - (yr - Y_CENTRO) * k;
    o.k = k;
    o.t = Math.min(1, Math.max(0, (zc + RADIO) / (2 * RADIO)));
  }

  const progreso = (t, ini, dur) => {
    const p = (t - ini) / dur;
    return p <= 0 ? 0 : p >= 1 ? 1 : 1 - Math.pow(1 - p, 3);
  };

  function brillo(rgb) {
    const c = document.createElement("canvas");
    c.width = c.height = 48;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(24, 24, 0, 24, 24, 24);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.2, `rgba(${rgb},0.95)`);
    grad.addColorStop(0.55, `rgba(${rgb},0.26)`);
    grad.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, 48, 48);
    return c;
  }
  for (const tipo of SERVICIOS) ESTILOS[tipo].brillo = brillo(ESTILOS[tipo].rgb);

  // ------------------------------------------------------------------ dibujo
  function dibujar(t) {
    const angulo = ANGULO_INICIAL + GIRO * t;
    cosT = Math.cos(angulo);
    sinT = Math.sin(angulo);
    ctx.clearRect(0, 0, ancho, alto);
    ctx.lineCap = "round";

    proyectar(0, 0, 0, A);                                                        // resplandor bajo la plataforma
    const aparecer = progreso(t, 0.2, 1.6);
    if (aparecer) {
      const radio = RADIO * A.k * 1.05;
      ctx.save();
      ctx.translate(A.x, A.y);
      ctx.scale(1, sinF);
      const resplandor = ctx.createRadialGradient(0, 0, 0, 0, 0, radio);
      resplandor.addColorStop(0, "rgba(99,102,241,0.30)");
      resplandor.addColorStop(0.6, "rgba(99,102,241,0.10)");
      resplandor.addColorStop(1, "rgba(99,102,241,0)");
      ctx.globalAlpha = aparecer;
      ctx.fillStyle = resplandor;
      ctx.beginPath();
      ctx.arc(0, 0, radio, 0, 6.2832);
      ctx.fill();
      ctx.restore();
    }

    for (const s of segmentos) {
      const p = progreso(t, s.ini, s.dur);
      if (!p) continue;
      const e = ESTILOS[s.tipo];
      proyectar(s.a[0], s.a[1], s.a[2], A);
      proyectar(s.a[0] + (s.b[0] - s.a[0]) * p, s.a[1] + (s.b[1] - s.a[1]) * p, s.a[2] + (s.b[2] - s.a[2]) * p, B);
      const cerca = (A.t + B.t) / 2;
      ctx.globalAlpha = e.alfa * (0.2 + 0.8 * cerca);
      ctx.strokeStyle = e.color;
      ctx.lineWidth = s.grosor * (0.8 + 0.55 * cerca);
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(B.x, B.y);
      ctx.stroke();
      if (p < 1) {                                                                // chispa de soldadura mientras se construye
        ctx.globalAlpha = 0.9;
        ctx.fillStyle = "#e0e7ff";
        ctx.beginPath();
        ctx.arc(B.x, B.y, 1.8, 0, 6.2832);
        ctx.fill();
      }
    }

    ctx.fillStyle = "#e0e7ff";
    for (const n of nodos) {
      const p = progreso(t, n.ini, 0.5);
      if (!p) continue;
      proyectar(n.p[0], n.p[1], n.p[2], A);
      ctx.globalAlpha = 0.25 + 0.75 * A.t;
      ctx.beginPath();
      ctx.arc(A.x, A.y, Math.max(1.3, 0.055 * A.k) * p, 0, 6.2832);
      ctx.fill();
    }

    for (const r of rutas) {                                                      // pulsos que recorren las instalaciones
      const aparece = Math.min(1, (t - r.listo - 0.3) / 0.8);
      if (aparece <= 0) continue;
      const brilloTipo = ESTILOS[r.tipo].brillo;
      for (let i = 0; i < r.pulsos; i++) {
        const d = (t * r.velocidad + (i * r.total) / r.pulsos) % r.total;
        let j = 1;
        while (j < r.acumulado.length - 1 && r.acumulado[j] < d) j++;
        const f = (d - r.acumulado[j - 1]) / (r.acumulado[j] - r.acumulado[j - 1]), a = r.pts[j - 1], b = r.pts[j];
        proyectar(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, A);
        const lado = Math.max(12, 0.5 * A.k);
        ctx.globalAlpha = aparece * (0.35 + 0.65 * A.t);
        ctx.drawImage(brilloTipo, A.x - lado / 2, A.y - lado / 2, lado, lado);
      }
    }
    ctx.globalAlpha = 1;
  }

  // ------------------------------------------------------------------ ciclo
  // Quien tiene desactivadas las animaciones en su sistema ve la estructura completa y quieta,
  // y puede reanudarla con el botón. Cualquiera puede pausarla (WCAG 2.2.2).
  const boton = document.getElementById("estructura-pausa");
  const consulta = window.matchMedia("(prefers-reduced-motion: reduce)");
  let pausado = consulta.matches;
  let reloj = pausado ? TIEMPO_COMPLETO : 0, ultimo = 0, cuadro = 0;

  function paso(ahora) {
    cuadro = requestAnimationFrame(paso);
    reloj += Math.min((ahora - ultimo) / 1000, 0.1);   // si la pestaña estuvo oculta no hay saltos
    ultimo = ahora;
    dibujar(reloj);
  }
  function detener() {
    if (cuadro) cancelAnimationFrame(cuadro);
    cuadro = 0;
  }
  function actualizar() {
    detener();
    if (!ancho) return;
    if (pausado) { dibujar(reloj); return; }
    ultimo = performance.now();
    cuadro = requestAnimationFrame(paso);
  }
  function rotular() {
    if (!boton) return;
    const texto = pausado ? "Reanudar la animación de fondo" : "Pausar la animación de fondo";
    boton.setAttribute("aria-label", texto);
    boton.title = texto.replace(" de fondo", "");
    boton.querySelector("[data-icono=pausa]").hidden = pausado;
    boton.querySelector("[data-icono=reproducir]").hidden = !pausado;
  }

  if (boton) boton.addEventListener("click", () => { pausado = !pausado; rotular(); actualizar(); });
  consulta.addEventListener("change", (e) => { pausado = e.matches; rotular(); actualizar(); });
  rotular();

  // El panel solo existe en pantallas anchas: al ocultarse no se dibuja nada.
  new ResizeObserver(() => { if (medir()) actualizar(); else detener(); }).observe(lienzo);
})();
