/**
 * La cara de Lancelot, dibujada en un <canvas>: el mismo personaje que en la laptop
 * (interfaz/cara.py), con los mismos estados y colores.
 *
 *   tranquilo  turquesa · nada para hoy          pendiente  ámbar · hay tareas hoy
 *   alerta     naranja que late · algo venció    feliz      ojos ^ ^ al completar o agregar
 *   dormido    ojos cerrados y "z" (de noche)    escuchando celeste con barritas (voz)
 */
export const COLORES = {
  bisel: "#16181d", pantalla: "#050608", ojos: "#f2f5f7",
  tranquilo: "#4fd1c5", pendiente: "#f6c453", alerta: "#ff6b4a", feliz: "#5be37d",
  dormido: "#3a4a6b", escuchando: "#4fc3ff",
};

export class Cara {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.estado = "tranquilo";
    this.felizHasta = 0;
    this.contador = 0;
    this.t = 0;
    this.cierre = 0;                     // 0 = ojos abiertos, 1 = cerrados
    this.proximoParpadeo = 2;
    this.inicioParpadeo = -1;
    this.mirada = [0, 0];
    this.objetivo = [0, 0];
    this.proximoVistazo = 1;
    this.quieta = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this._ultimo = performance.now();
    this._ajustar();
    addEventListener("resize", () => this._ajustar());
    requestAnimationFrame((ms) => this._cuadro(ms));
  }

  /** Estado "de fondo" (lo decide la app según las tareas). */
  poner(estado, contador = 0) {
    this.estado = estado;
    this.contador = contador;
    this.canvas.dataset.estado = estado;
  }

  celebrar(segundos = 2.5) {
    this.felizHasta = this.t + segundos;
  }

  get estadoVisible() {
    return this.t < this.felizHasta && this.estado !== "escuchando" ? "feliz" : this.estado;
  }

  _ajustar() {
    const lado = this.canvas.clientWidth || 120;
    const dpr = Math.min(devicePixelRatio || 1, 3);
    this.canvas.width = this.canvas.height = Math.round(lado * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.lado = lado;
  }

  _cuadro(ms) {
    const dt = Math.min(0.1, (ms - this._ultimo) / 1000);
    this._ultimo = ms;
    if (!document.hidden) {
      this.t += dt;
      this._animar();
      this._dibujar();
    }
    requestAnimationFrame((m) => this._cuadro(m));
  }

  _animar() {
    if (this.quieta) { this.cierre = 0; this.mirada = [0, 0]; return; }
    // Parpadeo cada 2-6 s
    if (this.inicioParpadeo < 0 && this.t >= this.proximoParpadeo) this.inicioParpadeo = this.t;
    if (this.inicioParpadeo >= 0) {
      const f = (this.t - this.inicioParpadeo) / 0.16;
      this.cierre = f < 1 ? Math.sin(Math.PI * f) : 0;
      if (f >= 1) { this.inicioParpadeo = -1; this.proximoParpadeo = this.t + 2 + Math.random() * 4; }
    }
    // Mira a los lados de vez en cuando
    if (this.t >= this.proximoVistazo) {
      const quieto = Math.random() < 0.45;
      this.objetivo = quieto ? [0, 0] : [(Math.random() * 2 - 1) * 7, (Math.random() * 2 - 1) * 4];
      this.proximoVistazo = this.t + 1.2 + Math.random() * 2.8;
    }
    this.mirada = this.mirada.map((v, i) => v + (this.objetivo[i] - v) * 0.12);
  }

  _dibujar() {
    const c = this.ctx, L = this.lado, cx = L / 2, cy = L / 2;
    const margen = L * 0.085, radio = L / 2 - margen, e = radio / 75;
    const estado = this.estadoVisible;
    const color = COLORES[estado];
    const pulso = estado === "alerta" ? (Math.sin(this.t * 6) + 1) / 2
      : estado === "escuchando" ? (Math.sin(this.t * 5) + 1) / 2 : 0;
    c.clearRect(0, 0, L, L);

    // Brillo del anillo
    const brillo = c.createRadialGradient(cx, cy, radio - 4, cx, cy, radio + margen);
    brillo.addColorStop(0, conAlfa(color, 0.28 + 0.35 * pulso));
    brillo.addColorStop(1, conAlfa(color, 0));
    circulo(c, cx, cy, radio + margen, brillo);
    // Cuerpo, anillo y pantalla
    circulo(c, cx, cy, radio, COLORES.bisel);
    c.beginPath();
    c.arc(cx, cy, radio - 7 * e, 0, Math.PI * 2);
    c.strokeStyle = color;
    c.lineWidth = (3.5 + 2 * pulso) * e;
    c.stroke();
    const rp = radio - 12 * e;
    const fondo = c.createRadialGradient(cx, cy - rp * 0.4, 0, cx, cy - rp * 0.4, rp * 1.3);
    fondo.addColorStop(0, "#11141a");
    fondo.addColorStop(1, COLORES.pantalla);
    circulo(c, cx, cy, rp, fondo);

    // Ojos
    let ancho = 32 * e, alto = 39 * e;
    let bx = cx + this.mirada[0] * e, by = cy - 4 * e + this.mirada[1] * e;
    if (estado === "alerta") { ancho *= 1.15; alto *= 1.15; by += Math.sin(this.t * 12) * 1.5 * e; }
    if (estado === "escuchando") { ancho *= 1.08; alto *= 1.08; }
    for (const lado of [-1, 1]) {
      const ox = bx + lado * 28 * e;
      if (estado === "feliz") ojoFeliz(c, ox, by, ancho, alto, e);
      else if (estado === "dormido") ojoDormido(c, ox, by, ancho, e);
      else ojoAbierto(c, ox, by, ancho, Math.max(alto * (1 - this.cierre), 3 * e));
    }
    if (estado === "dormido") this._zetas(c, cx, cy, rp, e);
    if (estado === "escuchando") this._ondas(c, cx, cy + rp * 0.5, e, color);

    // Número de tareas de hoy
    if (this.contador > 0 && !["dormido", "feliz", "escuchando"].includes(estado)) {
      c.fillStyle = color;
      c.font = `800 ${Math.max(9, 9 * e)}px Manrope, sans-serif`;
      c.textAlign = "center";
      c.textBaseline = "middle";
      c.fillText(this.contador < 10 ? String(this.contador) : "9+", cx, cy + rp * 0.62);
    }
  }

  _zetas(c, cx, cy, rp, e) {
    c.font = `800 ${11 * e}px Manrope, sans-serif`;
    for (let i = 0; i < 3; i++) {
      const fase = ((this.quieta ? 0.4 : this.t * 0.35) + i / 3) % 1;
      c.fillStyle = conAlfa(COLORES.ojos, 0.8 * Math.sin(Math.PI * fase));
      c.fillText("z", cx + rp * 0.35 + fase * 14 * e, cy - rp * 0.25 - fase * 30 * e);
    }
  }

  _ondas(c, x, y, e, color) {
    c.fillStyle = color;
    for (let i = 0; i < 5; i++) {
      const h = (4 + 7 * Math.abs(Math.sin(this.t * 7 + i * 0.9))) * e;
      redondeado(c, x + (i - 2) * 6 * e - 1.5 * e, y - h / 2, 3 * e, h, 1.5 * e);
    }
  }
}

function circulo(c, x, y, r, relleno) {
  c.beginPath();
  c.arc(x, y, r, 0, Math.PI * 2);
  c.fillStyle = relleno;
  c.fill();
}

function redondeado(c, x, y, w, h, r) {
  c.beginPath();
  c.roundRect(x, y, w, h, r);
  c.fill();
}

function ojoAbierto(c, x, y, w, h) {
  c.fillStyle = conAlfa(COLORES.ojos, 0.11);
  redondeado(c, x - w / 2 - 3, y - h / 2 - 3, w + 6, h + 6, w / 2 + 3);
  c.fillStyle = COLORES.ojos;
  redondeado(c, x - w / 2, y - h / 2, w, h, Math.min(w, h) / 2);
}

function ojoFeliz(c, x, y, w, h, e) {
  c.beginPath();
  c.moveTo(x - w / 2, y + h * 0.15);
  c.quadraticCurveTo(x, y - h * 0.65, x + w / 2, y + h * 0.15);
  c.strokeStyle = COLORES.ojos;
  c.lineWidth = 6 * e;
  c.lineCap = "round";
  c.stroke();
}

function ojoDormido(c, x, y, w, e) {
  c.beginPath();
  c.moveTo(x - w / 2, y);
  c.quadraticCurveTo(x, y + 7 * e, x + w / 2, y);
  c.strokeStyle = conAlfa(COLORES.ojos, 0.67);
  c.lineWidth = 4 * e;
  c.lineCap = "round";
  c.stroke();
}

function conAlfa(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}
