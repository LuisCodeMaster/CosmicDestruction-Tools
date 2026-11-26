#!/usr/bin/env python3
"""
cd_ps3 - traz as animações de um pacote do PS3 (.ps3, "vaps") para o formato do PSP (.psp, "spav")
Ben 10 Ultimate Alien: Cosmic Destruction

O pacote do PS3 é o mesmo formato do PSP com a ordem dos bytes invertida (big-endian).
Este programa converte só o que já sabemos converter com segurança:
    bloco 12 = esqueleto, bloco 13 = cabeçalhos de animação, bloco 9 = trilhas.
Modelo 3D, texturas, materiais e sons ficam de fora (formatos diferentes no PS3).
O resultado serve de ORIGEM para o cd_anims.py (copiar/redirecionar animações para um alien do PSP);
ele não é um personagem completo para colocar no jogo.

Uso:
    python cd_ps3.py listar   g_fa.ps3                       mostra os blocos e as animações
    python cd_ps3.py animacoes g_fa.ps3 g_fa_anims.psp       converte esqueleto + animações
    python cd_ps3.py conferir g_hm.ps3 g_hm.psp              converte o PS3 e compara com o PSP do
                                                             mesmo alien (prova de que a conversão bate)
    python cd_ps3.py texto-exportar ps3_us.txt textos.txt         textos do PS3 para editar (HASH|texto)
    python cd_ps3.py texto-importar ps3_us.txt traducao.txt saida.txt   coloca a tradução no ps3_us.txt
        (os textos do PS3 são o mesmo formato do PSP com os bytes invertidos; usa o cd_tool.py)
    python cd_ps3.py golpes g_fa.ps3 g_hm.psp saida.psp [animações...]
        teste: troca animações do alien do PSP pelas do PS3, redirecionadas para o esqueleto
        dele (padrão: idle_01 walk_01 run_01 atk_close_fwd_02 atk_close_fwd_03 atk_fin_fwd_01).
        Precisa do cd_anims.py na mesma pasta.

Só usa a biblioteca padrão do Python 3.8+.
"""
import math
import struct
import sys

MANTER = (9, 12, 13)
W3_PSP = {9: 0x40003, 12: 0x40004, 13: 0x40004}      # palavra 3 do cabeçalho, como no PSP
ROT, TRANS, ESCALA, EVENTOS = b"\x10\x02", b"\x01\x04", b"\x0c\x04", b"\x0a\x09"


# ---------- troca de bytes, campo a campo ----------

def u32s(b):
    k = len(b) // 4
    return struct.pack("<%dI" % k, *struct.unpack(">%dI" % k, b[:4 * k])) + b[4 * k:]


def u16s(b):
    k = len(b) // 2
    return struct.pack("<%dH" % k, *struct.unpack(">%dH" % k, b[:2 * k])) + b[2 * k:]


def trilha(b):
    """Trilha: 2 bytes de tipo, 1 byte de modo (PS3 0x50, PSP 0x10), 1 byte, u16 n, u16 n, chaves."""
    modo = b[2:3]
    if modo == b"\x50":
        modo = b"\x10"
    out = b[:2] + modo + b[3:4] + u16s(b[4:8])
    corpo = b[8:]
    if b[:2] == ROT:                                  # chave de 8 bytes: i16 x,y,z, i8 w, u8 quadro
        k = len(corpo) // 8
        r = bytearray()
        for i in range(k):
            c = corpo[8 * i:8 * i + 8]
            r += u16s(c[:6]) + c[6:8]
        return out + bytes(r) + corpo[8 * k:]
    return out + u32s(corpo)                          # translação, escala e eventos: só u32/float


def esqueleto(b):
    """12 bytes de cabeçalho (u16, u16, u8, u8, u16, u32), n registros de 44 bytes
    (10 floats, u8 pai, u8, u16 id do osso) e registros de 32 bytes (7 floats, u16, u16)."""
    n = struct.unpack(">H", b[:2])[0]
    out = bytearray(u16s(b[:4]) + b[4:6] + u16s(b[6:8]) + u32s(b[8:12]))
    p = 12
    for _ in range(n):
        r = b[p:p + 44]
        out += u32s(r[:40]) + r[40:42] + u16s(r[42:44])
        p += 44
    while p + 32 <= len(b):
        r = b[p:p + 32]
        out += u32s(r[:28]) + u16s(r[28:32])
        p += 32
    out += u32s(b[p:])
    return bytes(out)


def cab_anim(b):
    """Nome (0x48 bytes), 4 u32, 64 u16 (ids dos ossos), triplas u32 (índices das trilhas)."""
    return b[:0x48] + u32s(b[0x48:0x58]) + u16s(b[0x58:0xD8]) + u32s(b[0xD8:])


CONVERTE = {9: trilha, 12: esqueleto, 13: cab_anim}


# ---------- pacote ----------

def subpacotes(d, e):
    w = struct.unpack_from(e + "16I", d, 0)
    t0 = 0x20 + w[11]
    r = []
    for i in range(w[2]):
        h, t, o = struct.unpack_from(e + "III", d, t0 + 12 * i)
        p = w[7] + o
        r.append((struct.unpack_from(e + "16I", d, p)[5], p, t & 0xFFFFFF))
    return w, r


def entradas(d, p, e):
    w = struct.unpack_from(e + "16I", d, p)
    t0 = p + 0x20 + w[11]
    r = []
    for i in range(w[2]):
        h, t, o = struct.unpack_from(e + "III", d, t0 + 12 * i)
        r.append((h, t, p + w[7] + o, t & 0xFFFFFF))
    return w, r


def converter_sub(d, p, tam, tipo):
    """Converte um subpacote do PS3 no próprio lugar (os tamanhos não mudam)."""
    sub = bytearray(d[p:p + tam])
    w, ents = entradas(d, p, ">")
    w = list(w)
    w[3] = W3_PSP[tipo]
    w[13] = w[14] = w[15] = 0
    sub[0:64] = struct.pack("<16I", *w)
    cap, t0 = w[8], 0x20 + w[11]
    sub[0x40:0x40 + 4 * cap] = u32s(bytes(sub[0x40:0x40 + 4 * cap]))
    sub[t0:t0 + 12 * w[2]] = u32s(bytes(sub[t0:t0 + 12 * w[2]]))
    for h, t, q, n in ents:
        o = q - p
        novo = CONVERTE[tipo](bytes(sub[o:o + n]))
        assert len(novo) == n
        sub[o:o + n] = novo
    return bytes(sub)


def montar(subs):
    """Pacote PSP (contêiner) com os subpacotes dados [(tipo, bytes)], alinhados a 256 bytes."""
    subs = sorted(subs)
    n = len(subs)
    cap = (n + 1 + 3) // 4 * 4
    tab = sorted(range(n), key=lambda i: (subs[i][0] % cap, i))
    inicios, j = [], 0
    for k in range(cap):
        inicios.append(j)
        while j < n and subs[tab[j]][0] % cap == k:
            j += 1
    corpo, offs = bytearray(), {}
    for i, (tipo, dado) in enumerate(subs):
        corpo += b"\0" * (-len(corpo) % 256)
        offs[i] = (len(corpo), len(dado))
        corpo += dado
    corpo += b"\0" * (-len(corpo) % 256)
    fim_tab = 0x40 + 4 * cap + 12 * n
    cab = fim_tab + (-fim_tab % 256)
    w = [0x76617073, 0x10003, n, 0x40008, len(corpo), 0, 0, cab, cap, n, 0x20, 0x40 + 4 * cap - 0x20, 12, 0, 0, 0]
    out = bytearray(struct.pack("<16I", *w)) + struct.pack("<%dI" % cap, *inicios)
    for i in tab:
        o, t = offs[i]
        out += struct.pack("<III", subs[i][0], t, o)
    out += b"\0" * (cab - len(out))
    return bytes(out + corpo)


def converter(d):
    if d[:4] != b"vaps":
        raise SystemExit("Não é um pacote do PS3 (a assinatura não é 'vaps').")
    _, subs = subpacotes(d, ">")
    return montar([(tipo, converter_sub(d, p, tam, tipo)) for tipo, p, tam in subs if tipo in MANTER])


# ---------- leitura (LE ou BE) para listar e conferir ----------

def ler(d):
    e = ">" if d[:4] == b"vaps" else "<"
    _, subs = subpacotes(d, e)
    r = {}
    for tipo, p, tam in subs:
        _, ents = entradas(d, p, e)
        r[tipo] = [(h, d[q:q + n]) for h, t, q, n in ents]
    return r


def nome(cab):
    return cab[:0x48].split(b"\0")[0].decode("latin-1")


def listar(caminho):
    d = open(caminho, "rb").read()
    r = ler(d)
    print("%s (%s)" % (caminho, "PS3" if d[:4] == b"vaps" else "PSP"))
    for tipo in sorted(r):
        print("  bloco %2d: %5d entradas, %8d bytes%s" % (tipo, len(r[tipo]), sum(len(x) for _, x in r[tipo]),
                                                        "  (convertido)" if tipo in MANTER else ""))
    e = ">" if d[:4] == b"vaps" else "<"
    nomes = sorted(nome(x) for _, x in r.get(13, []))
    print("  %d animações: %s" % (len(nomes), ", ".join(nomes)))


def conferir(c_ps3, c_psp):
    """Converte o PS3 e compara com o PSP do mesmo alien."""
    novo = ler(converter(open(c_ps3, "rb").read()))
    psp = ler(open(c_psp, "rb").read())
    ok = True
    # trilhas com o mesmo hash e o mesmo tamanho devem ficar iguais (o PSP às vezes tem menos chaves)
    a = {h: x for h, x in psp[9]}
    b = {h: x for h, x in novo[9]}
    mesmos = [h for h in a if h in b and len(a[h]) == len(b[h])]
    iguais = sum(a[h] == b[h] for h in mesmos)
    quase = sum(a[h] != b[h] and perto(a[h], b[h]) for h in mesmos)
    print("trilhas: %d iguais, %d com diferença mínima de arredondamento, %d diferentes (de %d comparáveis)"
          % (iguais, quase, len(mesmos) - iguais - quase, len(mesmos)))
    ok &= iguais + quase == len(mesmos)
    ea, eb = psp[12][0][1], novo[12][0][1]
    print("esqueleto: %s" % ("igual (só arredondamento)" if len(ea) == len(eb) and perto(ea, eb, 0.01) else "DIFERENTE"))
    ok &= len(ea) == len(eb) and perto(ea, eb, 0.01)
    ca = {h: x for h, x in psp[13]}
    cb = {h: x for h, x in novo[13]}
    bate = 0
    for h in ca:
        if h in cb:
            x, y = ca[h], cb[h]
            nt = struct.unpack_from("<I", x, 0x48)[0]
            # (depois do nome há bytes de lixo da ferramenta original; só o nome conta)
            if (nome(x) == nome(y) and x[0x48:0x50] == y[0x48:0x50] and x[0x54:0x58] == y[0x54:0x58]
                    and x[0x58:0x58 + 2 * nt] == y[0x58:0x58 + 2 * nt]):
                bate += 1
    print("cabeçalhos de animação: %d de %d com nome, ossos e esqueleto iguais" % (bate, len(ca)))
    ok &= bate == len([h for h in ca if h in cb])
    print("RESULTADO: %s" % ("a conversão bate com o PSP" if ok else "há diferenças: não use ainda"))
    return ok


def perto(a, b, tol=0.002):
    if len(a) != len(b):
        return False
    for i in range(0, len(a) // 4 * 4, 4):
        if a[i:i + 4] != b[i:i + 4]:
            x, y = struct.unpack("<f", a[i:i + 4])[0], struct.unpack("<f", b[i:i + 4])[0]
            if not (math.isfinite(x) and math.isfinite(y) and abs(x - y) <= tol):
                return False
    return True


def texto_trocar(d, de, para):
    """Arquivo de textos: assinatura, depois [hash][tamanho][texto]; troca a ordem dos bytes."""
    out = bytearray(struct.pack(para + "I", struct.unpack(de + "I", d[:4])[0]))
    p = 4
    while p + 8 <= len(d):
        h, n = struct.unpack_from(de + "II", d, p)
        if p + 8 + n > len(d):
            break
        out += struct.pack(para + "II", h, n) + d[p + 8:p + 8 + n]
        p += 8 + n
    return bytes(out) + d[p:]


def texto(acao, args):
    import os
    import subprocess
    import tempfile
    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cd_tool.py")
    d = open(args[0], "rb").read()
    if d[:4] != b"\x1b\xad\xba\xbe":
        raise SystemExit("%s não é um arquivo de textos do PS3." % args[0])
    with tempfile.TemporaryDirectory() as tmp:
        le = os.path.join(tmp, "le.txt")
        open(le, "wb").write(texto_trocar(d, ">", "<"))
        if acao == "texto-exportar":
            subprocess.run([sys.executable, tool, "texto-exportar", le, args[1]], check=True)
        else:
            saida = os.path.join(tmp, "saida.txt")
            subprocess.run([sys.executable, tool, "texto-importar", le, args[1], saida], check=True)
            open(args[2], "wb").write(texto_trocar(open(saida, "rb").read(), "<", ">"))
            print("%s criado (formato do PS3 e do Xbox 360, %d bytes)." % (args[2], os.path.getsize(args[2])))


TESTE = ["idle_01", "walk_01", "run_01", "atk_close_fwd_02", "atk_close_fwd_03", "atk_fin_fwd_01"]


def golpes(c_ps3, c_psp, saida, nomes):
    import os
    import tempfile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cd_anims as ca
    with tempfile.TemporaryDirectory() as tmp:
        conv = os.path.join(tmp, "origem.psp")
        open(conv, "wb").write(converter(open(c_ps3, "rb").read()))
        o, d = ca.Pacote(conv), ca.Pacote(c_psp)
        faltam = [n for n in nomes if n not in o.anims or n not in d.anims]
        if faltam:
            raise SystemExit("Estas animações não existem nos dois pacotes: %s" % ", ".join(faltam))
        ca.copiar(o, d, [(n, n) for n in nomes], esqueletos=(ca.esqueleto_do_pacote(o), ca.esqueleto_do_pacote(d)))
        out = ca.salvar(d, saida)
    print("%s criado (%d bytes): %d animações de %s no esqueleto de %s." % (saida, len(out), len(nomes), o.prefixo, d.prefixo))


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "listar":
        listar(a[1])
    elif len(a) == 3 and a[0] == "animacoes":
        out = converter(open(a[1], "rb").read())
        open(a[2], "wb").write(out)
        print("%s criado (%d bytes)." % (a[2], len(out)))
        listar(a[2])
    elif len(a) == 3 and a[0] == "texto-exportar":
        texto(a[0], a[1:])
    elif len(a) == 4 and a[0] == "texto-importar":
        texto(a[0], a[1:])
    elif len(a) >= 4 and a[0] == "golpes":
        golpes(a[1], a[2], a[3], a[4:] or TESTE)
    elif len(a) == 3 and a[0] == "conferir":
        sys.exit(0 if conferir(a[1], a[2]) else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
