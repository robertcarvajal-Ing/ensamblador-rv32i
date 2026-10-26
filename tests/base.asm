# Todas las instrucciones base de RV32I (menos fence)
# Usa registros por número y por nombre ABI, e inmediatos en decimal, hex y binario.
        .text
inicio:
        # R
        add   x1, x2, x3
        sub   t0, t1, t2
        sll   s0, s1, a0
        slt   a1, a2, a3
        sltu  a4, a5, a6
        xor   a7, s2, s3
        srl   s4, s5, s6
        sra   s7, s8, s9
        or    s10, s11, t3
        and   t4, t5, t6
        # I aritméticas
        addi  x31, x0, -2048
        addi  sp, sp, 2047
        slti  gp, tp, -1
        sltiu fp, zero, 0xFF
        xori  ra, ra, 0b1010
        ori   t0, t0, 0x7FF
        andi  t1, t1, -0x10
        slli  a0, a0, 0
        srli  a1, a1, 31
        srai  a2, a2, 5
        # I cargas
        lb    t0, 0(sp)
        lh    t1, -2(sp)
        lw    t2, 8(sp)
        lbu   t3, 2047(s0)
        lhu   t4, (a0)
        # I otras
        jalr  ra, 0(t0)
        jalr  x0, 4(a1)
        jalr  t1, t2, -8
        ecall
        ebreak
        # S
        sb    t0, -2048(sp)
        sh    t1, 2(sp)
        sw    t2, (a0)
        # B (hacia atrás y hacia adelante)
atras:  beq   x1, x2, atras
        bne   t0, t1, adelante
        blt   a0, a1, inicio
        bge   a2, a3, adelante
        bltu  s0, s1, atras
        bgeu  s2, s3, adelante
        # U
        lui   t0, 0x12345
        lui   t1, 0xFFFFF
        auipc t2, 0
        auipc a0, 1
        # J
adelante:
        jal   ra, inicio
        jal   x0, adelante
        jal   t0, fin
fin:    jal   zero, fin
