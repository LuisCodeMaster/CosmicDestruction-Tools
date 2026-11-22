"""cd_vozes - Ultimates gritando o próprio nome ("Ultimate Humungousaur!") em qualquer fase
do Ben 10 Ultimate Alien: Cosmic Destruction (PSP).

No jogo original cada fase só tem o grito da Ultimate que aparece num evento dela
(Roma de dia: Humungossauro; Paris: Fogo-Fátuo; China: Arctiguana; Base militar: Eco Eco;
Corrida e Tóquio à noite: Macaco-Aranha). Para valer em todas as fases são duas coisas:
  1. o som: o banco de vozes da fase (vo/vo_eng.psp, FSB4 do FMOD) ganha os gritos que
     faltam, sempre NO FIM (as falas que já existiam ficam no mesmo lugar);
  2. a fala: o script de vozes da fase (scripts/vo_<fase>.ds) tem a função das Ultimates
     (0xe8c0396d) que diz qual som tocar para cada tipo de fala; ela ganha o grito das cinco.
O cd_scripts.py (mod Ultimate) toca o grito na hora da transformação.

Uso:
  python cd_vozes.py PASTA_VOZES PASTA_SCRIPTS PASTA_SAIDA
    PASTA_VOZES   pasta extraída com PSP_GAME/USRDIR/<fase>/vo/vo_eng.psp
    PASTA_SCRIPTS pasta extraída com PSP_GAME/USRDIR/<fase>/scripts/vo_<fase>.ds
"""
import os, sys, glob, struct, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cd_scripts as C

CAB, ALINHA = 48, 32
FALA_ULTIMATES = 0xE8C0396D      # função das falas das Ultimates nos scripts vo_<fase>.ds
ULTIMATES = ["humongousaur", "spidermonkey", "bigchill", "echoecho", "swampfire"]


def crc(s):
    return zlib.crc32(s.encode())


def ler_fsb(d):
    mag, n, shs, ds, ver, modo = struct.unpack_from("<4sIIIII", d, 0)
    if mag != b"FSB4":
        raise ValueError("não é FSB4")
    amostras, off, pos = [], CAB, CAB + shs
    for _ in range(n):
        sz = struct.unpack_from("<H", d, off)[0]
        cab = d[off:off + sz]
        comp = struct.unpack_from("<I", cab, 36)[0]
        amostras.append((cab[2:32].split(b"\0")[0], cab, d[pos:pos + comp]))
        pos += (comp + ALINHA - 1) // ALINHA * ALINHA
        off += sz
    if pos != CAB + shs + ds:
        raise ValueError("tamanhos do FSB não batem")
    return d[:CAB], amostras


def escrever_fsb(cab0, amostras):
    cabs = b"".join(c for _, c, _ in amostras)
    dados = b"".join(x + b"\0" * ((-len(x)) % ALINHA) for _, _, x in amostras)
    c = bytearray(cab0)
    struct.pack_into("<III", c, 4, len(amostras), len(cabs), len(dados))
    return bytes(c) + cabs + dados


def grito_do_banco(nome):
    return nome.startswith(b"ult_") and b"name_callout" in nome


def bancos_novos(pasta):
    arquivos = sorted(glob.glob(os.path.join(pasta, "**", "vo", "vo_eng.psp"), recursive=True))
    bancos = {f: open(f, "rb").read() for f in arquivos}
    todos = {}
    for d in bancos.values():
        for a in ler_fsb(d)[1]:
            if grito_do_banco(a[0]):
                todos.setdefault(a[0], a)
    saida = {}
    for f, d in bancos.items():
        cab0, am = ler_fsb(d)
        if not any(n.startswith(b"ult_") for n, _, _ in am):
            continue                                       # banco global (menus)
        tem = {n for n, _, _ in am}
        novos = [todos[k] for k in sorted(todos) if k not in tem]
        if not novos:
            continue
        out = escrever_fsb(cab0, am + novos)               # no fim: índices antigos intactos
        _, am2 = ler_fsb(out)
        assert am2[:len(am)] == am
        saida[f] = (out, [n.decode() for n, _, _ in novos])
    return saida, sorted(n.decode() for n in todos)


def fala_nova(d, funcs):
    """Função das falas das Ultimates com o grito das cinco antes do código original."""
    corpo, npar = C.corpo_de(d, funcs, FALA_ULTIMATES)
    itens = []
    for u in ULTIMATES:
        itens += [C.instr(0x05, 5, 0, 0, crc(u + "_name_callout")), C.instr(0x10, 5, 0, 4),
                  ("se_nao", 4, "x" + u),
                  C.instr(0x05, 5, 0, 0, crc("ult_%s_name_callout_01" % u)), C.instr(0x22, 5, 0, 0),
                  ("rotulo", "x" + u)]
    pre = b"".join(C.montar(itens))
    return pre + C.realocar(bytes(corpo), len(pre) // 4), npar


def script_novo(caminho):
    d = open(caminho, "rb").read()
    ops, funcs = C.ler(d)
    if not any(f[1] == FALA_ULTIMATES for f in funcs):
        return None
    if sum(1 for f in funcs if f[1] == FALA_ULTIMATES) > 1:
        raise ValueError("%s já tem o grito (use o vo_*.ds original)" % caminho)
    corpo, npar = fala_nova(d, funcs)
    out = bytearray(d) + C.registro(FALA_ULTIMATES, npar, corpo)
    struct.pack_into("<I", out, 4, struct.unpack_from("<I", out, 4)[0] + 1)
    C.ler(bytes(out))
    return bytes(out)


def relativo(f):
    f = f.replace("\\", "/")
    return f[f.index("USRDIR/") + 7:] if "USRDIR/" in f else os.path.basename(f)


def main(a):
    if len(a) < 3:
        print(__doc__); return 1
    vozes, scripts, saida = a
    bancos, todos = bancos_novos(vozes)
    print("gritos de Ultimate no jogo: %s" % ", ".join(todos))
    for f, (out, novos) in sorted(bancos.items()):
        dest = os.path.join(saida, relativo(f)); os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(out)
        print("  %-24s +%d grito(s)" % (relativo(f), len(novos)))
    for f in sorted(glob.glob(os.path.join(scripts, "**", "scripts", "vo_*.ds"), recursive=True)):
        out = script_novo(f)
        if out is None:
            continue
        dest = os.path.join(saida, relativo(f)); os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(out)
        print("  %-24s fala das Ultimates com os 5 gritos" % relativo(f))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
