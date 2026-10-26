# Todas las pseudoinstrucciones de la sección 5.2
        .text
main:
        nop
        mv    a0, a1
        not   t0, t1
        neg   t2, t3
        seqz  a2, a3
        snez  a4, a5
        sltz  a6, a7
        sgtz  s0, s1
        beqz  a0, main
        bnez  a0, destino
        blez  a1, main
        bgez  a1, destino
        bltz  a2, main
        bgtz  a2, destino
        bgt   a0, a1, main
        ble   a0, a1, destino
        bgtu  a2, a3, main
        bleu  a2, a3, destino
        j     main
        jal   destino
        jr    t0
        jalr  t1
        ret
        # li: una instrucción (cabe en 12 bits)
        li    t0, 0
        li    t0, -2048
        li    t0, 2047
        li    t0, 0xFFFFFFFF
        # li: solo lui (lo = 0)
        li    t1, 0x12345000
        li    t1, 0x80000000
        # li: lui + addi
        li    t2, 2048
        li    t2, 0x12345678
        li    t2, 0x12345FFF
        li    t2, 0x7FFFFFFF
        li    t2, -2049
        # símbolos (auipc + segunda instrucción)
        la    a0, numero
        lb    a1, letra
        lh    a2, medio
        lw    a3, numero
        sb    a1, letra, t0
        sh    a2, medio, t1
        sw    a3, numero, t2
        la    a4, main
        call  subrutina
        tail  subrutina
destino:
        nop
subrutina:
        ret

        .data
numero: .word 42, -1, 0x12345678
medio:  .half 7, -2
letra:  .byte 65, 0xFF, 0b1
mensaje: .string "hola # no es comentario\n"
