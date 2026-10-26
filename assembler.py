"""Ensamblador RV32I.

Uso:
    python assembler.py programa.asm programa.hex [programa.data.hex]

Lee un archivo en lenguaje ensamblador RISC-V (RV32I) y escribe un archivo
de texto con una instrucción de 32 bits por línea, en hexadecimal.
"""

import re
import sys


# ---------------------------------------------------------------------------
# 1. Tablas: instrucciones y registros
# ---------------------------------------------------------------------------

INST = {
    # (Type, Opcode, funct3, funct7)
    "add":  ("R", "0110011", "000", "0000000"),
    "sub":  ("R", "0110011", "000", "0100000"),
    "xor":  ("R", "0110011", "100", "0000000"),
    "or":   ("R", "0110011", "110", "0000000"),
    "and":  ("R", "0110011", "111", "0000000"),
    "sll":  ("R", "0110011", "001", "0000000"),
    "srl":  ("R", "0110011", "101", "0000000"),
    "sra":  ("R", "0110011", "101", "0100000"),
    "slt":  ("R", "0110011", "010", "0000000"),
    "sltu": ("R", "0110011", "011", "0000000"),
    # I aritméticas
    "addi":  ("I", "0010011", "000", None),
    "xori":  ("I", "0010011", "100", None),
    "ori":   ("I", "0010011", "110", None),
    "andi":  ("I", "0010011", "111", None),
    "slti":  ("I", "0010011", "010", None),
    "sltiu": ("I", "0010011", "011", None),
    "slli":  ("I", "0010011", "001", "0000000"),
    "srli":  ("I", "0010011", "101", "0000000"),
    "srai":  ("I", "0010011", "101", "0100000"),
    # I loads
    "lb":  ("I", "0000011", "000", None),
    "lh":  ("I", "0000011", "001", None),
    "lw":  ("I", "0000011", "010", None),
    "lbu": ("I", "0000011", "100", None),
    "lhu": ("I", "0000011", "101", None),
    # I otras
    "jalr":   ("I", "1100111", "000", None),
    "ecall":  ("I", "1110011", "000", None),
    "ebreak": ("I", "1110011", "000", None),
    # S
    "sb": ("S", "0100011", "000", None),
    "sh": ("S", "0100011", "001", None),
    "sw": ("S", "0100011", "010", None),
    # B
    "beq":  ("B", "1100011", "000", None),
    "bne":  ("B", "1100011", "001", None),
    "blt":  ("B", "1100011", "100", None),
    "bge":  ("B", "1100011", "101", None),
    "bltu": ("B", "1100011", "110", None),
    "bgeu": ("B", "1100011", "111", None),
    # U
    "lui":   ("U", "0110111", None, None),
    "auipc": ("U", "0010111", None, None),
    # J
    "jal": ("J", "1101111", None, None),
}

CARGAS = ("lb", "lh", "lw", "lbu", "lhu")
ALMACENAMIENTOS = ("sb", "sh", "sw")
DESPLAZAMIENTOS = ("slli", "srli", "srai")

# Nombres ABI de los registros. Además se aceptan x0 a x31 (ver registro()).
REGISTROS = {
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7,
    "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13,
    "a4": 14, "a5": 15, "a6": 16, "a7": 17,
    "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22, "s7": 23,
    "s8": 24, "s9": 25, "s10": 26, "s11": 27,
    "t3": 28, "t4": 29, "t5": 30, "t6": 31,
}

# Pseudoinstrucciones de una sola instrucción que solo reordenan registros.
# nombre: (instrucción base, cómo se arman sus operandos a partir de rd/rs)
PSEUDO_REG = {
    "mv":   ("addi",  "rd rs 0"),
    "not":  ("xori",  "rd rs -1"),
    "neg":  ("sub",   "rd x0 rs"),
    "seqz": ("sltiu", "rd rs 1"),
    "snez": ("sltu",  "rd x0 rs"),
    "sltz": ("slt",   "rd rs x0"),
    "sgtz": ("slt",   "rd x0 rs"),
}

# Bifurcaciones contra cero: beqz rs, L  ->  beq rs, x0, L
PSEUDO_CERO = {
    "beqz": ("beq", "rs x0"),
    "bnez": ("bne", "rs x0"),
    "blez": ("bge", "x0 rs"),
    "bgez": ("bge", "rs x0"),
    "bltz": ("blt", "rs x0"),
    "bgtz": ("blt", "x0 rs"),
}

# Bifurcaciones con los registros invertidos: bgt rs, rt, L -> blt rt, rs, L
PSEUDO_INVERTIDA = {"bgt": "blt", "ble": "bge", "bgtu": "bltu", "bleu": "bgeu"}

DIR_TEXT = 0x00000000
DIR_DATA = 0x10000000

ETIQUETA = re.compile(r"^[A-Za-z_.$][\w.$]*$")
NUMERO = re.compile(r"^[+-]?(0x[0-9a-f]+|0b[01]+|[0-9]+)$", re.IGNORECASE)
MEMORIA = re.compile(r"^(.*)\(\s*([^()]*?)\s*\)$")


class ErrorEnsamblador(Exception):
    """Un error en una línea del programa. Lo atrapa ensamblar()."""


# ---------------------------------------------------------------------------
# 2. Lectura de operandos
# ---------------------------------------------------------------------------

def registro(texto):
    texto = texto.strip()
    if texto in REGISTROS:
        return REGISTROS[texto]
    if re.fullmatch(r"x([0-9]|[12][0-9]|3[01])", texto):
        return int(texto[1:])
    if es_numero(texto):
        raise ErrorEnsamblador(f"se esperaba un registro y se encontró '{texto}'")
    raise ErrorEnsamblador(f"registro '{texto}' no existe")


def es_numero(texto):
    return NUMERO.match(texto.strip()) is not None


def inmediato(texto):
    texto = texto.strip()
    if not es_numero(texto):
        raise ErrorEnsamblador(f"se esperaba un inmediato y se encontró '{texto}'")
    # int(texto, 0) entiende 42, -12, 0xFF y 0b1010
    return int(texto, 0)


def comprobar_rango(valor, minimo, maximo, que="inmediato"):
    if not minimo <= valor <= maximo:
        raise ErrorEnsamblador(f"{que} {valor} fuera de rango [{minimo}, {maximo}]")
    return valor


def memoria(texto):
    """Lee 'desplazamiento(registro)'. Si no hay desplazamiento vale 0."""
    m = MEMORIA.match(texto.strip())
    if not m:
        raise ErrorEnsamblador(f"se esperaba desplazamiento(registro) y se encontró '{texto.strip()}'")
    desplazamiento = m.group(1).strip()
    imm = inmediato(desplazamiento) if desplazamiento else 0
    return imm, registro(m.group(2))


def direccion_etiqueta(texto, etiquetas):
    texto = texto.strip()
    if not ETIQUETA.match(texto):
        raise ErrorEnsamblador(f"se esperaba una etiqueta y se encontró '{texto}'")
    if texto not in etiquetas:
        raise ErrorEnsamblador(f"etiqueta '{texto}' no definida")
    return etiquetas[texto]


def esperar(nombre, operandos, cantidad, forma):
    if len(operandos) != cantidad:
        raise ErrorEnsamblador(
            f"'{nombre}' espera {cantidad} operandos ({forma}) y recibió {len(operandos)}")


def partir_32(valor):
    """Divide un valor de 32 bits en parte alta (20 bits) y baja (12 bits).

    Se suma 0x800 porque la parte baja se extiende con signo: si su bit 11
    es 1, vale negativo y la parte alta debe ser una unidad mayor.
    """
    hi = (valor + 0x800) >> 12
    lo = valor - (hi << 12)
    return hi & 0xFFFFF, lo


# ---------------------------------------------------------------------------
# 3. Codificación: de campos a bits (una función por formato)
# ---------------------------------------------------------------------------

def bits(valor, ancho):
    """Número a binario de 'ancho' bits. Los negativos quedan en complemento a dos."""
    return format(valor & ((1 << ancho) - 1), f"0{ancho}b")


def manager(nombre, rd=0, rs1=0, rs2=0, imm=0):
    """Devuelve los 32 bits (como texto) de una instrucción base."""
    if nombre not in INST:
        raise ErrorEnsamblador(f"instrucción inválida '{nombre}'")

    tipo, opcode, funct3, funct7 = INST[nombre]

    if tipo == "R":
        bit_line = assembler_R(funct7, rs2, rs1, funct3, rd, opcode)
    elif tipo == "I":
        if nombre == "ecall":
            bit_line = assembler_I(0, 0, funct3, 0, opcode)
        elif nombre == "ebreak":
            bit_line = assembler_I(1, 0, funct3, 0, opcode)
        else:
            bit_line = assembler_I(imm, rs1, funct3, rd, opcode, funct7)
    elif tipo == "S":
        bit_line = assembler_S(imm, rs2, rs1, funct3, opcode)
    elif tipo == "B":
        bit_line = assembler_B(imm, rs2, rs1, funct3, opcode)
    elif tipo == "U":
        bit_line = assembler_U(imm, rd, opcode)
    else:
        bit_line = assembler_J(imm, rd, opcode)

    assert len(bit_line) == 32, (nombre, bit_line)
    return bit_line


def assembler_R(funct7, rs2, rs1, funct3, rd, opcode):
    return funct7 + bits(rs2, 5) + bits(rs1, 5) + funct3 + bits(rd, 5) + opcode


def assembler_I(imm, rs1, funct3, rd, opcode, funct7=None):
    if funct7 is None:
        imm_bin = bits(imm, 12)
    else:
        # slli, srli, srai: los 7 bits altos son funct7 y los 5 bajos el shamt
        imm_bin = funct7 + bits(imm, 5)
    return imm_bin + bits(rs1, 5) + funct3 + bits(rd, 5) + opcode


def assembler_S(imm, rs2, rs1, funct3, opcode):
    imm = bits(imm, 12)            # imm[11:0], imm[0] es el bit 11
    imm_high = imm[:7]             # imm[11:5]
    imm_low = imm[7:]              # imm[4:0]
    return imm_high + bits(rs2, 5) + bits(rs1, 5) + funct3 + imm_low + opcode


def assembler_B(imm, rs2, rs1, funct3, opcode):
    imm = bits(imm, 13)            # imm[12:0]; el bit 0 siempre es 0 y no se guarda
    imm12 = imm[0]
    imm11 = imm[1]
    imm10_5 = imm[2:8]
    imm4_1 = imm[8:12]
    return (imm12 + imm10_5 + bits(rs2, 5) + bits(rs1, 5) + funct3
            + imm4_1 + imm11 + opcode)


def assembler_U(imm, rd, opcode):
    return bits(imm, 20) + bits(rd, 5) + opcode


def assembler_J(imm, rd, opcode):
    imm = bits(imm, 21)            # imm[20:0]; el bit 0 no se guarda
    imm20 = imm[0]
    imm19_12 = imm[1:9]
    imm11 = imm[9]
    imm10_1 = imm[10:20]
    return imm20 + imm10_1 + imm11 + imm19_12 + bits(rd, 5) + opcode


# ---------------------------------------------------------------------------
# 4. Traducción de una línea: de texto a una o dos instrucciones base
# ---------------------------------------------------------------------------

def es_simbolo(texto):
    """True si el operando es una etiqueta (y no un número ni d(reg))."""
    texto = texto.strip()
    return ETIQUETA.match(texto) is not None and not es_numero(texto)


def tamano(nombre, operandos):
    """Cuántas instrucciones de 32 bits ocupa una línea (primera pasada)."""
    if nombre in ("la", "call", "tail"):
        return 2
    if nombre in CARGAS and len(operandos) == 2 and es_simbolo(operandos[1]):
        return 2
    if nombre in ALMACENAMIENTOS and len(operandos) == 3:
        return 2
    if nombre == "li" and len(operandos) == 2:
        try:
            valor = valor_li(operandos[1])
        except ErrorEnsamblador:
            return 1                  # el error se reporta en la segunda pasada
        if -2048 <= valor <= 2047 or partir_32(valor)[1] == 0:
            return 1
        return 2
    return 1


def valor_li(texto):
    """Inmediato de li como valor de 32 bits con signo (0xFFFFFFFF -> -1)."""
    valor = comprobar_rango(inmediato(texto), -2**31, 2**32 - 1)
    return valor - 2**32 if valor >= 2**31 else valor


def desplazamiento_salto(destino, pc, ancho):
    """Distancia de un salto (B: 13 bits, J: 21 bits) con su rango comprobado."""
    offset = destino - pc
    limite = 1 << (ancho - 1)
    if not -limite <= offset <= limite - 2:
        raise ErrorEnsamblador(
            f"destino del salto demasiado lejos: desplazamiento {offset} "
            f"fuera de rango [{-limite}, {limite - 2}]")
    return offset


def traducir(nombre, ops, pc, etiquetas):
    """Devuelve la lista de bit_lines (32 bits cada una) de una línea."""

    # --- Pseudoinstrucciones -------------------------------------------
    if nombre == "nop":
        esperar(nombre, ops, 0, "sin operandos")
        return [manager("addi", rd=0, rs1=0, imm=0)]

    if nombre in PSEUDO_REG:
        base, forma = PSEUDO_REG[nombre]
        esperar(nombre, ops, 2, "rd, rs")
        valores = {"rd": registro(ops[0]), "rs": registro(ops[1]), "x0": 0}
        a, b, c = forma.split()
        if INST[base][0] == "R":
            return [manager(base, rd=valores[a], rs1=valores[b], rs2=valores[c])]
        return [manager(base, rd=valores[a], rs1=valores[b], imm=int(c))]

    if nombre in PSEUDO_CERO:
        base, forma = PSEUDO_CERO[nombre]
        esperar(nombre, ops, 2, "rs, etiqueta")
        valores = {"rs": registro(ops[0]), "x0": 0}
        a, b = forma.split()
        return traducir(base, [f"x{valores[a]}", f"x{valores[b]}", ops[1]], pc, etiquetas)

    if nombre in PSEUDO_INVERTIDA:
        esperar(nombre, ops, 3, "rs, rt, etiqueta")
        return traducir(PSEUDO_INVERTIDA[nombre], [ops[1], ops[0], ops[2]], pc, etiquetas)

    if nombre == "j":
        esperar(nombre, ops, 1, "etiqueta")
        return traducir("jal", ["x0", ops[0]], pc, etiquetas)

    if nombre == "jr":
        esperar(nombre, ops, 1, "rs")
        return [manager("jalr", rd=0, rs1=registro(ops[0]), imm=0)]

    if nombre == "ret":
        esperar(nombre, ops, 0, "sin operandos")
        return [manager("jalr", rd=0, rs1=1, imm=0)]

    if nombre == "li":
        esperar(nombre, ops, 2, "rd, inmediato")
        rd = registro(ops[0])
        valor = valor_li(ops[1])
        if -2048 <= valor <= 2047:
            return [manager("addi", rd=rd, rs1=0, imm=valor)]
        hi, lo = partir_32(valor)
        if lo == 0:
            return [manager("lui", rd=rd, imm=hi)]
        return [manager("lui", rd=rd, imm=hi), manager("addi", rd=rd, rs1=rd, imm=lo)]

    # Pseudoinstrucciones de dos instrucciones con auipc: v = S - PC(auipc)
    if nombre in ("la", "call", "tail") or (
            nombre in CARGAS and len(ops) == 2 and es_simbolo(ops[1])) or (
            nombre in ALMACENAMIENTOS and len(ops) == 3):
        if nombre == "la":
            esperar(nombre, ops, 2, "rd, símbolo")
            rd = registro(ops[0])
            hi, lo = partir_32(direccion_etiqueta(ops[1], etiquetas) - pc)
            return [manager("auipc", rd=rd, imm=hi), manager("addi", rd=rd, rs1=rd, imm=lo)]
        if nombre in CARGAS:
            rd = registro(ops[0])
            hi, lo = partir_32(direccion_etiqueta(ops[1], etiquetas) - pc)
            return [manager("auipc", rd=rd, imm=hi), manager(nombre, rd=rd, rs1=rd, imm=lo)]
        if nombre in ALMACENAMIENTOS:
            rs, rt = registro(ops[0]), registro(ops[2])
            hi, lo = partir_32(direccion_etiqueta(ops[1], etiquetas) - pc)
            return [manager("auipc", rd=rt, imm=hi), manager(nombre, rs1=rt, rs2=rs, imm=lo)]
        esperar(nombre, ops, 1, "etiqueta")
        hi, lo = partir_32(direccion_etiqueta(ops[0], etiquetas) - pc)
        if nombre == "call":
            return [manager("auipc", rd=1, imm=hi), manager("jalr", rd=1, rs1=1, imm=lo)]
        return [manager("auipc", rd=6, imm=hi), manager("jalr", rd=0, rs1=6, imm=lo)]

    # --- Instrucciones base -------------------------------------------
    if nombre not in INST:
        raise ErrorEnsamblador(f"instrucción inválida '{nombre}'")

    tipo = INST[nombre][0]

    if tipo == "R":
        esperar(nombre, ops, 3, "rd, rs1, rs2")
        return [manager(nombre, rd=registro(ops[0]), rs1=registro(ops[1]), rs2=registro(ops[2]))]

    if nombre in ("ecall", "ebreak"):
        esperar(nombre, ops, 0, "sin operandos")
        return [manager(nombre)]

    if nombre == "jalr":
        # jalr rs | jalr rd, imm(rs1) | jalr rd, rs1, imm
        if len(ops) == 1:
            return [manager("jalr", rd=1, rs1=registro(ops[0]), imm=0)]
        if len(ops) == 2:
            imm, rs1 = memoria(ops[1])
        else:
            esperar(nombre, ops, 3, "rd, rs1, inmediato")
            rs1, imm = registro(ops[1]), inmediato(ops[2])
        comprobar_rango(imm, -2048, 2047)
        return [manager("jalr", rd=registro(ops[0]), rs1=rs1, imm=imm)]

    if nombre in CARGAS:
        esperar(nombre, ops, 2, "rd, desplazamiento(rs1)")
        rd = registro(ops[0])
        imm, rs1 = memoria(ops[1])
        comprobar_rango(imm, -2048, 2047)
        return [manager(nombre, rd=rd, rs1=rs1, imm=imm)]

    if tipo == "I":
        esperar(nombre, ops, 3, "rd, rs1, inmediato")
        rd, rs1, imm = registro(ops[0]), registro(ops[1]), inmediato(ops[2])
        if nombre in DESPLAZAMIENTOS:
            comprobar_rango(imm, 0, 31, "desplazamiento")
        else:
            comprobar_rango(imm, -2048, 2047)
        return [manager(nombre, rd=rd, rs1=rs1, imm=imm)]

    if tipo == "S":
        esperar(nombre, ops, 2, "rs2, desplazamiento(rs1)")
        rs2 = registro(ops[0])
        imm, rs1 = memoria(ops[1])
        comprobar_rango(imm, -2048, 2047)
        return [manager(nombre, rs1=rs1, rs2=rs2, imm=imm)]

    if tipo == "B":
        esperar(nombre, ops, 3, "rs1, rs2, etiqueta")
        rs1, rs2 = registro(ops[0]), registro(ops[1])
        offset = desplazamiento_salto(direccion_etiqueta(ops[2], etiquetas), pc, 13)
        return [manager(nombre, rs1=rs1, rs2=rs2, imm=offset)]

    if tipo == "U":
        esperar(nombre, ops, 2, "rd, inmediato")
        rd = registro(ops[0])
        imm = comprobar_rango(inmediato(ops[1]), 0, 0xFFFFF)
        return [manager(nombre, rd=rd, imm=imm)]

    # tipo J: jal L  |  jal rd, L
    if len(ops) == 1:
        rd, destino = 1, ops[0]
    else:
        esperar(nombre, ops, 2, "rd, etiqueta")
        rd, destino = registro(ops[0]), ops[1]
    offset = desplazamiento_salto(direccion_etiqueta(destino, etiquetas), pc, 21)
    return [manager("jal", rd=rd, imm=offset)]


# ---------------------------------------------------------------------------
# 5. Lectura del archivo: comentarios, etiquetas, directivas
# ---------------------------------------------------------------------------

def quitar_comentario(linea):
    """Corta desde '#' hasta el final, salvo que el '#' esté dentro de comillas."""
    dentro = False
    for i, c in enumerate(linea):
        if c == '"' and (i == 0 or linea[i - 1] != "\\"):
            dentro = not dentro
        elif c == "#" and not dentro:
            return linea[:i]
    return linea


def separar_operandos(texto):
    texto = texto.strip()
    if texto == "":
        return []
    operandos = [op.strip() for op in texto.split(",")]
    if "" in operandos:
        raise ErrorEnsamblador("sintaxis incorrecta: operando vacío (revise las comas)")
    return operandos


def leer_cadena(texto):
    """Convierte '"hola\\n"' en los bytes de la cadena, terminada en 0."""
    texto = texto.strip()
    if len(texto) < 2 or texto[0] != '"' or texto[-1] != '"':
        raise ErrorEnsamblador("sintaxis incorrecta: .string espera un texto entre comillas")
    escapes = {"n": 10, "t": 9, "r": 13, "0": 0, "\\": 92, '"': 34}
    resultado = bytearray()
    i = 1
    while i < len(texto) - 1:
        c = texto[i]
        if c == "\\":
            i += 1
            if texto[i] not in escapes:
                raise ErrorEnsamblador(f"sintaxis incorrecta: secuencia de escape '\\{texto[i]}' no soportada")
            resultado.append(escapes[texto[i]])
        else:
            resultado.extend(c.encode("utf-8"))
        i += 1
    resultado.append(0)
    return bytes(resultado)


TAMANO_DATO = {".word": 4, ".half": 2, ".byte": 1}


def ensamblar(lineas):
    """Ensambla una lista de líneas.

    Devuelve (errores, palabras_text, bytes_data). errores es una lista de
    (número_de_línea, mensaje); si no está vacía, lo demás no sirve.
    """
    errores = []
    etiquetas = {}
    instrucciones = []   # (línea, pc, nombre, operandos)
    datos = []           # (línea, dirección, directiva, operandos)

    # ---- Primera pasada: direcciones de cada etiqueta -----------------
    segmento = ".text"
    pc = {".text": DIR_TEXT, ".data": DIR_DATA}

    for num, linea in enumerate(lineas, start=1):
        try:
            resto = quitar_comentario(linea).strip()

            # Una o varias etiquetas al inicio:  loop:   o   loop: addi ...
            while True:
                m = re.match(r"^([^\s:,()\"]+)\s*:\s*(.*)$", resto)
                if not m:
                    break
                nombre_etiqueta, resto = m.group(1), m.group(2)
                if not ETIQUETA.match(nombre_etiqueta) or es_numero(nombre_etiqueta):
                    raise ErrorEnsamblador(f"sintaxis incorrecta: '{nombre_etiqueta}' no es un nombre de etiqueta válido")
                if nombre_etiqueta in etiquetas:
                    raise ErrorEnsamblador(f"etiqueta '{nombre_etiqueta}' duplicada")
                etiquetas[nombre_etiqueta] = pc[segmento]

            if resto == "":
                continue

            partes = resto.split(None, 1)
            nombre = partes[0].lower()
            argumentos = partes[1] if len(partes) > 1 else ""

            if nombre in (".text", ".data"):
                if argumentos.strip():
                    raise ErrorEnsamblador(f"sintaxis incorrecta: {nombre} no lleva argumentos")
                segmento = nombre
            elif nombre in (".globl", ".global"):
                pass                            # no afecta la salida
            elif nombre in TAMANO_DATO or nombre == ".string":
                if segmento != ".data":
                    raise ErrorEnsamblador(f"sintaxis incorrecta: {nombre} solo se permite en .data")
                if nombre == ".string":
                    valores = leer_cadena(argumentos)
                    tam = len(valores)
                else:
                    valores = separar_operandos(argumentos)
                    if not valores:
                        raise ErrorEnsamblador(f"sintaxis incorrecta: {nombre} necesita al menos un valor")
                    tam = TAMANO_DATO[nombre] * len(valores)
                datos.append((num, pc[".data"], nombre, valores))
                pc[".data"] += tam
            elif nombre.startswith("."):
                raise ErrorEnsamblador(f"sintaxis incorrecta: directiva '{nombre}' no soportada")
            else:
                if segmento != ".text":
                    raise ErrorEnsamblador(f"sintaxis incorrecta: la instrucción '{nombre}' debe ir en .text")
                operandos = separar_operandos(argumentos)
                instrucciones.append((num, pc[".text"], nombre, operandos))
                pc[".text"] += 4 * tamano(nombre, operandos)
        except ErrorEnsamblador as e:
            errores.append((num, str(e)))

    # ---- Segunda pasada: codificar con todas las etiquetas conocidas ----
    palabras = []
    for num, direccion, nombre, operandos in instrucciones:
        try:
            bit_lines = traducir(nombre, operandos, direccion, etiquetas)
            # tamano() y traducir() deben coincidir o las etiquetas quedan corridas
            assert len(bit_lines) == tamano(nombre, operandos), (num, nombre)
            palabras.extend(int(b, 2) for b in bit_lines)
        except ErrorEnsamblador as e:
            errores.append((num, str(e)))
            palabras.extend([0] * tamano(nombre, operandos))

    memoria_datos = bytearray()
    for num, direccion, nombre, valores in datos:
        try:
            if nombre == ".string":
                memoria_datos.extend(valores)
                continue
            ancho = TAMANO_DATO[nombre]
            for v in valores:
                if es_simbolo(v):
                    valor = direccion_etiqueta(v, etiquetas)
                else:
                    valor = comprobar_rango(inmediato(v), -2**(8 * ancho - 1), 2**(8 * ancho) - 1)
                memoria_datos.extend((valor & ((1 << 8 * ancho) - 1)).to_bytes(ancho, "little"))
        except ErrorEnsamblador as e:
            errores.append((num, str(e)))

    errores.sort(key=lambda error: error[0])
    return errores, palabras, bytes(memoria_datos)


# ---------------------------------------------------------------------------
# 6. Programa principal
# ---------------------------------------------------------------------------

def escribir_hex(ruta, palabras):
    with open(ruta, "w") as archivo:
        for palabra in palabras:
            archivo.write(format(palabra, "08x") + "\n")


def main(argumentos):
    if len(argumentos) not in (3, 4):
        print("uso: python assembler.py programa.asm programa.hex [programa.data.hex]",
              file=sys.stderr)
        return 2

    entrada, salida = argumentos[1], argumentos[2]
    try:
        with open(entrada, encoding="utf-8") as archivo:
            lineas = archivo.read().splitlines()
    except OSError as e:
        print(f"{entrada}: error: no se pudo leer el archivo ({e.strerror})", file=sys.stderr)
        return 1

    errores, palabras, memoria_datos = ensamblar(lineas)

    if errores:
        for num, mensaje in errores:
            print(f"{entrada}:{num}: error: {mensaje}", file=sys.stderr)
        return 1

    escribir_hex(salida, palabras)

    if len(argumentos) == 4:
        # Segmento de datos: palabras de 4 bytes en little-endian
        relleno = memoria_datos + bytes(-len(memoria_datos) % 4)
        palabras_datos = [int.from_bytes(relleno[i:i + 4], "little")
                          for i in range(0, len(relleno), 4)]
        escribir_hex(argumentos[3], palabras_datos)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
