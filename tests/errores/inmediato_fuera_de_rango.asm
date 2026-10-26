addi x1, x2, 4096
addi x1, x2, 0x7FF
slli x1, x2, 32
lui t0, 0x100000
sw t0, 2048(sp)
li t0, 0x100000000
