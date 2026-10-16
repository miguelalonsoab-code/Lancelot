/**
 * Frases para la cara del celular: las mismas de la laptop (nucleo/frases.py, REFLEXIONES) más las tuyas,
 * que la laptop sube desde frases.txt. Una prueba revisa que esta lista sea igual a la de Python.
 */
export const REFLEXIONES = [
  "No dejes para mañana lo que puedes hacer hoy.",
  "El día depende de ti, puedes hacerlo grandioso.",
  "No dejes que tus malos pensamientos te controlen, tú puedes controlarlos.",
  "Un paso pequeño hoy vale más que un plan perfecto mañana.",
  "No tienes que hacerlo todo hoy. Solo lo siguiente.",
  "Respira. Una cosa a la vez.",
  "Lo que hoy te cuesta, mañana te sale solo.",
  "Empezar es la mitad del camino.",
  "Hecho es mejor que perfecto.",
  "Tu yo del futuro te va a agradecer lo que hagas ahora.",
  "Equivocarse también es avanzar: es aprender qué no funciona.",
  "La disciplina es elegir entre lo que quieres ahora y lo que más quieres.",
  "Descansar también es parte del trabajo.",
  "No te compares con otros; compárate con quien eras ayer.",
  "Los días difíciles también terminan. Este también.",
  "Si no sabes por dónde empezar, empieza por lo más pequeño.",
  "Cada tarea terminada es una preocupación menos.",
  "Hoy es un buen día para tachar algo de la lista.",
  "Tu mente es un jardín: cuida lo que siembras en ella.",
  "No esperes a tener ganas. Las ganas llegan cuando ya empezaste.",
  "Poco a poco se llega lejos.",
  "Lo importante no es ir rápido, es no detenerse.",
  "Agradece algo de hoy, por pequeño que sea.",
  "Eres más capaz de lo que crees.",
  "Un error no te define; lo que haces después, sí.",
  "Ordena tu espacio y tu mente se ordena con él.",
  "Toma agua, endereza la espalda y sigue.",
  "La motivación te hace empezar; el hábito te hace seguir.",
  "Pregúntate: ¿qué es lo más importante ahora mismo?",
  "Celebra tus avances, aunque sean pequeños.",
  "Lo que hoy siembras, mañana lo cosechas.",
  "Si te caes siete veces, levántate ocho.",
  "Hoy no tiene que ser perfecto para ser un buen día.",
  "Descansa si lo necesitas, pero no te rindas.",
  "La paciencia también es avanzar.",
  "Háblate con el cariño con que le hablarías a un amigo.",
  "Haz hoy algo que te acerque a quien quieres ser.",
  "Cinco minutos de enfoque valen más que una hora de distracción.",
  "Confía en el proceso: los resultados llegan.",
  "Un buen día empieza con una buena decisión.",
  "Si algo te preocupa, anótalo: tu mente descansa cuando no tiene que recordarlo todo.",
  "La constancia le gana a la prisa.",
];

/**
 * Como sacar papelitos de una bolsa: al azar y sin repetir hasta usarlas todas
 * (igual que BolsaFrases de la laptop).
 */
export class BolsaFrases {
  constructor(frases = REFLEXIONES) {
    this.frases = [];
    this.bolsa = [];
    this.ultima = null;
    this.cambiar(frases);
  }

  cambiar(frases) {
    const unicas = [...new Set(frases.filter(Boolean))];
    const nuevas = unicas.filter((f) => !this.frases.includes(f));
    this.frases = unicas;
    this.bolsa = mezclar([...this.bolsa.filter((f) => unicas.includes(f)), ...nuevas]);
  }

  sacar() {
    if (!this.frases.length) return null;
    if (!this.bolsa.length) {
      this.bolsa = mezclar([...this.frases]);
      const n = this.bolsa.length;
      if (n > 1 && this.bolsa[n - 1] === this.ultima) [this.bolsa[0], this.bolsa[n - 1]] = [this.bolsa[n - 1], this.bolsa[0]];
    }
    this.ultima = this.bolsa.pop();
    return this.ultima;
  }
}

function mezclar(lista) {
  for (let i = lista.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [lista[i], lista[j]] = [lista[j], lista[i]];
  }
  return lista;
}
