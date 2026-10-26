#!/bin/sh
# Compara la salida de assembler.py con la del ensamblador de GNU (sección 7 del PDF).
# Uso: sh tests/comparar_con_gnu.sh programa.asm
# Funciona con riscv64-unknown-elf-* (Linux) o riscv64-elf-* (Homebrew en Mac).
set -e
if command -v riscv64-unknown-elf-as >/dev/null 2>&1; then P=riscv64-unknown-elf; else P=riscv64-elf; fi
tmp=$(mktemp -d)
"$P-as" -march=rv32i -mabi=ilp32 -mno-relax "$1" -o "$tmp/programa.o"
"$P-ld" -m elf32lriscv -Ttext=0 -Tdata=0x10000000 -e 0 "$tmp/programa.o" -o "$tmp/programa.elf"
"$P-objcopy" -O binary -j .text "$tmp/programa.elf" "$tmp/programa.bin"
# Igual que 'od -An -v -tx4 -w4', pero también funciona con el od de macOS
python3 -c 'import sys; b=open(sys.argv[1],"rb").read(); [print(format(int.from_bytes(b[i:i+4],"little"),"08x")) for i in range(0,len(b),4)]' "$tmp/programa.bin" > "$tmp/esperado.hex"
python3 "$(dirname "$0")/../assembler.py" "$1" "$tmp/programa.hex"
if diff "$tmp/esperado.hex" "$tmp/programa.hex"; then echo "iguales: $1"; fi
rm -rf "$tmp"
