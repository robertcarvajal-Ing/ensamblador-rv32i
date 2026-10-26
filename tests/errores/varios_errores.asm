# El ensamblador reporta todos los errores, no solo el primero
main:  addi x1, x2, 4096
       foo  x1
       beq  x1, x2, nowhere
main:  nop
       slli x1, x2, 32
