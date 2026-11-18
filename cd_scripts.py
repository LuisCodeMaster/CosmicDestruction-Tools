#!/usr/bin/env python3
"""
cd_scripts - Kit de modding do Ben 10 Ultimate Alien: Cosmic Destruction (PSP)
Ferramenta 6: scripts compilados (.ds)

COMANDOS
  Desmontar um script em texto legível:
    python cd_scripts.py desmontar globals.ds globals.txt [--nomes cd_nomes.txt]

  Gerar a lista de nomes (a partir da SUA cópia do jogo, para a desmontagem ficar legível):
    python cd_scripts.py gerar-nomes ULUS10542_EBOOT.BIN pasta_extraida cd_nomes.txt
    (o EBOOT descriptografado sai do PPSSPP; a pasta é a extraída com cd_analisador.py --extrair)

  Aplicar o mod "Ultimate a qualquer momento" no globals.ds:
    python cd_scripts.py ultimate-livre globals.ds globals_mod.ds

  Rastreio (o mod completo + um sinal: o direcional trava quando a etapa N começa):
    python cd_scripts.py rastreio 1 globals.ds globals_r1.ds    (etapa 1: SELECT -> voltar a ser Ben)
    python cd_scripts.py rastreio 2 globals.ds globals_r2.ds    (etapa 2: carregar a forma Ultimate)
    python cd_scripts.py rastreio 3 globals.ds globals_r3.ds    (etapa 3: virar o alien de novo)
    python cd_scripts.py rastreio 4 globals.ds globals_r4.ds    (etapa 4: ativar a Ultimate)

  Teste de diagnóstico (só libera o SELECT para aliens normais, com o efeito original):
    python cd_scripts.py diagnostico-select globals.ds globals_diag.ds

O QUE O MOD ULTIMATE-LIVRE FAZ
  1. Na função que ativa a forma Ultimate (0x1da4f7b4), remove a checagem
     da variável 0x28280148, que só as fases ligam durante os Ultimate Events,
     e preenche a variável 0xf495406a (qual alien vira Ultimate) com o alien atual.
  2. Em switch_form_update (botão SELECT): quando você está como alien,
     o SELECT chama a função da forma Ultimate.
  3. Libera o SELECT para os aliens normais (o jogo só aceitava como Ben,
     que abre a seleção de aliens, ou já na forma Ultimate).
  4. Ignora player.isabletotransform no caminho do SELECT (só era verdadeira como Ben).
  5. Grava, dentro de 3 funções que o jogo nunca usa, o fluxo dos Ultimate Events:
     volta a ser Ben, guarda os aliens do direcional, carrega o alien e a
     forma Ultimate, vira o alien de novo e, 1 segundo depois, vira Ultimate.
     Apertar SELECT de novo sai da forma Ultimate pelo caminho oficial do jogo
     (undo_ultimate_form), que restaura os aliens do direcional. Se a Ultimate
     acabar sozinha ou você sair pelo direcional, SELECT (até como Ben) restaura.
     Os botões ficam travados durante o carregamento. Como Ben, sem nada
     pendente, SELECT abre a tela de troca de aliens, como no jogo original.
     Um "vigia" (timer) libera as travas dos botões alguns segundos depois de
     entrar ou sair da Ultimate, para os controles nunca ficarem presos.
     Entrar e sair da Ultimate só acontece se o jogador não estiver atacando,
     interagindo, agarrado ou com o movimento bloqueado.
  O arquivo continua com o mesmo tamanho.

FORMATO (descoberto)
  Cabeçalho: 1BADBABE, nº de funções+1, hash, ?, tamanho do código inicial.
  Função: 21 00 00 00 | hash do nome | nº parâmetros | tamanho em palavras
  Instruções de 4 bytes [op a b c]; 03 05 07 08 17 19 20 têm +4 bytes.
    01 r        r = nil            02 r n      r = inteiro n
    03 r f      r = float f        05 r h      r = constante (hash)
    06 a b      rb = ra            07 r h      r = global[h]
    08 r h      global[h] = r      0f a b      rb = não ra
    10/11 a b c rc = (ra == / != rb)          14/15 a b c rc = ra e/ou rb
    17 a b . h  rb = ra.h          18 a b c    rc = ra[rb]
    19 a b . h  ra.h = rb          1d n        vai para n
    1f r n      se não r, vai para n (n = b | c<<8, em palavras desde o início da função)
    20 f a n d  rd = rf(ra, ..., n argumentos)
    21          retorna (dentro de função)

Só usa a biblioteca padrão do Python 3.8+.
"""
import os
import struct
import sys
import zlib

MAGIC = b"\xbe\xba\xad\x1b"
IMM = {0x03: 1, 0x05: 1, 0x07: 1, 0x08: 1, 0x17: 1, 0x19: 1, 0x20: 1}


def crc(s):
    return zlib.crc32(s.lower().encode("latin-1"))


# ----------------------------------------------------------------------
# Leitura
# ----------------------------------------------------------------------

def _corpo(d, p, fim, ops, func):
    while p < fim:
        op = d[p]
        if op == 0x04:
            e = d.index(b"\0", p + 4)
            n = e - (p + 4) + 1
            ops.append((p, op, tuple(d[p + 1:p + 4]), d[p + 4:e], func))
            p += 4 + ((n + 3) // 4) * 4
            continue
        k = IMM.get(op, 0)
        imm = struct.unpack_from("<%dI" % k, d, p + 4) if k else ()
        ops.append((p, op, tuple(d[p + 1:p + 4]), imm, func))
        p += 4 + 4 * k
    return p


def ler(d):
    if d[:4] != MAGIC:
        raise ValueError("não é um script .ds")
    ops, funcs = [], []
    n0 = struct.unpack_from("<I", d, 0x10)[0]
    p = _corpo(d, 0x14, 0x10 + 4 * n0, ops, None)
    while p + 16 <= len(d):
        if d[p] != 0x21:
            raise ValueError("estrutura inesperada em 0x%x" % p)
        h, npar, n = struct.unpack_from("<III", d, p + 4)
        fim = p + 12 + 4 * n
        funcs.append((p, h, npar, fim))
        ops.append((p, 0x21, (0, 0, 0), (h, npar, n), h))
        if _corpo(d, p + 16, fim, ops, h) != fim:
            raise ValueError("função em 0x%x não fecha certo" % p)
        p = fim
    return ops, funcs


# ----------------------------------------------------------------------
# Desmontagem
# ----------------------------------------------------------------------

def carregar_nomes(caminho, d):
    nomes = set()
    if caminho and os.path.exists(caminho):
        nomes |= set(open(caminho, encoding="utf-8", errors="replace").read().split())
    import re
    nomes |= set(x.decode().lower() for x in re.findall(rb"[A-Za-z_][A-Za-z0-9_]{2,60}", d))
    return {crc(n): n for n in nomes}


def texto_instr(op, abc, imm, nm):
    a, b, c = abc
    def h(v):
        return "#" + nm[v] if v in nm else "0x%08x" % v
    if op == 0x04:
        return 'r%d = "%s"' % (a, imm.decode("latin-1"))
    if op == 0x01: return "r%d = nil" % a
    if op == 0x02: return "r%d = %d" % (a, b)
    if op == 0x03: return "r%d = %g" % (a, struct.unpack("<f", struct.pack("<I", imm[0]))[0])
    if op == 0x05: return "r%d = %s" % (a, h(imm[0]))
    if op == 0x06: return "r%d = r%d" % (b, a)
    if op == 0x07: return "r%d = global %s" % (a, h(imm[0]))
    if op == 0x08: return "global %s = r%d" % (h(imm[0]), a)
    if op == 0x0f: return "r%d = not r%d" % (b, a)
    if op == 0x10: return "r%d = (r%d == r%d)" % (c, a, b)
    if op == 0x11: return "r%d = (r%d != r%d)" % (c, a, b)
    if op == 0x14: return "r%d = r%d and r%d" % (c, a, b)
    if op == 0x15: return "r%d = r%d or r%d" % (c, a, b)
    if op == 0x17: return "r%d = r%d.%s" % (b, a, h(imm[0])[1:] if imm[0] in nm else h(imm[0]))
    if op == 0x18: return "r%d = r%d[r%d]" % (c, a, b)
    if op == 0x19: return "r%d.%s = r%d" % (a, h(imm[0])[1:] if imm[0] in nm else h(imm[0]), b)
    if op == 0x1d: return "vai para %d" % (a | (b << 8))
    if op == 0x1f: return "se não r%d, vai para %d" % (a, b | (c << 8))
    if op == 0x20:
        args = ", ".join("r%d" % (b + i) for i in range(c))
        return "r%d = r%d(%s)" % (imm[0], a, args)
    if op == 0x21: return "retorna"
    s = "op%02x %d %d %d" % (op, a, b, c)
    for v in imm:
        s += " " + h(v)
    return s


def cmd_desmontar(origem, destino, arq_nomes):
    d = open(origem, "rb").read()
    ops, funcs = ler(d)
    nm = carregar_nomes(arq_nomes, d)
    inicio = {p: (h, npar, fim) for p, h, npar, fim in funcs}
    with open(destino, "w", encoding="utf-8") as f:
        f.write("; %s - %d funções, %d instruções\n" % (os.path.basename(origem), len(funcs), len(ops)))
        f.write("; inicialização\n")
        base = 0x14
        for p, op, abc, imm, func in ops:
            if p in inicio and op == 0x21 and len(imm) == 3:
                h, npar, fim = inicio[p]
                nome = nm.get(h, "0x%08x" % h)
                f.write("\nfunção %s(%s)    ; arquivo 0x%x\n" % (nome, ", ".join("r%d" % i for i in range(npar)), p))
                base = p + 16
                continue
            f.write("  %4d  %s\n" % ((p - base) // 4, texto_instr(op, abc, imm, nm)))
    print("%s criado (%d funções)" % (destino, len(funcs)))


# ----------------------------------------------------------------------
# Mod: Ultimate a qualquer momento
# ----------------------------------------------------------------------

def instr(op, a=0, b=0, c=0, *imm):
    return bytes((op, a, b, c)) + b"".join(struct.pack("<I", v) for v in imm)


NOP = instr(0x06, 0, 0, 0)  # r0 = r0 (não faz nada)


def chamar0(h):
    """chama a função de hash h sem argumentos"""
    return [instr(0x07, 6, 0, 0, h), instr(0x20, 6, 8, 0, 7)]


def montar(itens):
    """itens: bytes de instr() ou ("rotulo", nome) ou ("se_nao", reg, nome).
    Calcula os destinos dos saltos (em palavras desde o início da função)."""
    pos, rot, tam = 0, {}, []
    for it in itens:
        if isinstance(it, tuple) and it[0] == "rotulo":
            rot[it[1]] = pos
        elif isinstance(it, tuple):
            pos += 1
        else:
            pos += len(it) // 4
    saida = []
    for it in itens:
        if isinstance(it, tuple) and it[0] == "rotulo":
            continue
        if isinstance(it, tuple) and it[0] == "se_nao":
            alvo = rot[it[2]]
            saida.append(instr(0x1F, it[1], alvo & 0xFF, alvo >> 8))
        else:
            saida.append(it)
    return saida

FUNC_ULT = 0x1DA4F7B4        # ativa a forma Ultimate (chamada pelo ícone do evento)
FLAG_EVENTO = 0x28280148     # ligada pelas fases só durante os Ultimate Events
FORMA_ULT = 0xF495406A       # alien que vai virar Ultimate (preenchida pelas fases no evento)
PRECARREGAR = 0xC61AE271     # carrega (alien, ultimate, -, -) e chama o callback no fim
CAMPO_ULT = 0x461241EB       # gformdata[alien].<este campo> = id da forma Ultimate
# Funções do globals.ds que nunca são chamadas (nenhum script, dado ou EBOOT usa).
# O código das 3 etapas é gravado dentro delas, porque o jogo não registra
# funções acrescentadas ao arquivo.
F_SELECT = 0x12E1E367     # etapa 1 (136 palavras livres)
F_CARREGAR = 0x2B1B2ADF   # etapa 2 (112 palavras livres)
F_PRONTO = 0x5C1DF2F7     # etapa 3 (179 palavras livres)
F_TIMER = 0xD03088FD      # etapa 4: chamada pelo timer, ativa a Ultimate (156 palavras livres)
F_SAIR = 0x2843B93B       # sair da Ultimate: libera travas, restaura o direcional (150 livres)
F_VIGIA = 0xD21DA61D      # vigia: alguns segundos depois, libera as travas de qualquer jeito (138 livres)
TRANSF_EM_CURSO = 0x597A958A  # outra trava dos botões (transformação em andamento)
F_ENTRAR = 0xAA74095A     # entrar na Ultimate: checagens + início do fluxo (197 livres)
F_SAIR_SEGURO = 0x3BB14198  # sai da Ultimate só em situação segura (194 livres)
F_SALVAR = 0x0097B937     # guarda a posição do jogador (127 livres)
F_REPOS = 0x8DE6B44B      # devolve o jogador à posição guardada (127 livres)
POS_GUARDADA = crc("luis_pos")
# nº de parâmetros de cada etapa = nº de argumentos com que ela é chamada
# (o jogo recusa a chamada quando não bate)
PARAMS = {F_SELECT: 1, F_CARREGAR: 0, F_PRONTO: 0, F_TIMER: 0, F_SAIR: 0, F_VIGIA: 0,
          F_SALVAR: 0, F_REPOS: 0, F_ENTRAR: 0, F_SAIR_SEGURO: 0}
NOMES_ANTIGOS = ("luis_ultimate_select", "luis_ult_carregar", "luis_ult_pronto")
VOLTAR_BEN = 0xEF438378          # volta a ser Ben e chama o callback
GUARDAR_DIRECIONAL = 0x9A9FABAC  # guarda os aliens do direcional (restaurados ao sair da Ultimate)
VIRAR_ALIEN = 0x49F16B17         # transforma no alien indicado
TABELA_ALIENS = 0xE1003DC4       # devolve a tabela de ids (ben, spidermonkey, ...)
TRAVA_INPUT = 0xC16EF1C4         # quando = 1, switch_form_update ignora os botões
ULTIMO_NORMAL = 0x39A39C8C   # campo da tabela de aliens = 10 (último alien normal)
FUNC_DESTRANSF = 0xF02A2526  # efeito/ação ao apertar transformar já sendo alien
ARG_DESTRANSF = 0xD6819B97


def achar_funcao(funcs, h):
    r = [f for f in funcs if f[1] == h]
    if len(r) != 1:
        raise ValueError("função %08x não encontrada (esse é o globals.ds certo?)" % h)
    return r[0]


def cmd_ultimate_livre(origem, destino, diagnostico=False, rastreio=0):
    d = bytearray(open(origem, "rb").read())
    ops, funcs = ler(bytes(d))
    if diagnostico:
        print("  modo diagnóstico: só o ajuste 3 (o SELECT mantém o efeito original)")

    # 1) remover a checagem da variável de evento e dizer ao jogo qual alien
    #    vira Ultimate: global 0xf495406a = gcurrentcharacter
    #    (fora dos eventos essa variável fica vazia e switch_to_ultimate falha)
    p0, _, _, fim = achar_funcao(funcs, FUNC_ULT)
    if diagnostico:
        fim = p0  # pula o ajuste 1
    corpo = [o for o in ops if o[4] == FUNC_ULT and p0 < o[0] < fim]
    h_gform, h_gcur = crc("gformdata"), crc("gcurrentcharacter")
    feito1 = diagnostico
    for i in range(len(corpo) - 4):
        o = corpo[i:i + 5]
        if (o[0][1] == 0x07 and o[0][3] == (FLAG_EVENTO,) and o[1][1] in (0x1F, 0x06) and
                o[2][1] == 0x07 and o[2][3] == (h_gform,) and
                o[3][1] == 0x07 and o[3][3] == (h_gcur,) and o[4][1] == 0x18):
            r_tab, r_idx = o[2][2][0], o[3][2][0]
            novo = (instr(0x07, r_idx, 0, 0, h_gcur) +           # r_idx = gcurrentcharacter
                    instr(0x08, r_idx, 0, 0, FORMA_ULT) +         # global 0xf495406a = r_idx
                    instr(0x07, r_tab, 0, 0, h_gform) +           # r_tab = gformdata
                    NOP)
            ini, fim_t = o[0][0], o[4][0]
            if len(novo) != fim_t - ini:
                raise ValueError("tamanho inesperado no ajuste 1")
            d[ini:fim_t] = novo
            feito1 = True
            print("  1/5  trava do evento removida e alien atual passado para a forma Ultimate (0x%x)" % ini)
            break
        if (o[0][1] == 0x07 and o[0][3] == (h_gcur,) and o[1][1] == 0x08 and o[1][3] == (FORMA_ULT,)):
            feito1 = True
            print("  1/5  já estava aplicado")
            break
    if not feito1:
        raise ValueError("não achei o começo da função da forma Ultimate")

    # 2) botão de transformar (já como alien) -> forma Ultimate
    h_upd = crc("switch_form_update")
    p1, _, _, fim1 = achar_funcao(funcs, h_upd)
    corpo = [o for o in ops if o[4] == h_upd and p1 < o[0] < fim1]
    feito2 = diagnostico
    for i in range(0 if diagnostico else len(corpo) - 2):
        a, b, c = corpo[i], corpo[i + 1], corpo[i + 2]
        if (a[1] == 0x07 and a[3] == (ARG_DESTRANSF,) and
                b[1] == 0x07 and b[3] == (FUNC_DESTRANSF,) and
                c[1] == 0x20 and c[2][0] == b[2][0] and c[2][1] == a[2][0] and c[2][2] == 1):
            r_arg, r_fn, r_dst = a[2][0], b[2][0], c[3][0]
            novo = (instr(0x01, r_arg) +                    # r_arg = nil
                    instr(0x07, r_fn, 0, 0, F_SELECT) +      # r_fn = etapa 1
                    instr(0x20, r_fn, r_arg, 1, r_dst) +     # chama
                    NOP)
            ini, fim_trecho = a[0], c[0] + 8
            if len(novo) != fim_trecho - ini:
                raise ValueError("tamanho do trecho inesperado")
            d[ini:fim_trecho] = novo
            # o salto anterior separava Ben (tela de troca) de alien; agora a
            # etapa 1 decide os dois casos
            ant = corpo[i - 1]
            if ant[1] == 0x1F:
                d[ant[0]:ant[0] + 4] = NOP
            feito2 = True
            print("  2/5  SELECT (já como alien) ligado à forma Ultimate (0x%x)" % ini)
            break
    if not feito2:
        alvos = [FUNC_ULT, F_SELECT] + [crc(n) for n in NOMES_ANTIGOS]
        for i in range(len(corpo) - 1):
            if corpo[i][1] == 0x07 and corpo[i][3] and corpo[i][3][0] in alvos and corpo[i + 1][1] == 0x20:
                ant = corpo[i - 2] if i >= 2 else None   # (01 r_arg) vem antes do 07
                if ant is not None and ant[1] == 0x1F:
                    d[ant[0]:ant[0] + 4] = NOP
                    print("  2/5  Ben e aliens agora passam pela etapa 1")
                if corpo[i][3][0] != F_SELECT:
                    pos = corpo[i][0] + 4
                    d[pos:pos + 4] = struct.pack("<I", F_SELECT)
                    print("  2/5  SELECT redirecionado para a etapa 1")
                else:
                    print("  2/5  botão SELECT -> etapa 1: já estava aplicado")
                feito2 = True
                break
    if not feito2:
        raise ValueError("não achei o trecho do botão de transformar")

    # 3) liberar o SELECT para os aliens normais (antes só Ben e formas Ultimate)
    feito3 = False
    for i in range(len(corpo) - 2):
        a, b, c = corpo[i], corpo[i + 1], corpo[i + 2]
        if a[1] == 0x17 and a[3] == (ULTIMO_NORMAL,) and b[1] in (0x07, 0x13):
            # procura o "not" logo depois da comparação
            for j in range(i + 1, min(i + 6, len(corpo))):
                if corpo[j][1] == 0x13 and j + 1 < len(corpo):
                    nx = corpo[j + 1]
                    if nx[1] == 0x0F and nx[2][0] == corpo[j][2][2]:
                        dst = nx[2][1]
                        d[nx[0]:nx[0] + 4] = instr(0x02, dst, 1, 0)   # rdst = 1 (sempre verdadeiro)
                        feito3 = True
                        print("  3/5  SELECT liberado para os aliens normais (0x%x)" % nx[0])
                    elif nx[1] == 0x02 and nx[2][1] == 1:
                        feito3 = True
                        print("  3/5  SELECT para aliens normais: já estava aplicado")
                    break
            if feito3:
                break
    if not feito3:
        raise ValueError("não achei a checagem de alien normal")

    # 4) ignorar player.isabletotransform no caminho do SELECT
    #    (ela só libera o SELECT como Ben, que abre a tela de troca de aliens)
    feito4 = diagnostico
    h_iat = crc("isabletotransform")
    for i in range(0 if diagnostico else len(corpo) - 3):
        if corpo[i][1] == 0x17 and corpo[i][3] == (h_iat,):
            r_fn = corpo[i][2][1]
            ch = corpo[i + 1]
            if ch[1] == 0x20 and ch[2][0] == r_fn:
                r_res = ch[3][0]
                nx = corpo[i + 2]
                if nx[1] == 0x14 and nx[2][1] == r_res:
                    d[nx[0]:nx[0] + 4] = instr(0x06, nx[2][0], nx[2][2], 0)  # rc = ra (sem o "and")
                    feito4 = True
                    print("  4/5  checagem isabletotransform ignorada no SELECT (0x%x)" % nx[0])
                elif nx[1] == 0x06 and nx[2][1] != r_res:
                    feito4 = True
                    print("  4/5  isabletotransform: já estava aplicado")
                break
    if not feito4:
        raise ValueError("não achei a checagem isabletotransform")

    # 5) gravar as 3 etapas (o mesmo fluxo dos Ultimate Events) dentro de
    #    funções que o jogo nunca usa:
    #    SELECT -> volta a ser Ben -> guarda os aliens do direcional -> carrega
    #    alien + forma Ultimate -> vira o alien de novo -> 1 s depois, Ultimate.
    if not diagnostico:
        velhas = [f for f in funcs if f[1] in {crc(n) for n in NOMES_ANTIGOS}]
        if velhas:  # remove funções acrescentadas por versões anteriores do mod
            ini_v = min(f[0] for f in velhas)
            fim_v = max(f[3] for f in velhas)
            del d[ini_v:fim_v]
            struct.pack_into("<I", d, 4, struct.unpack_from("<I", d, 4)[0] - len(velhas))
            ops, funcs = ler(bytes(d))
            print("  (removidas %d funções de uma versão anterior do mod)" % len(velhas))
        h_gform, h_gcur = crc("gformdata"), crc("gcurrentcharacter")
        um = struct.unpack("<I", struct.pack("<f", 1.0))[0]
        seis = struct.unpack("<I", struct.pack("<f", 6.0))[0]
        quinze = struct.unpack("<I", struct.pack("<f", 15.0))[0]
        h_player, h_person = crc("player"), crc("person")
        seguro = []   # só transforma se não estiver atacando/interagindo/agarrado/sem movimento
        for k, metodo in enumerate(("isattacking", "isinteracting", "isstruggling")):
            seguro += [
                instr(0x07, 28, 0, 0, h_player), instr(0x07, 25, 0, 0, h_player),
                instr(0x17, 25, 3, 0, h_person), instr(0x20, 3, 28, 1, 20),   # r20 = person
                instr(0x17, 20, 21, 0, crc(metodo)), instr(0x06, 20, 22, 0),
                instr(0x20, 21, 22, 1, 23),                                   # r23 = person.metodo()
                ("se_nao", 23, "ok%d" % k), instr(0x21), ("rotulo", "ok%d" % k),
            ]
        seguro += [
            instr(0x07, 28, 0, 0, h_player), instr(0x07, 25, 0, 0, h_player),
            instr(0x17, 25, 21, 0, crc("isplayermovementdisabled")),
            instr(0x20, 21, 28, 1, 23),
            ("se_nao", 23, "ok_mov"), instr(0x21), ("rotulo", "ok_mov"),
        ]
        etapas = {
            F_SELECT: montar([                          # etapa 1 (SELECT)
                # A) fluxo da Ultimate ativo (alien guardado)? SELECT = sair e restaurar
                instr(0x07, 9, 0, 0, FORMA_ULT),
                ("se_nao", 9, "B"),
                instr(0x07, 2, 0, 0, TABELA_ALIENS), instr(0x20, 2, 8, 0, 3),
                instr(0x17, 3, 4, 0, crc("ben")),
                instr(0x07, 5, 0, 0, h_gcur), instr(0x10, 5, 4, 6),   # r6 = (é o Ben?)
                ("se_nao", 6, "A_alien"),
                *chamar0(F_SAIR),                                       # já é Ben: sai direto
                instr(0x21),
                ("rotulo", "A_alien"),
                *chamar0(F_SAIR_SEGURO),                               # checa e volta a ser Ben
                instr(0x21),
                # B) é o Ben? SELECT abre a tela de troca de aliens (comportamento original)
                ("rotulo", "B"),
                instr(0x07, 2, 0, 0, TABELA_ALIENS), instr(0x20, 2, 8, 0, 3),
                instr(0x17, 3, 4, 0, crc("ben")),
                instr(0x07, 10, 0, 0, h_gcur), instr(0x10, 10, 4, 6),
                ("se_nao", 6, "C"),
                instr(0x07, 28, 0, 0, crc("overlay")),
                instr(0x07, 29, 0, 0, crc("characterpresetscreen_enter")),
                instr(0x07, 25, 0, 0, crc("overlay")),
                instr(0x17, 25, 3, 0, crc("runuser")), instr(0x20, 3, 28, 2, 4),
                instr(0x07, 28, 0, 0, 0x23F332A3), instr(0x07, 25, 0, 0, 0x801B4AF7),
                instr(0x20, 25, 28, 1, 3),
                instr(0x21),
                # C) alien: entrar na forma Ultimate
                ("rotulo", "C"),
                *chamar0(F_ENTRAR),
                instr(0x21),
            ]),
            F_ENTRAR: montar([                          # entrar na forma Ultimate (só em situação segura)
                instr(0x07, 2, 0, 0, h_gform), instr(0x07, 3, 0, 0, h_gcur),
                instr(0x18, 2, 3, 4), instr(0x17, 4, 5, 0, CAMPO_ULT),   # r5 = forma Ultimate
                ("se_nao", 5, "fim"),
                *seguro,
                instr(0x07, 3, 0, 0, h_gcur),
                instr(0x02, 6, 1, 0), instr(0x08, 6, 0, 0, TRAVA_INPUT),  # trava durante o carregamento
                instr(0x08, 3, 0, 0, FORMA_ULT),                          # guarda o alien
                instr(0x07, 8, 0, 0, F_VIGIA), instr(0x03, 9, 0, 0, quinze),  # vigia em 15 s
                instr(0x03, 10, 0, 0, um), instr(0x07, 6, 0, 0, crc("createtimer")),
                instr(0x20, 6, 8, 3, 7),
                instr(0x07, 8, 0, 0, F_CARREGAR),                         # volta a ser Ben e
                instr(0x07, 6, 0, 0, VOLTAR_BEN), instr(0x20, 6, 8, 1, 7),  # depois etapa 2
                ("rotulo", "fim"),
                instr(0x21),
            ]),
            F_CARREGAR: montar([                        # etapa 2 (já como Ben)
                *chamar0(GUARDAR_DIRECIONAL),           # guarda os aliens do direcional
                instr(0x07, 8, 0, 0, FORMA_ULT),        # r8 = alien
                instr(0x07, 2, 0, 0, h_gform),
                instr(0x18, 2, 8, 4), instr(0x17, 4, 9, 0, CAMPO_ULT),   # r9 = forma Ultimate
                instr(0x01, 10), instr(0x01, 11),
                instr(0x07, 12, 0, 0, F_PRONTO),        # r12 = etapa 3
                instr(0x07, 6, 0, 0, PRECARREGAR), instr(0x20, 6, 8, 5, 7),  # carrega
                instr(0x21),
            ]),
            F_PRONTO: montar([                          # etapa 3 (carregamento terminou)
                instr(0x07, 8, 0, 0, FORMA_ULT),
                instr(0x07, 6, 0, 0, VIRAR_ALIEN), instr(0x20, 6, 8, 1, 7),  # vira o alien
                instr(0x07, 8, 0, 0, F_TIMER),          # 1 s depois: etapa 4
                instr(0x03, 9, 0, 0, um), instr(0x03, 10, 0, 0, um),
                instr(0x07, 6, 0, 0, crc("createtimer")), instr(0x20, 6, 8, 3, 7),
                instr(0x21),
            ]),
            F_TIMER: montar([                           # etapa 4 (timer)
                instr(0x01, 8),
                instr(0x07, 6, 0, 0, FUNC_ULT), instr(0x20, 6, 8, 1, 7),  # ativa a Ultimate
                instr(0x21),
            ]),
            F_SAIR: montar([                            # sair da Ultimate (já como Ben)
                instr(0x01, 6),
                instr(0x08, 6, 0, 0, TRAVA_INPUT),      # libera as travas ANTES de restaurar
                instr(0x08, 6, 0, 0, TRANSF_EM_CURSO),
                *chamar0(crc("undo_ultimate_form")),    # remove a Ultimate e restaura o direcional
                instr(0x07, 8, 0, 0, F_VIGIA), instr(0x03, 9, 0, 0, seis),  # vigia em 6 s
                instr(0x03, 10, 0, 0, um), instr(0x07, 6, 0, 0, crc("createtimer")),
                instr(0x20, 6, 8, 3, 7),
                instr(0x21),
            ]),
            F_VIGIA: montar([                           # libera as travas de qualquer jeito
                instr(0x01, 6),
                instr(0x08, 6, 0, 0, TRAVA_INPUT),
                instr(0x08, 6, 0, 0, TRANSF_EM_CURSO),
                instr(0x21),
            ]),
            F_SAIR_SEGURO: montar([                     # só sai se for seguro
                *seguro,
                instr(0x07, 8, 0, 0, F_SAIR),           # volta a ser Ben e sai
                instr(0x07, 6, 0, 0, FUNC_DESTRANSF), instr(0x20, 6, 8, 1, 7),
                instr(0x21),
            ]),
            # versões anteriores usavam estas duas para teletransportar o jogador
            # (playermgr.beam), mas isso deixava o personagem de lado: agora vazias
            F_SALVAR: [instr(0x21)],
            F_REPOS: [instr(0x21)],
        }
        if rastreio:
            # sinal: trava o direcional (mesma variável que a forma Ultimate liga)
            alvo = [F_SELECT, F_CARREGAR, F_PRONTO, F_TIMER][rastreio - 1]
            sinal = [instr(0x02, 20, 1, 0), instr(0x08, 20, 0, 0, TRAVA_INPUT)]  # 3 palavras
            novo_corpo = []
            for ins in etapas[alvo]:
                if ins[0] == 0x1F:   # corrige o destino do salto (+3 palavras)
                    alvo_salto = ins[2] | (ins[3] << 8)
                    ins = instr(0x1F, ins[1], (alvo_salto + 3) & 0xFF, (alvo_salto + 3) >> 8)
                novo_corpo.append(ins)
            etapas[alvo] = sinal + novo_corpo
            print("  rastreio: a etapa %d trava o direcional assim que começa" % rastreio)
        for h, corpo_f in etapas.items():
            p, _, _, fim_f = achar_funcao(funcs, h)
            codigo = b"".join(corpo_f)
            espaco = fim_f - (p + 16)
            if len(codigo) > espaco:
                raise ValueError("função %08x pequena demais" % h)
            d[p + 16:fim_f] = codigo + NOP * ((espaco - len(codigo)) // 4)
            struct.pack_into("<I", d, p + 8, PARAMS[h])
        print("  5/5  funções gravadas em funções que o jogo não usa (vigia + entrada e saída seguras)")

    ler(bytes(d))  # confere se o script continua válido
    with open(destino, "wb") as f:
        f.write(d)
    print("%s criado (%d bytes)" % (destino, len(d)))


def cmd_gerar_nomes(eboot, pasta, destino):
    import re
    nomes = set()
    arquivos = [eboot]
    for raiz, _, lista in os.walk(pasta):
        for n in lista:
            if n.lower().endswith((".ds", ".ddf", ".txt", ".psp")):
                arquivos.append(os.path.join(raiz, n))
    for caminho in arquivos:
        d = open(caminho, "rb").read()
        nomes |= set(x.decode().lower() for x in re.findall(rb"[A-Za-z_][A-Za-z0-9_\-./\\]{2,60}", d))
    nomes |= {"luis_pos"}
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(nomes)) + "\n")
    print("%s criado com %d nomes (de %d arquivos)" % (destino, len(nomes), len(arquivos)))


def main():
    a = sys.argv[1:]
    nomes = None
    if "--nomes" in a:
        i = a.index("--nomes")
        nomes = a[i + 1]
        del a[i:i + 2]
    try:
        if len(a) == 3 and a[0] == "desmontar":
            cmd_desmontar(a[1], a[2], nomes)
        elif len(a) == 4 and a[0] == "gerar-nomes":
            cmd_gerar_nomes(a[1], a[2], a[3])
        elif len(a) == 3 and a[0] == "ultimate-livre":
            cmd_ultimate_livre(a[1], a[2])
        elif len(a) == 4 and a[0] == "rastreio" and a[1] in ("1", "2", "3", "4"):
            cmd_ultimate_livre(a[2], a[3], rastreio=int(a[1]))
        elif len(a) == 3 and a[0] == "diagnostico-select":
            cmd_ultimate_livre(a[1], a[2], diagnostico=True)
        else:
            print(__doc__)
            sys.exit(1)
    except (OSError, ValueError) as e:
        sys.exit("Erro: %s" % e)


if __name__ == "__main__":
    main()
