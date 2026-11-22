"""cd_anims - Kit de modding do Ben 10 Cosmic Destruction
Copia animações de um alien normal para a forma Ultimate (pacotes .psp do Cosmic Destruction).

Uso:
  python cd_anims.py ORIGEM.psp DESTINO.psp SAIDA.psp anim1 anim2 ...
  python cd_anims.py --pasta PASTA_global --saida PASTA_SAIDA      (todas as Ultimates)

Formato (descoberto no próprio jogo):
  bloco 13 = cabeçalhos de animação (hash = crc32(prefixo + "_" + nome)):
     0x00 nome; 0x48 n ossos; 0x4c n ossos; 0x50 índice da trilha de eventos (ou -1);
     0x54 hash do esqueleto; 0x58 64 ids de osso (u16); 0xd8 n * (translação, rotação, escala)
     = índices na TABELA do bloco 9 (-1 = sem trilha).
  bloco 9 = trilhas. Translação: u16 0x0401, u16 0x0110, u16 n, u16 n, n * (t, x, y, z) float.
"""
import struct, sys, os, zlib, statistics
import types as _types

# ---- módulos embutidos (para ser um arquivo só) ----
_m = _types.ModuleType('spav'); exec(compile('"""Leitura e escrita dos pacotes spav (.psp) do Ben 10 Cosmic Destruction.\n\nCabeçalho (palavras u32): 0 \'spav\', 1 versão 0x10003, 2 n, 3 0x4000A (A = alinhamento 2^A),\n4 tamanho dos dados, 5 tipo, 6 0, 7 tamanho do cabeçalho (dados começam aqui),\n8 cap (baldes), 9 n, 10 0x20, 11 posição da tabela - 0x20, 12 12, 13 0, 14/15 livres.\n+0x40: cap inícios de balde (u32); depois n entradas [hash][tamanho|flags<<24][offset].\nEntradas ordenadas por balde = hash % cap. Um bloco "contêiner" (u16 em +0xC == 8) tem\nsub-pacotes como dados.\n"""\nimport struct\n\nMAGIC = b"spav"\n\n\nclass Bloco:\n    def __init__(self):\n        self.palavras = []      # 16 palavras do cabeçalho\n        self.entradas = []      # [hash, flags, dados(bytes) ou Bloco]\n        self.ordem = []         # ordem dos dados no arquivo (índices de entradas)\n        self.preench = {}       # índice -> bytes de enchimento depois dos dados\n        self.inicio_extra = b""  # bytes entre a tabela e o começo dos dados (além dos zeros)\n        self.cauda = b""\n\n    @property\n    def alinh(self):\n        return 1 << (self.palavras[3] & 0xFFFF)\n\n    @property\n    def conteiner(self):\n        return (self.palavras[3] >> 0) & 0xFFFF == 8 and False or struct.pack("<I", self.palavras[3])[0:2] == b"\\x08\\x00"\n\n\ndef ler(d, base=0, tam=None):\n    b = Bloco()\n    b.palavras = list(struct.unpack_from("<16I", d, base))\n    if d[base:base + 4] != MAGIC:\n        raise ValueError("não é spav em 0x%x" % base)\n    n = b.palavras[2]\n    cap = b.palavras[8]\n    cab = b.palavras[7]\n    t0 = base + 0x20 + b.palavras[11]\n    eh_cont = struct.unpack_from("<H", d, base + 0x0C)[0] == 8\n    b.eh_cont = eh_cont\n    ents = [struct.unpack_from("<III", d, t0 + 12 * i) for i in range(n)]\n    b.inicios = list(struct.unpack_from("<%dI" % cap, d, base + 0x40))\n    fim_tab = t0 + 12 * n\n    b.meio = d[fim_tab:base + cab]           # enchimento entre tabela e dados\n    dados0 = base + cab\n    tam_dados = b.palavras[4]\n    for h, t, o in ents:\n        tam_e = t & 0xFFFFFF\n        bruto = d[dados0 + o:dados0 + o + tam_e]\n        if eh_cont and bruto[:4] == MAGIC:\n            filho = ler(d, dados0 + o, tam_e)\n            b.entradas.append([h, t >> 24, filho, o, tam_e])\n        else:\n            b.entradas.append([h, t >> 24, bruto, o, tam_e])\n    b.ordem = sorted(range(n), key=lambda i: b.entradas[i][3])\n    # enchimentos\n    for k, i in enumerate(b.ordem):\n        o, te = b.entradas[i][3], b.entradas[i][4]\n        prox = b.entradas[b.ordem[k + 1]][3] if k + 1 < n else tam_dados\n        b.preench[i] = d[dados0 + o + te:dados0 + prox]\n    b.cauda = b""\n    if tam is not None:\n        b.cauda = d[dados0 + tam_dados:base + tam]\n    return b\n\n\ndef _alinha(x, a):\n    return (x + a - 1) // a * a\n\n\ndef escrever(b, preservar=True):\n    """Monta o bloco. preservar=True mantém enchimentos originais (para conferir).\n    Um bloco com o atributo mudou=True é sempre remontado; com mudou=False é sempre\n    copiado como estava (os filhos decidem por si)."""\n    if hasattr(b, "mudou"):\n        preservar = not b.mudou\n    n = len(b.entradas)\n    a = b.alinh\n    if preservar:\n        cap = b.palavras[8]\n    else:\n        cap = _alinha(n + 1, 4)\n    # ordem da tabela: por balde (estável)\n    tab = sorted(range(n), key=lambda i: (b.entradas[i][0] % cap, i))\n    inicios = []\n    j = 0\n    for k in range(cap):\n        inicios.append(j)\n        while j < n and b.entradas[tab[j]][0] % cap == k:\n            j += 1\n    # dados\n    corpo = bytearray()\n    offs = {}\n    for i in b.ordem:\n        e = b.entradas[i]\n        dado = escrever(e[2], preservar if not hasattr(b, \'mudou\') else True) if isinstance(e[2], Bloco) else e[2]\n        if not preservar:\n            corpo += b"\\0" * (_alinha(len(corpo), a) - len(corpo))\n        offs[i] = (len(corpo), len(dado))\n        corpo += dado\n        if preservar:\n            corpo += b.preench.get(i, b"")\n    if not preservar:\n        corpo += b"\\0" * (_alinha(len(corpo), a) - len(corpo))\n    tab_off = 0x40 + 4 * cap\n    fim_tab = tab_off + 12 * n\n    if preservar:\n        meio = b.meio\n    else:\n        meio = b"\\0" * (_alinha(fim_tab, a) - fim_tab)\n    cab = fim_tab + len(meio)\n    p = list(b.palavras)\n    p[2], p[4], p[7], p[8], p[9], p[11] = n, len(corpo), cab, cap, n, tab_off - 0x20\n    out = bytearray(struct.pack("<16I", *p))\n    out += struct.pack("<%dI" % cap, *inicios)\n    for i in tab:\n        h, fl = b.entradas[i][0], b.entradas[i][1]\n        o, t = offs[i]\n        out += struct.pack("<III", h, t | (fl << 24), o)\n    out += meio\n    out += corpo\n    out += b.cauda if preservar else b""\n    return bytes(out)\n', 'spav', 'exec'), _m.__dict__); sys.modules['spav'] = _m
_m = _types.ModuleType('redirecionar'); exec(compile('"""Redireciona rotações de animação entre esqueletos diferentes (Cosmic Destruction PSP).\n\nEsqueleto (bloco 12): u16 n, u16 n, u8, u8, u16, u32 hash; depois n registros de 44 bytes:\n  quat (x,y,z,w) float, translação (3 float), escala (3 float), u8 pai (0xff = raiz), u8, u16 id do osso.\nTrilha de rotação tipo 0x0210: u16 0x0210, u16 0x0210, u16 n, u16 n; n chaves de 8 bytes:\n  x,y,z int16 (/32767), w int8 (/127), u8 quadro (1 quadro = 160 tiques).\n\nAtenção: os quatérnios ficam guardados CONJUGADOS (inversos) no arquivo; aqui eles são\ndesconjugados na leitura e conjugados de novo na escrita.\n\nA rotação de cada osso é refeita em espaço de mundo: o movimento do osso de origem, medido a partir\nda pose de montagem (bind) do esqueleto de origem, é aplicado sobre a pose de montagem do destino.\nAssim ossos com eixos diferentes (ex.: quadril do Gigante x quadril do Ben) ficam na posição certa.\n"""\nimport math\nimport struct\n\n\ndef ler_esqueleto(d):\n    n = struct.unpack_from("<H", d, 0)[0]\n    ossos = []\n    for i in range(n):\n        o = 12 + 44 * i\n        q = inv(normal(struct.unpack_from("<4f", d, o)))\n        t = struct.unpack_from("<3f", d, o + 16)\n        pai, _, ident = struct.unpack_from("<BBH", d, o + 40)\n        ossos.append(dict(q=q, t=t, pai=None if pai == 0xFF else pai, id=ident))\n    # pose de montagem em mundo (rotação e posição de cada junta)\n    for b in ossos:\n        if b["pai"] is None:\n            b["W"], b["P"] = b["q"], b["t"]\n        else:\n            p = ossos[b["pai"]]\n            b["W"] = mul(p["W"], b["q"])\n            b["P"] = tuple(a + c for a, c in zip(p["P"], girar(p["W"], b["t"])))\n    return dict(hash=struct.unpack_from("<I", d, 8)[0], ossos=ossos,\n                por_id={b["id"]: i for i, b in enumerate(ossos)})\n\n\n# ---- quatérnios (x, y, z, w) ----\ndef normal(q):\n    s = math.sqrt(sum(x * x for x in q)) or 1.0\n    return tuple(x / s for x in q)\n\n\ndef mul(a, b):\n    ax, ay, az, aw = a\n    bx, by, bz, bw = b\n    return (aw * bx + ax * bw + ay * bz - az * by,\n            aw * by - ax * bz + ay * bw + az * bx,\n            aw * bz + ax * by - ay * bx + az * bw,\n            aw * bw - ax * bx - ay * by - az * bz)\n\n\ndef inv(q):\n    return (-q[0], -q[1], -q[2], q[3])\n\n\ndef girar(q, v):\n    return mul(mul(q, tuple(v) + (0.0,)), inv(q))[:3]\n\n\ndef arco(u, v):\n    """Menor rotação que leva a direção u até a direção v."""\n    nu = math.sqrt(sum(x * x for x in u))\n    nv = math.sqrt(sum(x * x for x in v))\n    if nu < 1e-6 or nv < 1e-6:\n        return (0.0, 0.0, 0.0, 1.0)\n    u = [x / nu for x in u]\n    v = [x / nv for x in v]\n    d = sum(a * b for a, b in zip(u, v))\n    if d < -0.9999:\n        eixo = (0.0, 1.0, 0.0) if abs(u[0]) > 0.9 else (1.0, 0.0, 0.0)\n        c = (u[1] * eixo[2] - u[2] * eixo[1], u[2] * eixo[0] - u[0] * eixo[2], u[0] * eixo[1] - u[1] * eixo[0])\n        return normal(c + (0.0,))\n    c = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])\n    return normal(c + (1.0 + d,))\n\n\ndef slerp(a, b, t):\n    d = sum(x * y for x, y in zip(a, b))\n    if d < 0:\n        b = tuple(-x for x in b)\n        d = -d\n    if d > 0.9995:\n        return normal(tuple(x + (y - x) * t for x, y in zip(a, b)))\n    th = math.acos(max(-1.0, min(1.0, d)))\n    s = math.sin(th)\n    wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s\n    return tuple(wa * x + wb * y for x, y in zip(a, b))\n\n\n# ---- trilhas ----\ndef ler_rot(t):\n    tipo, _, n, _ = struct.unpack_from("<HHHH", t, 0)\n    if tipo != 0x0210:\n        return None\n    ks = []\n    for k in range(n):\n        x, y, z, w, f = struct.unpack_from("<hhhbB", t, 8 + 8 * k)\n        v = (x / 32767.0, y / 32767.0, z / 32767.0)\n        # x,y,z guardam a precisão; o byte de w é só aproximado (o jogo usa o sinal)\n        ww = math.sqrt(max(0.0, 1.0 - sum(a * a for a in v)))\n        ks.append((f, inv(normal(v + (ww if w >= 0 else -ww,)))))\n    return ks\n\n\ndef escrever_rot(ks):\n    out = struct.pack("<HHHH", 0x0210, 0x0210, len(ks), len(ks))\n    for f, q in ks:\n        q = inv(normal(q))\n        c = [max(-32767, min(32767, int(round(v * 32767)))) for v in q[:3]]\n        w = max(-127, min(127, int(round(q[3] * 127))))\n        out += struct.pack("<hhhbB", c[0], c[1], c[2], w, f)\n    return out\n\n\ndef amostrar(ks, f):\n    if f <= ks[0][0]:\n        return ks[0][1]\n    for (f0, q0), (f1, q1) in zip(ks, ks[1:]):\n        if f0 <= f <= f1:\n            return slerp(q0, q1, (f - f0) / float(f1 - f0)) if f1 > f0 else q1\n    return ks[-1][1]\n\n\ndef redirecionar(rot_origem, esq_o, esq_d, rot_destino_fixa):\n    """rot_origem: {id_osso: chaves} da animação de origem.\n    rot_destino_fixa: {id_osso: quat} para ossos do destino sem par (fica a pose parada do destino).\n    Devolve {id_osso_destino: chaves} com uma chave por quadro."""\n    # as chaves usam o quadro absoluto do clipe original (ex.: cotovelada = quadros 30 a 38)\n    ultimo = max((ks[-1][0] for ks in rot_origem.values() if ks), default=0)\n    primeiro = min((ks[0][0] for ks in rot_origem.values() if ks), default=0)\n    quadros = list(range(primeiro, ultimo + 1))\n    # mundo na pose de montagem\n    def mundo_bind(esq):\n        m = [None] * len(esq["ossos"])\n        for i, b in enumerate(esq["ossos"]):\n            m[i] = b["q"] if b["pai"] is None else mul(m[b["pai"]], b["q"])\n        return m\n    wb_o, wb_d = mundo_bind(esq_o), mundo_bind(esq_d)\n\n    # correção de postura de montagem: o Ben é montado em T, o Gigante com os braços para\n    # baixo. Para cada osso, A gira a direção do osso no destino até a direção na origem.\n    def direcao(esq, i):\n        b = esq["ossos"][i]\n        filhos = [k for k, x in enumerate(esq["ossos"]) if x["pai"] == i]\n        for k in filhos:\n            if esq["ossos"][k]["id"] in ids_comuns:\n                return tuple(a - c for a, c in zip(esq["ossos"][k]["P"], b["P"]))\n        return None\n    ids_comuns = set(esq_o["por_id"]) & set(esq_d["por_id"])\n    ajuste = {}\n    for i, b in enumerate(esq_d["ossos"]):\n        j = esq_o["por_id"].get(b["id"])\n        A = (0.0, 0.0, 0.0, 1.0)\n        if j is not None:\n            u, v = direcao(esq_d, i), direcao(esq_o, j)\n            if u and v:\n                A = arco(u, v)\n            elif b["pai"] is not None:\n                A = ajuste.get(b["pai"], A)\n        ajuste[i] = A\n    saida = {b["id"]: [] for b in esq_d["ossos"]}\n    for f in quadros:\n        # mundo da origem neste quadro\n        wo = [None] * len(esq_o["ossos"])\n        for i, b in enumerate(esq_o["ossos"]):\n            ks = rot_origem.get(b["id"])\n            q = amostrar(ks, f) if ks else b["q"]\n            wo[i] = q if b["pai"] is None else mul(wo[b["pai"]], q)\n        wd = [None] * len(esq_d["ossos"])\n        for i, b in enumerate(esq_d["ossos"]):\n            j = esq_o["por_id"].get(b["id"])\n            pai_w = (0, 0, 0, 1) if b["pai"] is None else wd[b["pai"]]\n            if j is not None and b["id"] in rot_origem:\n                wd[i] = mul(mul(mul(wo[j], inv(wb_o[j])), ajuste[i]), wb_d[i])\n                local = mul(inv(pai_w), wd[i])\n            else:\n                local = rot_destino_fixa.get(b["id"], b["q"])\n                wd[i] = mul(pai_w, local)\n            local = normal(local)\n            if saida[b["id"]] and sum(x * y for x, y in zip(saida[b["id"]][-1][1], local)) < 0:\n                local = tuple(-x for x in local)      # mesmo hemisfério da chave anterior\n            saida[b["id"]].append((f, local))\n    # tira chaves que a interpolação já reproduz (erro < ~0,6 grau) para economizar memória\n    for k, ks in saida.items():\n        saida[k] = enxugar(ks)\n    return saida\n\n\ndef enxugar(ks, tol=0.99995):\n    if len(ks) <= 2:\n        if len(ks) == 2 and abs(sum(x * y for x, y in zip(ks[0][1], ks[1][1]))) > tol:\n            return ks[:1]\n        return ks\n    if all(abs(sum(x * y for x, y in zip(ks[0][1], q))) > tol for _, q in ks):\n        return ks[:1]\n    out = [ks[0]]\n    i = 0\n    while i < len(ks) - 1:\n        j = i + 1\n        # estica o segmento i..j enquanto os quadros do meio continuarem certos\n        while j + 1 < len(ks):\n            f0, q0 = ks[i]\n            f1, q1 = ks[j + 1]\n            ok = all(abs(sum(x * y for x, y in zip(slerp(q0, q1, (ks[m][0] - f0) / float(f1 - f0)), ks[m][1]))) > tol\n                     for m in range(i + 1, j + 1))\n            if not ok:\n                break\n            j += 1\n        out.append(ks[j])\n        i = j\n    return out\n', 'redirecionar', 'exec'), _m.__dict__); sys.modules['redirecionar'] = _m
sys.modules['copiar_anims'] = sys.modules[__name__]
import spav

NADA = 0xFFFFFFFF


def nome_anim(h):
    return h[:0x48].split(b"\0")[0].decode("latin1")


class Pacote:
    def __init__(self, caminho, prefixo=None):
        self.dados = open(caminho, "rb").read()
        self.raiz = spav.ler(self.dados, 0, len(self.dados))
        self.blk = {e[0]: e for e in self.raiz.entradas}
        self.b9 = self.blk[9][2]
        self.b13 = self.blk[13][2]
        self.prefixo = prefixo
        self.anims = {}
        for i, e in enumerate(self.b13.entradas):
            h = e[2]
            n = nome_anim(h)
            if n.endswith("_lod0") or " " in n:
                if n.endswith("_01_lod0"):
                    self.prefixo = n[:-len("_01_lod0")]
                continue
            nt = struct.unpack_from("<I", h, 0x48)[0]
            ids = struct.unpack_from("<%dH" % nt, h, 0x58)
            tr = struct.unpack_from("<%dI" % (3 * nt), h, 0xd8)
            self.anims[n] = dict(i=i, nt=nt, ids=ids, ev=struct.unpack_from("<I", h, 0x50)[0],
                                 esq=struct.unpack_from("<I", h, 0x54)[0],
                                 tr={ids[k]: tr[3 * k:3 * k + 3] for k in range(nt)})
        idle = self.anims["idle_01"]
        self.ossos = idle["ids"]
        self.esqueleto = idle["esq"]

    def trilha(self, i):
        return self.b9.entradas[i][2]


def chaves(t):
    a, b, n, n2 = struct.unpack_from("<HHHH", t, 0)
    assert a == 0x0401 and len(t) == 8 + 16 * n, "trilha de translação inesperada"
    return [struct.unpack_from("<4f", t, 8 + 16 * k) for k in range(n)]


def montar_trans(cab, ks):
    return cab[:4] + struct.pack("<HH", len(ks), len(ks)) + b"".join(struct.pack("<4f", *k) for k in ks)


try:
    import redirecionar as rd
except ImportError:
    rd = None


def deslocar_trilha(t, quadros):
    """Adianta o tempo de todas as chaves de uma trilha em 'quadros' (1 quadro = 160 tiques)."""
    if not quadros:
        return t
    t = bytearray(t)
    tipo, _, n, _ = struct.unpack_from("<HHHH", t, 0)
    tiques = 160.0 * quadros
    if tipo == 0x0210:                        # rotação: quadro num byte
        for k in range(n):
            t[8 + 8 * k + 7] = max(0, t[8 + 8 * k + 7] - quadros)
    elif tipo in (0x0401, 0x040C, 0x090A):    # translação, escala, eventos: tempo em float
        passo = 36 if tipo == 0x090A else 16
        for k in range(n):
            v = struct.unpack_from("<f", t, 8 + passo * k)[0]
            struct.pack_into("<f", t, 8 + passo * k, max(0.0, v - tiques))
    return bytes(t)


def acelerar_trilha(t, vel):
    """Toca a trilha 'vel' vezes mais rápido (divide o tempo de todas as chaves)."""
    if not vel or vel == 1:
        return t
    tipo, _, n, _ = struct.unpack_from("<HHHH", t, 0)
    if tipo == 0x0210:
        chaves_, vistos = [], set()
        for k in range(n):
            ch = bytearray(t[8 + 8 * k:16 + 8 * k])
            ch[7] = int(round(ch[7] / vel))
            if ch[7] in vistos:
                continue                      # duas chaves caíram no mesmo quadro
            vistos.add(ch[7])
            chaves_.append(bytes(ch))
        return struct.pack("<HHHH", tipo, tipo, len(chaves_), len(chaves_)) + b"".join(chaves_)
    t = bytearray(t)
    if tipo in (0x0401, 0x040C, 0x090A):
        passo = 36 if tipo == 0x090A else 16
        for k in range(n):
            v = struct.unpack_from("<f", t, 8 + passo * k)[0]
            struct.pack_into("<f", t, 8 + passo * k, v / vel)
    return bytes(t)


def copiar(orig, dest, nomes, log=print, esqueletos=None, deslocar=0, manter_eventos=False, velocidade=1.0):
    """Acrescenta em dest (Pacote) as animações 'nomes' de orig. Devolve lista de nomes copiados.
    Um item pode ser um par (nome_no_destino, nome_na_origem): se o destino já tiver uma
    animação com esse nome, ela é SUBSTITUÍDA (o golpe passa a tocar a animação nova)."""
    novas9 = []                       # [hash, flags, dados]
    por_dado = {}
    for i, e in enumerate(dest.b9.entradas):
        por_dado.setdefault(e[2], i)
    n0 = len(dest.b9.entradas)
    usados = {e[0] for e in dest.b9.entradas}

    def nova(dado, h):
        dado = acelerar_trilha(deslocar_trilha(dado, deslocar), velocidade)
        if dado in por_dado:
            return por_dado[dado]
        while h in usados:
            h = (h * 1103515245 + 12345) & 0xFFFFFFFF
        usados.add(h)
        idx = n0 + len(novas9)        # índice provisório (remapeado depois)
        novas9.append([h, 0, dado])
        por_dado[dado] = idx
        return idx

    # descanso (pose de idle) para reescalar translações
    def descanso(p, osso):
        t = p.anims["idle_01"]["tr"].get(osso)
        if not t or t[0] == NADA:
            return None
        return chaves(p.trilha(t[0]))[0][1:]

    razoes = []
    for o in dest.ossos:
        a, b = descanso(orig, o), descanso(dest, o)
        if a and b:
            la, lb = sum(x * x for x in a) ** .5, sum(x * x for x in b) ** .5
            if la > 1e-3 and lb > 1e-3:
                razoes.append(lb / la)
    escala = statistics.median(razoes) if razoes else 1.0
    log("  escala %s -> %s: %.3f" % (orig.prefixo, dest.prefixo, escala))

    copiadas = []
    novos13 = []
    trocar = set()
    for item in nomes:
        nome, nome_o = (item, item) if isinstance(item, str) else item
        if nome_o not in orig.anims:
            log("  (sem %s em %s)" % (nome_o, orig.prefixo))
            continue
        if nome in dest.anims:
            if isinstance(item, str):
                log("  (%s já existe no destino)" % nome)
                continue
            trocar.add(dest.anims[nome]["i"])
        a = orig.anims[nome_o]
        # (pry_01 do Humungossauro usa outro esqueleto; o mapeamento é por id de osso)
        idle_d = dest.anims["idle_01"]["tr"]
        rot_nova = None
        if esqueletos:
            ro = {}
            for o_, (ti_, ri_, si_) in a["tr"].items():
                if ri_ != NADA:
                    ks = rd.ler_rot(orig.trilha(ri_))
                    if ks:
                        ro[o_] = ks
            fixa = {}
            for o_ in dest.ossos:
                ri_ = idle_d[o_][1]
                ks = rd.ler_rot(dest.trilha(ri_)) if ri_ != NADA else None
                if ks:
                    fixa[o_] = ks[0][1]
            rot_nova = rd.redirecionar(ro, esqueletos[0], esqueletos[1], fixa)
        trip = []
        faltam = 0
        for o in dest.ossos:
            if o not in a["tr"]:
                # osso que a origem não tem: fica parado na primeira pose do idle do destino
                # (trilhas de uma chave só, para não esticar a duração do golpe)
                it, ir, is_ = idle_d[o]
                t = it
                if it != NADA and len(chaves(dest.trilha(it))) > 1:
                    k0 = chaves(dest.trilha(it))[0]
                    t = nova(montar_trans(dest.trilha(it), [(0.0,) + tuple(k0[1:])]), dest.b9.entradas[it][0])
                if rot_nova is not None and rot_nova.get(o):
                    r = nova(rd.escrever_rot(rot_nova[o][:1]), 0x7654321)
                else:
                    r = ir
                trip += [t, r, is_]
                faltam += 1
                continue
            ti, ri, si = a["tr"][o]
            # rotação e escala: cópia direta
            if rot_nova is not None and rot_nova.get(o):
                r = nova(rd.escrever_rot(rot_nova[o]), orig.b9.entradas[ri][0] if ri != NADA else 0x1234567)
            else:
                r = nova(orig.trilha(ri), orig.b9.entradas[ri][0]) if ri != NADA else NADA
            s = nova(orig.trilha(si), orig.b9.entradas[si][0]) if si != NADA else NADA
            # translação: reescalada a partir da pose de descanso da Ultimate
            if ti == NADA:
                t = NADA
            else:
                src = orig.trilha(ti)
                ks = chaves(src)
                ra, rb = descanso(orig, o), descanso(dest, o)
                if ra is None or rb is None:
                    t = nova(src, orig.b9.entradas[ti][0])
                else:
                    parado = all(max(abs(k[j + 1] - ra[j]) for j in range(3)) < 1e-3 for k in ks)
                    if parado:
                        t = idle_d[o][0] if len(chaves(dest.trilha(idle_d[o][0]))) == 1 else \
                            nova(montar_trans(src, [(0.0,) + tuple(rb)]), orig.b9.entradas[ti][0])
                    else:
                        conv = lambda v: v
                        if esqueletos:
                            # o deslocamento está no espaço do osso pai da origem: passa para o
                            # espaço do pai no destino (eixos diferentes entre esqueletos)
                            eo_, ed_ = esqueletos
                            po = eo_["ossos"][eo_["por_id"][o]]["pai"] if o in eo_["por_id"] else None
                            pd = ed_["ossos"][ed_["por_id"][o]]["pai"] if o in ed_["por_id"] else None
                            if po is not None and pd is not None:
                                Wo, Wd = eo_["ossos"][po]["W"], ed_["ossos"][pd]["W"]
                                conv = lambda v, Wo=Wo, Wd=Wd: rd.girar(rd.inv(Wd), rd.girar(Wo, v))
                        nk = []
                        for k in ks:
                            dv = conv(tuple((k[j + 1] - ra[j]) * escala for j in range(3)))
                            nk.append((k[0],) + tuple(rb[j] + dv[j] for j in range(3)))
                        t = nova(montar_trans(src, nk), orig.b9.entradas[ti][0])
            trip += [t, r, s]
        ev = a["ev"]
        if manter_eventos == "escalar" and nome in dest.anims:
            # eventos do golpe original (as partes do corpo que acertam), com os tempos
            # esticados para a duração da animação nova
            ev = dest.anims[nome]["ev"]
            if ev != NADA:
                def faixa(p, an):
                    fs = [k[0] for (t_, r_, s_) in an["tr"].values() if r_ != NADA
                          for k in (rd.ler_rot(p.trilha(r_)) or [])]
                    return (min(fs), max(fs)) if fs else (0, 1)
                d0, d1 = faixa(dest, dest.anims[nome])
                o0, o1 = faixa(orig, a)
                o0, o1 = o0 - deslocar, o1 - deslocar
                tr_ev = bytearray(dest.trilha(ev))
                n_ev = struct.unpack_from("<H", tr_ev, 4)[0]
                for k in range(n_ev):
                    tq = struct.unpack_from("<f", tr_ev, 8 + 36 * k)[0] / 160.0
                    x = (tq - d0) / float(max(1, d1 - d0))
                    struct.pack_into("<f", tr_ev, 8 + 36 * k, 160.0 * (o0 + x * (o1 - o0)))
                ev = nova(deslocar_trilha(bytes(tr_ev), -deslocar) if deslocar else bytes(tr_ev), 0x0E7E0000 + k)
        elif manter_eventos and nome in dest.anims:
            ev = dest.anims[nome]["ev"]          # eventos (momento do acerto) do golpe original
        elif ev != NADA:
            ev = nova(orig.trilha(ev), orig.b9.entradas[ev][0])
        h = bytearray(orig.b13.entradas[a["i"]][2])
        nt = len(dest.ossos)
        cab = bytearray(h[:0x58])
        cab[:0x48] = nome.encode().ljust(0x48, b"\0")[:0x48]
        struct.pack_into("<IIII", cab, 0x48, nt, nt, ev, dest.esqueleto)
        ids = list(dest.ossos) + [0] * (64 - nt)
        corpo = cab + struct.pack("<64H", *ids) + struct.pack("<%dI" % (3 * nt), *trip)
        novos13.append([zlib.crc32((dest.prefixo + "_" + nome).encode()), orig.b13.entradas[a["i"]][1], bytes(corpo)])
        copiadas.append(nome)
        log("  %s %-24s%s ossos sem par: %d" % ("~" if nome in dest.anims else "+", nome,
            "" if nome == nome_o else " <- " + nome_o, faltam))

    # --- bloco 9: acrescenta e reconstrói a tabela (índices mudam -> remapear tudo) ---
    b9 = dest.b9
    antigas = b9.entradas
    todas = [[e[0], e[1], e[2]] for e in antigas] + novas9
    cap = (len(todas) + 1 + 3) // 4 * 4
    ordem_tab = sorted(range(len(todas)), key=lambda i: (todas[i][0] % cap, i))
    novo_idx = {velho: novo for novo, velho in enumerate(ordem_tab)}
    # ordem dos dados: antigas como estavam, novas no fim
    pos_dados = {i: k for k, i in enumerate(list(b9.ordem) + list(range(len(antigas), len(todas))))}
    b9.entradas = [[todas[i][0], todas[i][1], todas[i][2], 0, len(todas[i][2])] for i in ordem_tab]
    b9.ordem = sorted(range(len(todas)), key=lambda novo: pos_dados[ordem_tab[novo]])
    b9.palavras[8] = cap
    b9.preench = {}

    def remap_cab(h):
        h = bytearray(h)
        nt = struct.unpack_from("<I", h, 0x48)[0]
        ev = struct.unpack_from("<I", h, 0x50)[0]
        if ev != NADA:
            struct.pack_into("<I", h, 0x50, novo_idx[ev])
        tr = struct.unpack_from("<%dI" % (3 * nt), h, 0xd8)
        struct.pack_into("<%dI" % (3 * nt), h, 0xd8, *[v if v == NADA else novo_idx[v] for v in tr])
        return bytes(h)

    b13 = dest.b13
    ents = []
    for k, e in enumerate(b13.entradas):
        if k in trocar:
            continue
        n = nome_anim(e[2])
        ents.append([e[0], e[1], e[2] if (n.endswith("_lod0") or " " in n) else remap_cab(e[2])])
    for e in novos13:
        ents.append([e[0], e[1], remap_cab(e[2])])
    velho_p_novo, j = {}, 0
    for k in range(len(b13.entradas)):
        if k not in trocar:
            velho_p_novo[k] = j
            j += 1
    ordem13 = [velho_p_novo[i] for i in b13.ordem if i in velho_p_novo] + list(range(j, len(ents)))
    cap13 = max(b13.palavras[8], (len(ents) + 1 + 3) // 4 * 4)
    tab13 = sorted(range(len(ents)), key=lambda i: (ents[i][0] % cap13, i))
    pos13 = {i: k for k, i in enumerate(ordem13)}
    b13.entradas = [[ents[i][0], ents[i][1], ents[i][2], 0, len(ents[i][2])] for i in tab13]
    b13.ordem = sorted(range(len(ents)), key=lambda novo: pos13[tab13[novo]])
    b13.palavras[8] = cap13
    b13.preench = {}
    return copiadas


def esqueleto_do_pacote(p):
    """Esqueleto (bloco 12) do próprio pacote, no formato do redirecionar."""
    b12 = p.blk[12][2]
    for e in b12.entradas:
        if struct.unpack_from("<I", e[2], 8)[0] == p.esqueleto:
            return rd.ler_esqueleto(e[2])
    return rd.ler_esqueleto(b12.entradas[0][2])


def salvar(p, caminho):
    # só os blocos alterados (raiz, trilhas 9, cabeçalhos 13, esqueleto novo) são
    # remontados; texturas, malhas etc. ficam byte a byte como no original
    p.raiz.mudou = True
    p.b9.mudou = True
    p.b13.mudou = True
    out = spav.escrever(p.raiz, preservar=True)
    open(caminho, "wb").write(out)
    return out


# Animações de interação com o cenário e de reação (o que faz o alien travar se faltar)
PARES = {
    "g_uhm.psp": ("g_hm.psp", ["interact_in_01", "interact_01", "interact_out_01", "pry_01",
                               "knockback_01", "gethit_front_01", "gethit_front_fall_01", "counter_stunned_01"]),
    "g_usm.psp": ("g_sm.psp", ["interact_in_01", "interact_01", "interact_out_01",
                               "ledge_in_01", "ledge_idle_01", "ledge_left_01", "ledge_right_01", "ledge_pullup_01",
                               "jumpdouble_01", "grapple_01", "grapple_air_in_01", "grapple_ground_idle_01",
                               "grapple_ground_in_01", "grapple_pull_01", "grapple_swing_01",
                               "knockback_01", "stun_01", "gethit_fwd_01", "gethit_fwd_fall_01",
                               "counter_stunned_01", "defeated_01"]),
    "g_usf.psp": ("g_sf.psp", ["interact_in_01", "interact_01", "interact_out_01",
                               "ledge_in_01", "ledge_idle_01", "ledge_left_01", "ledge_right_01", "ledge_pullup_01",
                               "jumpdouble_01", "knockback_01", "stun_01", "gethit_fwd_01", "gethit_fwd_fall_01",
                               "counter_stunned_01", "defeated_01"]),
    "g_ubc.psp": ("g_bc.psp", ["interact_in_01", "interact_01", "interact_out_01",
                               "ledge_in_01", "ledge_idle_01", "ledge_left_01", "ledge_right_01", "ledge_pullup_01",
                               "knockback_01", "stun_01", "gethit_front_01", "gethit_front_fall_01",
                               "counter_stunned_01"]),
    "g_uec.psp": ("g_ec.psp", ["interact_in_01", "interact_idle_01", "interact_out_01",
                               "knockback_01", "gethit_front_01", "gethit_front_fall_01",
                               "counter_stunned_01", "defeated_01", "prone_01", "prone_gethit_01", "prone_out_01"]),
}


def montar_gigante(pasta_tokd, pasta_global, saida, log=print):
    import copy
    dest = Pacote(os.path.join(pasta_tokd, "g_wayb.psp"), "waybig")
    glob_ = Pacote(os.path.join(pasta_global, "g_wayb.psp"), "waybig")
    assert dest.ossos == glob_.ossos and dest.esqueleto == glob_.esqueleto
    extras = sorted(set(glob_.anims) - set(dest.anims))
    copiar(glob_, dest, extras, log)
    d = open(os.path.join(pasta_tokd, "l_tokd.psp"), "rb").read()
    fase = spav.ler(d, 0, len(d))
    esq = [e for e in fase.entradas if e[0] == 12][0][2]
    pele = {e[0]: e[2] for e in esq.entradas if struct.unpack_from("<I", e[2], 8)[0] == dest.esqueleto}
    assert pele, "esqueleto do Gigante não encontrado em l_tokd.psp"
    b12 = copy.deepcopy(esq)
    b12.entradas = [[h, 0, x, 0, len(x)] for h, x in pele.items()]
    b12.ordem = list(range(len(b12.entradas)))
    b12.preench = {}
    b12.mudou = True
    b12.palavras[8] = (len(b12.entradas) + 1 + 3) // 4 * 4
    r = dest.raiz
    if not any(e[0] == 12 for e in r.entradas):
        r.entradas.append([12, 0, b12, 0, 0])
        r.ordem = [len(r.entradas) - 1] + list(r.ordem)
    r.preench = {}
    os.makedirs(saida, exist_ok=True)
    out = salvar(dest, os.path.join(saida, "g_wayb.psp"))
    log("  g_wayb.psp: %d bytes (esqueletos: %d, animações extras: %d)" % (len(out), len(pele), len(extras)))


_MB_SRC = '"""Ben com os golpes do Gigante: monta o a_plyr.psp a partir do original do jogo."""\nimport sys, os, struct, zlib\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\nc = sys.modules[\'copiar_anims\']; import spav, redirecionar as rd\n\ndef esqueleto(pk, h):\n    d = open(pk, \'rb\').read(); b = spav.ler(d, 0, len(d))\n    for e in [e for e in b.entradas if e[0] == 12][0][2].entradas:\n        if struct.unpack_from(\'<I\', e[2], 8)[0] == h:\n            return rd.ler_esqueleto(e[2])\n\n# (golpe do Ben, animação do Gigante, quadro onde a animação do Gigante começa)\n# (pares, quadro em que a animação do Gigante começa, velocidade)\nGOLPES = [\n    # quadrado parado (o golpe mais usado): chute voador\n    ([(\'atk_close_fwd_02\', \'flying_heel_01\'), (\'atk_close_fwd_out_02\', \'flying_heel_out_01\')], 25, 1.3),\n    # quadrado em movimento: cotovelada; aproximação: o salto do chute voador\n    ([(\'atk_close_fwd_01\', \'elbow_smash_01\'), (\'atk_close_fwd_out_01\', \'elbow_smash_out_01\')], 30, 1.3),\n    ([(\'atk_close_fwd_travel_01\', \'flying_heel_in_01\')], 3, 1.5),\n    # triângulo em movimento: pisão\n    ([(\'atk_close_fwd_03\', \'crushingheel_01\')], 0, 2.0),\n    ([(\'atk_close_fwd_out_03\', \'atk_close_fwd_out_03\')], 21, 1.5),\n    # triângulo parado: socos seguidos no chão\n    ([(\'atk_close_bwd_01\', \'fistpummel_01\')], 0, 1.8),\n    ([(\'atk_close_bwd_out_01\', \'atk_close_fwd_out_02\')], 21, 1.5),\n    # contra-ataque: cotovelada\n    ([(\'counter_atk_01\', \'elbow_smash_01\'), (\'counter_atk_out_01\', \'elbow_smash_out_01\')], 30, 1.3),\n    ([(\'counter_atk_travel_01\', \'counter_atk_travel_01\')], 0, 1.3),\n    # especiais do Gigante (R + botão, como na roda): animações novas com o nome do Gigante\n    ([(\'elbow_smash_01\', \'elbow_smash_01\'), (\'elbow_smash_out_01\', \'elbow_smash_out_01\')], 30, 1.3),\n    ([(\'flying_heel_01\', \'flying_heel_01\'), (\'flying_heel_out_01\', \'flying_heel_out_01\')], 25, 1.3),\n    ([(\'fistpummel_01\', \'fistpummel_01\')], 0, 1.8),\n]\n\n# especiais do Gigante que o Ben ganha: (registro no atk_wb.ddf, nome do golpe no Ben)\nESPECIAIS = [(3, \'ben_elbow_smash\'), (5, \'ben_fistpummel\'), (8, \'ben_flying_heel\')]\n\n\ndef atk_ben(atk_bn, atk_wb):\n    """atk_bn.ddf com os especiais do Gigante acrescentados (apontando para as animações do Ben).\n    Cada especial parte de um golpe do próprio Ben (o 3º soco) e recebe do Gigante só a marca\n    de especial, o dano e os tempos. Referências que só existem com o Gigante carregado\n    (efeitos, câmera, aproximação) ficam as do Ben: com elas o jogo travava."""\n    bn = bytearray(atk_bn)\n    base = bytes(atk_bn[4 + 224 * 3:4 + 224 * 4])          # golpe forte do Ben (eee0be9c)\n    for i, nome in ESPECIAIS:\n        wb = atk_wb[4 + 224 * i:4 + 224 * (i + 1)]\n        r = bytearray(base)\n        struct.pack_into(\'<I\', r, 0, zlib.crc32(nome.encode()))\n        for campo in (8, 9):\n            h = struct.unpack_from(\'<I\', wb, 4 * campo)[0]\n            struct.pack_into(\'<I\', r, 4 * campo, ANIM_BEN[h] if h else 0)\n        r[4 * 12:4 * 24] = wb[4 * 12:4 * 24]                 # dano, alcance, tempos\n        r[4 * 25:4 * 26] = wb[4 * 25:4 * 26]                 # marca de especial\n        # campos 36/37: qual melhoria (upgrade) libera o golpe. Os do Gigante pedem melhorias\n        # que o Ben não tem, então o golpe ficava bloqueado; ficam os "sempre liberado" do Ben.\n        # 38..41: tipo e botão do especial (o campo 40 é o botão: cada especial tem o seu).\n        r[4 * 38:4 * 42] = wb[4 * 38:4 * 42]\n        bn += r\n    return bytes(bn)\n\n\n# hash da animação no Gigante -> hash da mesma animação no Ben\nANIM_BEN = {zlib.crc32((\'waybig_\' + n).encode()): zlib.crc32((\'ben_\' + n).encode())\n            for n in (\'elbow_smash_01\', \'elbow_smash_out_01\', \'flying_heel_01\', \'flying_heel_out_01\',\n                      \'fistpummel_01\', \'bigbeam_01\', \'bigbeam_out_01\')}\nIDS_ESPECIAIS = [zlib.crc32(n.encode()) for _, n in ESPECIAIS]\n\n\ndef montar(a_plyr, g_wayb, l_tokd, saida, log=print):\n    w = c.Pacote(g_wayb, \'waybig\')\n    eb = esqueleto(l_tokd, c.Pacote(a_plyr, \'ben\').esqueleto)\n    ew = esqueleto(g_wayb, w.esqueleto)\n    atual = a_plyr\n    for i, (pares, desl, vel) in enumerate(GOLPES):\n        ben = c.Pacote(atual, \'ben\')\n        c.copiar(w, ben, pares, log=log, esqueletos=(ew, eb), deslocar=desl, manter_eventos=\'escalar\', velocidade=vel)\n        atual = saida + \'.tmp%d\' % i\n        c.salvar(ben, atual)\n    os.replace(atual, saida)\n    for i in range(len(GOLPES) - 1):\n        os.remove(saida + \'.tmp%d\' % i)\n    return saida\n\nif __name__ == \'__main__\':\n    montar(*sys.argv[1:5])\n'


PASTAS_BEN = ["global", "l_chin", "l_mili", "l_pari", "l_romd", "l_romn", "l_rush", "l_tokd", "l_tokn"]


def ben_gigante(a_plyr, pasta_tokd, pasta_global, saida, log=print):
    """Ben humano com os golpes do Gigante, em todas as cópias do a_plyr.psp."""
    import tempfile, shutil
    if 'montar_ben_gigante' not in sys.modules:
        _mb = _types.ModuleType('montar_ben_gigante'); _mb.__dict__['__file__'] = __file__
        exec(compile(_MB_SRC, 'montar_ben_gigante', 'exec'), _mb.__dict__); sys.modules['montar_ben_gigante'] = _mb
    import montar_ben_gigante as mb
    with tempfile.TemporaryDirectory() as tmp:
        montar_gigante(pasta_tokd, pasta_global, tmp, log=lambda *x: None)
        destino = os.path.join(tmp, "a_plyr.psp")
        mb.montar(a_plyr, os.path.join(tmp, "g_wayb.psp"), os.path.join(pasta_tokd, "l_tokd.psp"), destino, log=log)
        for p in PASTAS_BEN:
            os.makedirs(os.path.join(saida, p), exist_ok=True)
            shutil.copyfile(destino, os.path.join(saida, p, "a_plyr.psp"))
    log("  a_plyr.psp colocado em %d pastas dentro de %s" % (len(PASTAS_BEN), saida))
    # golpes especiais (R + botão): acrescenta os do Gigante no atk_bn.ddf
    scripts = os.path.join(os.path.dirname(os.path.abspath(a_plyr)), "scripts")
    bn, wb = os.path.join(scripts, "atk_bn.ddf"), os.path.join(scripts, "atk_wb.ddf")
    if os.path.exists(bn) and os.path.exists(wb):
        novo = mb.atk_ben(open(bn, "rb").read(), open(wb, "rb").read())
        os.makedirs(os.path.join(saida, "global", "scripts"), exist_ok=True)
        open(os.path.join(saida, "global", "scripts", "atk_bn.ddf"), "wb").write(novo)
        log("  atk_bn.ddf com %d especiais do Gigante" % len(mb.ESPECIAIS))
    else:
        log("  (atk_bn.ddf/atk_wb.ddf não achados em %s: só as animações)" % scripts)


def main(a):
    if a and a[0] == "--ben-gigante":
        saida = a[a.index("--saida") + 1] if "--saida" in a else "ben_gigante"
        ben_gigante(a[1], a[2], a[3], saida)
        return
    if a and a[0] == "--gigante":
        saida = a[a.index("--saida") + 1] if "--saida" in a else "gigante_mod"
        montar_gigante(a[1], a[2], saida)
        return
    if a and a[0] == "--pasta":
        pasta = a[1]
        saida = a[a.index("--saida") + 1] if "--saida" in a else "ultimates_mod"
        os.makedirs(saida, exist_ok=True)
        for ult, (norm, nomes) in PARES.items():
            print(ult, "<-", norm)
            o, d = Pacote(os.path.join(pasta, norm)), Pacote(os.path.join(pasta, ult))
            copiar(o, d, nomes, esqueletos=(esqueleto_do_pacote(o), esqueleto_do_pacote(d)))
            out = salvar(d, os.path.join(saida, ult))
            print("  tamanho: %d -> %d bytes" % (len(d.dados), len(out)))
        return
    if len(a) < 4:
        print(__doc__)
        return 1
    o, d = Pacote(a[0]), Pacote(a[1])
    copiar(o, d, a[3:])
    salvar(d, a[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
