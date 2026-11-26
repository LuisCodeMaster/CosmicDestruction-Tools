"""cd_vozes - Ultimates gritando o próprio nome ("Ultimate Humungousaur!") em qualquer fase
do Ben 10 Ultimate Alien: Cosmic Destruction (PSP e Xbox 360).

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
  Se a PASTA_SCRIPTS tiver global/scripts/sounds.ddf (a lista nome -> posição no banco),
  os gritos ganham nomes novos (luis_ult_<alien>_grito) numa posição fixa, igual em todos
  os bancos, e o sounds.ddf ganha essas 5 linhas. Sem o sounds.ddf o jogo não acha o som
  copiado (o banco só tem o nome cortado; quem diz a posição é o sounds.ddf).
  No Xbox 360 as duas pastas são a pasta do jogo extraído (<fase>/vo/vo_eng.xbx e
  <fase>/scripts/vo_<fase>.ds, scripts big-endian); a saída repete os caminhos.
"""
import os, sys, glob, struct, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cd_scripts as C

CAB, ALINHA = 48, 32
FALA_ULTIMATES = 0xE8C0396D      # função das falas das Ultimates nos scripts vo_<fase>.ds
ULTIMATES = ["humongousaur", "spidermonkey", "bigchill", "echoecho", "swampfire"]
NOMES_GRITO = lambda u: "ult_%s_name_callout_01" % u   # trocado por nome_grito com sounds.ddf


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
    arquivos = sorted(glob.glob(os.path.join(pasta, "**", "vo", "vo_eng.psp"), recursive=True) +
                      glob.glob(os.path.join(pasta, "**", "vo", "vo_eng.xbx"), recursive=True))
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


def nome_grito(u):
    return "luis_ult_%s_grito" % u


def prefixo_grito(u):
    return ("ult_%s_name_callout" % u).encode()[:30]


def bancos_com_posicao(pasta):
    """Põe os 5 gritos nas posições BASE..BASE+4 de todos os bancos de fase (enchendo com
    cópias da menor fala até a posição BASE) e devolve as linhas novas do sounds.ddf."""
    arquivos = sorted(glob.glob(os.path.join(pasta, "**", "vo", "vo_eng.psp"), recursive=True) +
                      glob.glob(os.path.join(pasta, "**", "vo", "vo_eng.xbx"), recursive=True))
    lidos = {f: ler_fsb(open(f, "rb").read()) for f in arquivos}
    fases = {f: v for f, v in lidos.items() if any(n.startswith(b"ult_") for n, _, _ in v[1])}
    gritos = {}
    for cab0, am in fases.values():
        for a in am:
            for u in ULTIMATES:
                if a[0].startswith(prefixo_grito(u)):
                    gritos.setdefault(u, a)
    falta = [u for u in ULTIMATES if u not in gritos]
    if falta:
        raise ValueError("grito não achado em nenhum banco: %s" % ", ".join(falta))
    base = max(len(am) for _, am in fases.values())
    saida = {}
    for f, (cab0, am) in fases.items():
        menor = min(am, key=lambda a: len(a[2]))
        enchimento = [menor] * (base - len(am))
        novos = [gritos[u] for u in ULTIMATES]
        out = escrever_fsb(cab0, am + enchimento + novos)
        _, am2 = ler_fsb(out)
        assert am2[:len(am)] == am and len(am2) == base + len(ULTIMATES)
        saida[f] = (out, len(enchimento))
    linhas = "".join('\t\t<sound name="%s" id="%d" bank="voice" isloop="no" falloffstart="-1.0" '
                     'falloffend="-1.0" volume="1.0" />\r\n' % (nome_grito(u), base + i)
                     for i, u in enumerate(ULTIMATES))
    return saida, base, linhas


def sounds_novo(d, linhas):
    """Acrescenta as linhas no fim do grupo das falas (dialog) do sounds.ddf."""
    i = d.find(b'<group name="dialog">')
    j = d.find(b"</group>", i)
    if i < 0 or j < 0:
        raise ValueError("sounds.ddf sem o grupo dialog")
    if b"luis_ult_" in d:
        raise ValueError("sounds.ddf já tem os gritos (use o original)")
    k = d.rfind(b"\n", 0, j) + 1                       # começo da linha do </group>
    return d[:k] + linhas.encode() + d[k:]


def fala_nova(d, funcs):
    """Função das falas das Ultimates com o grito das cinco antes do código original."""
    corpo, npar = C.corpo_de(d, funcs, FALA_ULTIMATES)
    itens = []
    for u in ULTIMATES:
        itens += [C.instr(0x05, 5, 0, 0, crc(u + "_name_callout")), C.instr(0x10, 5, 0, 4),
                  ("se_nao", 4, "x" + u),
                  C.instr(0x05, 5, 0, 0, crc(NOMES_GRITO(u))), C.instr(0x22, 5, 0, 0),
                  ("rotulo", "x" + u)]
    pre = b"".join(C.montar(itens))
    return pre + C.realocar(bytes(corpo), len(pre) // 4), npar


def script_novo(caminho):
    d = open(caminho, "rb").read()
    x360 = d[:4] == C.MAGIC[::-1]              # Xbox 360: script big-endian
    if x360:
        d = C.trocar_ordem(d, ">", "<")
    ops, funcs = C.ler(d)
    if not any(f[1] == FALA_ULTIMATES for f in funcs):
        return None
    if sum(1 for f in funcs if f[1] == FALA_ULTIMATES) > 1:
        raise ValueError("%s já tem o grito (use o vo_*.ds original)" % caminho)
    corpo, npar = fala_nova(d, funcs)
    out = bytearray(d) + C.registro(FALA_ULTIMATES, npar, corpo)
    struct.pack_into("<I", out, 4, struct.unpack_from("<I", out, 4)[0] + 1)
    C.ler(bytes(out))
    if x360:
        return C.trocar_ordem(bytes(out), "<", ">")
    return bytes(out)


def relativo(f, base=None):
    f = f.replace("\\", "/")
    if "USRDIR/" in f:
        return f[f.index("USRDIR/") + 7:]
    if base:                                   # Xbox 360: pasta extraída sem USRDIR
        return os.path.relpath(f, base).replace("\\", "/")
    return os.path.basename(f)


def main(a):
    if len(a) < 3:
        print(__doc__); return 1
    global NOMES_GRITO
    vozes, scripts, saida = a
    sounds = os.path.join(scripts, "global", "scripts", "sounds.ddf")
    if os.path.exists(sounds):
        NOMES_GRITO = nome_grito
        bancos, base, linhas = bancos_com_posicao(vozes)
        print("sounds.ddf achado: gritos novos nas posições %d a %d de todos os bancos" % (base, base + 4))
        for f, (out, ench) in sorted(bancos.items()):
            dest = os.path.join(saida, relativo(f, vozes)); os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "wb").write(out)
            print("  %-24s +%d enchimento(s) +5 gritos" % (relativo(f, vozes), ench))
        out = sounds_novo(open(sounds, "rb").read(), linhas)
        dest = os.path.join(saida, relativo(sounds, scripts)); os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(out)
        print("  %-24s +5 falas (%s ...)" % (relativo(sounds, scripts), nome_grito(ULTIMATES[0])))
    else:
        bancos, todos = bancos_novos(vozes)
        print("gritos de Ultimate no jogo: %s" % ", ".join(todos))
        for f, (out, novos) in sorted(bancos.items()):
            dest = os.path.join(saida, relativo(f, vozes)); os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "wb").write(out)
            print("  %-24s +%d grito(s)" % (relativo(f, vozes), len(novos)))
    for f in sorted(glob.glob(os.path.join(scripts, "**", "scripts", "vo_*.ds"), recursive=True)):
        out = script_novo(f)
        if out is None:
            continue
        dest = os.path.join(saida, relativo(f, scripts)); os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(out)
        print("  %-24s fala das Ultimates com os 5 gritos" % relativo(f, scripts))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
