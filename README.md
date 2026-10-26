# Ensamblador RV32I

Ensamblador para el conjunto de instrucciones base RISC-V de 32 bits (RV32I),
escrito en Python 3 para la Entrega 1 de Arquitectura de Computadores.
Lee un programa en ensamblador y genera un archivo `.hex` con una instrucción
de 32 bits por línea, listo para cargarse en Verilog con `$readmemh`.

## Cómo ejecutarlo

Solo necesita Python 3 (probado con 3.12 y 3.13). No usa librerías externas,
por eso no hay `requirements.txt`.

```sh
python assembler.py programa.asm programa.hex
```

Bonificación (segmento `.data`, una palabra little-endian por línea desde 0x10000000):

```sh
python assembler.py programa.asm programa.hex programa.data.hex
```

Si el programa tiene errores, se imprimen todos (no solo el primero), con el
formato `archivo:línea: error: descripción`. El programa termina con código 1
y no crea el archivo de salida. Ejemplo:

```text
programa.asm:2: error: inmediato 4096 fuera de rango [-2048, 2047]
```

## Pruebas

```sh
python tests/probar.py
```

- `tests/*.asm` con su `.hex` esperado (y `.data.hex` cuando hay datos):
  - `suma.asm`: el ejemplo del enunciado.
  - `base.asm`: todas las instrucciones base de RV32I (menos `fence`).
  - `pseudo.asm`: todas las pseudoinstrucciones, incluidas `li`, `la`, `call`,
    `tail` y las cargas y almacenamientos con símbolo.
- `tests/errores/*.asm` con el mensaje esperado en `.err`: instrucción
  inválida, operandos incorrectos, registro inexistente, etiqueta no definida,
  etiqueta duplicada, inmediato fuera de rango, salto demasiado lejos, errores
  de sintaxis y un archivo con varios errores a la vez.

Los `.hex` esperados se generaron con el ensamblador de GNU. Para comparar
cualquier programa contra GNU (necesita `riscv64-unknown-elf-binutils`, o
`riscv64-elf-binutils` de Homebrew en Mac):

```sh
sh tests/comparar_con_gnu.sh tests/base.asm
```

## Diseño

Todo está en `assembler.py`, dividido en seis partes:

1. **Tablas.** `INST` guarda, para cada instrucción base, su formato
   (R, I, S, B, U, J), `opcode`, `funct3` y `funct7` como texto binario.
   `REGISTROS` traduce los nombres ABI (`zero`, `ra`, `sp`, `t0`…) a su
   número; `x0` a `x31` se aceptan directamente. Otras tablas describen las
   pseudoinstrucciones simples (`mv`, `not`, `beqz`, `bgt`…).
2. **Lectura de operandos.** `registro()`, `inmediato()` (decimal, `0x`, `0b`),
   `memoria()` para `desplazamiento(registro)` y `direccion_etiqueta()`.
   Cada una lanza `ErrorEnsamblador` con un mensaje claro si el operando no sirve.
3. **Codificación.** `manager()` recibe una instrucción base con sus campos
   ya como números y llama a `assembler_R`, `assembler_I`, `assembler_S`,
   `assembler_B`, `assembler_U` o `assembler_J`. Cada una arma los 32 bits
   como un texto de ceros y unos, en el orden de la tarjeta de referencia.
   `bits(valor, ancho)` convierte un número a binario y deja los negativos en
   complemento a dos.
4. **Traducción.** `traducir()` toma una línea ya separada (mnemónico y
   operandos), revisa operandos y rangos, expande las pseudoinstrucciones y
   devuelve una o dos instrucciones codificadas.
5. **Lectura del archivo.** `ensamblar()` quita comentarios, reconoce etiquetas
   y directivas (`.text`, `.data`, `.word`, `.half`, `.byte`, `.string`) y
   hace las dos pasadas.
6. **Programa principal.** `main()` lee los argumentos, escribe el `.hex` y
   muestra los errores.

### Cómo se resuelven las etiquetas (dos pasadas)

Un salto puede ir hacia una etiqueta que todavía no se ha leído
(`beqz a0, end` aparece antes que `end:`). Por eso el archivo se recorre dos veces:

- **Primera pasada:** se lleva un contador de direcciones para `.text`
  (desde 0x00000000) y otro para `.data` (desde 0x10000000). Cada etiqueta
  se guarda en el diccionario `etiquetas` con la dirección actual. No se
  codifica nada; solo se suma el tamaño de cada línea. `tamano()` dice cuántas
  instrucciones ocupa: 1 casi siempre, 2 para `la`, `call`, `tail` y
  cargas/almacenamientos con símbolo, y 1 o 2 para `li` según el valor.
- **Segunda pasada:** ya se conocen todas las direcciones. Para un salto se
  calcula `desplazamiento = dirección_de_la_etiqueta - PC_de_la_instrucción`
  y se codifica.

### Por qué `li`, `la` y `call` necesitan dos instrucciones

Una instrucción mide 32 bits, y una parte de ellos se usa para el opcode y
los registros. A `addi` solo le quedan 12 bits para el inmediato, así que solo
puede sumar valores entre -2048 y 2047. Un valor o una dirección de 32 bits no
cabe en una sola instrucción.

La solución es repartirlo en dos: `lui` (o `auipc`) pone los 20 bits de arriba
y luego `addi` (o `jalr`, `lw`, `sw`…) suma los 12 bits de abajo.

- `li rd, valor`: `lui` carga la parte alta y `addi` suma la baja. Si el valor
  cabe en 12 bits basta un `addi`, y si la parte baja es 0 basta un `lui`.
- `la rd, símbolo` y `call etiqueta`: no se usa la dirección absoluta sino la
  distancia desde la instrucción. `auipc` suma la parte alta de esa distancia
  al PC, y la segunda instrucción suma la parte baja. Así el programa funciona
  en cualquier dirección de memoria y `call` llega a cualquier punto, mientras
  que `jal` solo alcanza ±1 MiB.

### Por qué se suma 0x800 al calcular la parte alta

La segunda instrucción (`addi`, `jalr`…) interpreta sus 12 bits **con signo**.
Si el bit 11 de la parte baja es 1, esos 12 bits valen un número negativo, y al
sumarlos le quitan 4096 (0x1000) al resultado. Para compensar, la parte alta
debe ser una unidad mayor.

Sumar 0x800 (que es la mitad de 0x1000) antes de quedarse con los bits de
arriba hace justo eso: si el bit 11 es 1, la suma produce un acarreo hacia el
bit 12 y la parte alta sube en uno; si es 0, no cambia nada.

```text
hi = (v + 0x800) >> 12
lo = v - (hi << 12)          # siempre queda entre -2048 y 2047
```

Ejemplo: `li t0, 0x12345FFF`. Sin el 0x800 saldría `hi = 0x12345` y
`lo = 0xFFF`, pero `addi` lee 0xFFF como -1 y el resultado sería 0x12344FFF.
Con el 0x800 sale `hi = 0x12346` y `lo = -1`: 0x12346000 - 1 = 0x12345FFF.
