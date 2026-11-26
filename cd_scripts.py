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

  Aplicar o mod "Ultimate a qualquer momento" (sempre a partir do globals.ds ORIGINAL;
  se você passar um arquivo que já tem ESTA versão do mod, ele é tirado antes):
    python cd_scripts.py ultimate-livre globals.ds globals_mod.ds
    (--sem-rede desliga a rede de segurança contra quedas;
     --sem-habilidades deixa as Ultimates só com as habilidades originais;
     --gigante liga Tartagira -> Gigante; precisa do g_wayb.psp do cd_anims.py --gigante;
     --ben-gigante: segurando o botão de especiais como Ben, a roda mostra os golpes do Gigante;
     --sem-intro: sem a animação de transformação na 1ª Ultimate de cada fase)

  Conferir na ISO se algum nome usado pelo mod já existe no jogo (opcional):
    python cd_scripts.py verificar-funcoes jogo.iso relatorio_funcoes.txt

  Experimento: especiais das Ultimates
    python cd_scripts.py especiais-ultimate pasta_com_atk_u pasta_saida

  REGRAS DO INTERPRETADOR (lidas no EBOOT, 0x8950354):
    0x02 cria um BOOLEANO (0/1); só números float (0x03) aceitam soma e comparação.
    Conta com booleano não dá erro visível: o resultado só não é gravado.
    nil e falso são falsos; qualquer número (até 0.0) é verdadeiro.
  CARREGADOR (EBOOT 0x8952c4c): registra, em ordem, as funções que o cabeçalho
    anunciar; uma função com o mesmo nome de outra substitui a anterior.

O QUE O MOD ULTIMATE-LIVRE FAZ
  Nenhum byte das funções do jogo é alterado. O mod acrescenta no fim do arquivo:
  - 17 funções novas com nomes próprios (luis_f_...);
  - cópias ajustadas de funções do jogo (valem no lugar das originais):
    switch_form_update (SELECT chama o mod; a roda do canto passa pelo mod; quando
    o jogo ignora os botões, o mod confere se a trava ficou presa), a função que
    guarda o direcional (se uma fase começar um Ultimate Event enquanto o mod
    segura os seus aliens, ela recebe a cópia verdadeira) e as 2 das áreas de
    câmera fixa (SELECT ainda sai da Ultimate do mod).
  Fluxo (o mesmo dos Ultimate Events): SELECT como alien -> volta a ser Ben ->
  guarda o direcional -> carrega o alien e a Ultimate -> vira o alien -> 1 s depois
  vira Ultimate (o HUD mostra os golpes). SELECT de novo sai e devolve o direcional.
  A função da Ultimate das fases (0x1da4f7b4) fica original: os eventos das fases
  funcionam como no jogo e, durante eles, o SELECT não mexe em nada. O direcional
  é sempre o do jogo (o mod só trava os botões enquanto carrega). Monitor, vigias
  e a vigia por quadro liberam travas presas e devolvem o direcional sozinhos.
  A rede de segurança contra quedas só funciona enquanto o mod está em ação.
  As Ultimates ganham as habilidades do alien normal (Humungossauro Supremo empurra
  caixas; Aranha Macaca Suprema solta teia; Gelo Fumaça Supremo plana etc.), também
  nos eventos das fases.
  EXPERIMENTAL (--gigante): Tartagira + SELECT vira o Gigante, com tamanho 1,6 em vez
  de 3; ao sair, tira da memória e devolve o direcional. PRECISA do global/g_wayb.psp
  montado pelo cd_anims.py --gigante (o original não tem modelo nem esqueleto: o
  esqueleto do Gigante fica no pacote da fase final, l_tokd.psp). Aliens sem Ultimate:
  SELECT não faz nada.
  O arquivo fica ~7,6 KB maior: o cd_iso.py põe ele no fim da ISO.

FORMATO (descoberto)
  Cabeçalho: 1BADBABE, nº de funções+1, hash, ?, tamanho do código inicial.
  Função: 21 00 00 00 | hash do nome | nº parâmetros | tamanho em palavras
  Instruções de 4 bytes [op a b c]; 03 05 07 08 17 19 20 têm +4 bytes.
    01 r        r = nil            02 r b      r = booleano (b = 0 ou 1)
    03 r f      r = float f        05 r h      r = constante (hash)
    06 a b      rb = ra            07 r h      r = global[h]
    08 r h      global[h] = r      0f a b      rb = não ra
    0a/0b a b c rc = ra + / - rb (só float)   13 a b c    rc = (ra > rb) (só float)
    10/11 a b c rc = (ra == / != rb)          14/15 a b c rc = ra e/ou rb
    17 a b . h  rb = ra.h          18 a b c    rc = ra[rb]
    19 a b . h  ra.h = rb          1d n        vai para n
    1e/1f r n   se r / se não r, vai para n (n = b | c<<8, em palavras desde o início da função)
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


def trocar_ordem(d, de=">", para="<"):
    """Converte um .ds entre a ordem de bytes do PSP (little-endian) e a do PS3/Xbox 360 (big-endian).
    Cada palavra de instrução e cada número trocam a ordem dos bytes; o texto das strings (instrução 0x04)
    fica como está."""
    def op_de(p):
        return d[p + 3] if de == ">" else d[p]

    def palavra(p):
        return struct.pack(para + "I", struct.unpack_from(de + "I", d, p)[0])

    out = bytearray()
    for p in range(0, 0x14, 4):                    # assinatura + cabeçalho
        out += palavra(p)
    n0 = struct.unpack_from(de + "I", d, 0x10)[0]

    def corpo(p, fim):
        while p < fim:
            op = op_de(p)
            out.extend(palavra(p))
            if op == 0x04:
                e = d.index(b"\0", p + 4)
                n = ((e - (p + 4) + 1 + 3) // 4) * 4
                out.extend(d[p + 4:p + 4 + n])
                p += 4 + n
                continue
            for i in range(IMM.get(op, 0)):
                out.extend(palavra(p + 4 + 4 * i))
            p += 4 + 4 * IMM.get(op, 0)
        return p

    p = corpo(0x14, 0x10 + 4 * n0)
    while p + 16 <= len(d):
        if op_de(p) != 0x21:
            raise ValueError("estrutura inesperada em 0x%x" % p)
        h, npar, n = struct.unpack_from(de + "III", d, p + 4)
        for i in range(4):
            out += palavra(p + 4 * i)
        fim = p + 12 + 4 * n
        if corpo(p + 16, fim) != fim:
            raise ValueError("função em 0x%x não fecha certo" % p)
        p = fim
    while p + 4 <= len(d):                         # palavra final (0x21 que fecha o arquivo)
        out += palavra(p)
        p += 4
    out += d[p:]
    return bytes(out)


def ler(d):
    if d[:4] == MAGIC[::-1]:                       # .ds do PS3/Xbox 360 (big-endian)
        d = trocar_ordem(d)
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
#
# COMO O JOGO CARREGA UM .ds (lido no EBOOT, rotina 0x8952c4c)
#   O cabeçalho diz quantas funções existem (+1 do código inicial). O carregador
#   registra, em ordem, cada função [hash][nº de parâmetros][tamanho][código] como
#   variável global com aquele hash (rotina 0x894fc6c: se o nome já existe, a nova
#   SUBSTITUI a antiga). Por isso o mod:
#     - não mexe em NENHUM byte das funções do jogo;
#     - acrescenta no fim do arquivo as funções dele, com nomes próprios (luis_f_...);
#     - acrescenta também cópias ajustadas de 4 funções do jogo, com o mesmo nome
#       (switch_form_update, a que guarda o direcional e as 2 de câmera fixa).
#       Como elas vêm depois, valem no lugar das originais.
#   Se por algum motivo o jogo não lesse o fim do arquivo, ficaria tudo original.
#
# Versões anteriores do mod gravavam o código DENTRO de funções do globals.ds que
# pareciam sem uso. O relatório verificar-funcoes mostrou que quase todas são
# usadas pela IA dos inimigos (ai_globl.ddf), pelos pacotes de personagem (g_ec.psp)
# ou pelo próprio EBOOT (ex.: 0x74879a8a mostra/esconde o HUD).

def instr(op, a=0, b=0, c=0, *imm):
    if op == 0x02 and (b not in (0, 1) or c != 0):
        # Lido no interpretador do EBOOT: 0x02 cria um BOOLEANO (tipo 1). O jogo só
        # soma/compara números do tipo float (0x03); conta com booleano dá erro e o
        # resultado não é gravado. Para números use num().
        raise ValueError("0x02 só serve para falso/verdadeiro (0/1), não %d" % b)
    return bytes((op, a, b, c)) + b"".join(struct.pack("<I", v) for v in imm)


def num(r, v):
    """r = número (float), o único tipo com que o jogo faz contas e comparações"""
    return instr(0x03, r, 0, 0, struct.unpack("<I", struct.pack("<f", float(v)))[0])


NOP = instr(0x06, 0, 0, 0)  # r0 = r0 (não faz nada)
RETORNA = instr(0x21)


def chamar0(h):
    """chama a função de hash h sem argumentos"""
    return [instr(0x07, 6, 0, 0, h), instr(0x20, 6, 8, 0, 7)]


def montar(itens):
    """itens: bytes de instr() ou ("rotulo", nome), ("se_nao", reg, nome), ("vai", nome).
    Calcula os destinos dos saltos (em palavras desde o início da função)."""
    pos, rot = 0, {}
    for it in itens:
        if isinstance(it, tuple) and it[0] == "rotulo":
            if it[1] in rot:
                raise ValueError("rótulo repetido: %s" % it[1])
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
        elif isinstance(it, tuple) and it[0] == "vai":
            alvo = rot[it[1]]
            saida.append(instr(0x1D, alvo & 0xFF, alvo >> 8, 0))
        else:
            saida.append(it)
    return saida


def realocar(corpo, desloc):
    """Soma desloc (palavras) aos destinos dos saltos de um corpo de função."""
    ops = []
    _corpo(corpo, 0, len(corpo), ops, None)
    out = bytearray(corpo)
    for p, op, (a, b, c), imm, _ in ops:
        if op == 0x1D:
            t = (a | b << 8) + desloc
            out[p + 1], out[p + 2] = t & 0xFF, t >> 8
        elif op in (0x1E, 0x1F):
            t = (b | c << 8) + desloc
            out[p + 2], out[p + 3] = t & 0xFF, t >> 8
        elif op in (0x1B, 0x1C):
            raise ValueError("instrução de salto desconhecida (0x%02x)" % op)
    return bytes(out)


def registro(h, npar, corpo):
    """Uma função no formato do arquivo: [hash][parâmetros][tamanho][corpo][21]"""
    if len(corpo) % 4:
        raise ValueError("corpo desalinhado")
    return struct.pack("<III", h, npar, len(corpo) // 4 + 1) + corpo + RETORNA


# --- do jogo -----------------------------------------------------------
FUNC_ULT = 0x1DA4F7B4        # ativa a Ultimate nos eventos das fases (o mod NÃO mexe nela)
FORMA_ULT = 0xF495406A       # alien que vira Ultimate (a fase preenche no começo do evento;
                             # loadpreultimateform esvazia no fim)
EVENTO_ULT = 0x28280148      # ligada pelas fases (Roma de dia nunca desliga)
PRECARREGAR = 0xC61AE271     # carrega (alien, ultimate, -, -) e chama o callback no fim
CAMPO_ULT = 0x461241EB       # gformdata[alien].<este campo> = id da forma Ultimate
VOLTAR_BEN = 0xEF438378      # volta a ser Ben e chama o callback
GUARDAR_DIRECIONAL = 0x9A9FABAC  # guarda os aliens do direcional em BACKUP_JOGO
RESTAURAR_DIRECIONAL = 0x8EE0F42C  # carrega os aliens de BACKUP_JOGO e chama o callback
VIRAR_ALIEN = 0x49F16B17     # transforma no alien indicado
TABELA_ALIENS = 0xE1003DC4   # devolve a tabela de ids (ben, spidermonkey, ...)
TRAVA_INPUT = 0xC16EF1C4     # ligada: switch_form_update ignora os botões
TRANSF_EM_CURSO = 0x597A958A # outra trava dos botões (transformação em andamento)
ULTIMO_NORMAL = 0x39A39C8C   # campo da tabela de aliens = 10 (último alien normal)
FUNC_DESTRANSF = 0xF02A2526  # volta a ser Ben com o efeito do jogo e chama o callback
ARG_DESTRANSF = 0xD6819B97
BACKUP_JOGO = 0x90E796D7     # onde o jogo guarda a cópia do direcional
ORIG_DPAD = 0x66960347       # troca de alien pelo direcional (gld_psp.ds) - fica original
ORIG_RODA = 0x8F436AD3       # atualiza a roda do canto (circdisp.ds)
SEM_TROCA = False             # diagnóstico 360: carrega só a Ultimate, sem trocar o direcional
MANTER_ULTIMATE = False       # diagnóstico: ao sair, não tira a Ultimate da memória
BOTAO_TROCA = "btn_select"   # botão que entra/sai da Ultimate (no Xbox 360 vira "btn_r3")
BOTAO_ESPECIAIS = 0x643CCFE7 # campo do controle: segurando o botão que mostra os especiais
ZONAS_CAMERA = (0x9AD2BFC4, 0x3482B9BD)  # desligam a troca de alien (câmera fixa)
IDS_ULTIMATE = (0xF54B5E78, 0x0AA213A1, 0xD1349EEF, 0xF02188EC, 0xBCE02525)  # campos da tabela
CHARMGR = 0x93ACA275
CARGAS = crc("luis_cargas")             # partes da Ultimate ainda carregando
CARREGADAS = crc("luis_ult_carregadas")
CARREGADAS_MISSAO = crc("luis_ult_carregadas_m")  # Ultimates já carregadas nesta fase (sem troca)
PASTA_DADOS, PASTA_DESC = 0x0BFBFD2D, 0x79C61E79   # globais que o jogo passa a loaddata/loaddesc
MORTO = 0x677FCE7E           # = verdadeiro enquanto o jogador está morto
ZONA_ATIVA = 0x9CC5B0B4      # = verdadeiro dentro das áreas de câmera fixa
OUTRA_TRAVA = 0xC0468A8C     # o jogo liga enquanto recarrega o checkpoint
H_UPD = crc("switch_form_update")
LIMPA_TARTAGIRA = 0xC7A0B380  # desliga o redemoinho da Tartagira (gld_psp.ds)


# --- funções novas do mod (acrescentadas no fim do arquivo) -----------------
def _fn(nome):
    return crc("luis_f_" + nome)


F_SELECT = _fn("select")          # SELECT (Ben ou alien normal)
F_ENTRAR = _fn("entrar")          # checagens + início da entrada
F_CARREGAR = _fn("carregar")      # já como Ben: guarda o direcional e carrega a Ultimate
F_PRONTO = _fn("pronto")          # carregou: vira o alien
F_ATIVAR = _fn("ativar")          # 1 s depois: vira Ultimate (o mesmo que o jogo faz no evento)
F_MONITOR = _fn("monitor")        # a cada 1,5 s confere se a Ultimate continua
F_FIM = _fn("fim")                # a Ultimate acabou sem o SELECT: devolve
F_SAIR = _fn("sair")              # já como Ben: devolve os aliens do direcional
F_SAIR_SEGURO = _fn("sair_seguro")  # sai da Ultimate se for seguro
F_DEVOLVIDO = _fn("devolvido")    # callback: direcional devolvido
F_VIGIA = _fn("vigia")            # 15 s após entrar: solta a trava se a entrada empacou
F_UM = _fn("carga_um")           # (sem trocar o direcional) uma parte da Ultimate carregou
F_VIGIA_SAIDA = _fn("vigia_saida")  # 10 s após sair: solta se a devolução empacou
F_DESTRAVA = _fn("destrava")      # Ultimate sem resposta: solta as travas
F_RODA = _fn("roda")              # no lugar da roda do canto (repassa sempre)
F_ZONA = _fn("zona")              # controle nas áreas de câmera fixa
F_INTRO = _fn("intro")            # fim da animação de transformação (1ª vez na fase)
F_INTRO_T = _fn("intro_t")        # o mesmo, chamado pelo timer de segurança (sem argumento)
F_POSE = _fn("pose")              # a Ultimate recém-chegada faz a pose (corpo já trocado)
F_POSE_FIM = _fn("pose_fim")      # fim da pose: devolve o movimento
F_GRITO = _fn("grito")            # a Ultimate grita o próprio nome (vozes das fases)
F_QUADRO = _fn("quadro")          # a cada quadro em que o jogo ignora os botões
F_REDE = _fn("rede")              # rede de segurança contra quedas (só com o mod em ação)
F_GIG_ENTRAR = _fn("gig_entrar")  # Gigante: Tartagira + SELECT
F_GIG_CARREGAR = _fn("gig_carregar")  # já como Ben: carrega o Gigante no direcional
F_GIG_MODELO = _fn("gig_modelo")  # animações carregadas: carrega o modelo (l_tokd/g_wayb.psp)
F_GIG_PRONTO = _fn("gig_pronto")  # modelo carregado: vira o Gigante
F_GIG_CB = _fn("gig_cb")          # fim da animação de virar o Gigante
NPAR_MOD = {F_SELECT: 1, F_RODA: 3, F_ZONA: 3, F_QUADRO: 1, F_GIG_PRONTO: 1, F_INTRO: 1, F_UM: 1}
TRANSF_GIGANTE = 0xB7269B14  # vira o Gigante (usa character_waybig e os golpes de atk_wb.ddf)
# No jogo original o Gigante está espalhado: global/g_wayb.psp só tem ANIMAÇÕES,
# l_tokd/g_wayb.psp tem MODELO e texturas, e o ESQUELETO fica em l_tokd/l_tokd.psp (pacote da
# fase final, carregado só nela). O cd_anims.py --gigante junta tudo no global/g_wayb.psp.
GIG_PASTA, GIG_MODELO = "l_tokd", "g_wayb"
ESCALA_GIGANTE = 1.6         # a fase final usa 3.0 (luta guiada); 1.6 cabe melhor nas fases

# --- variáveis do mod ------------------------------------------------------
SAINDO = crc("luis_saindo")
RESTAURANDO = crc("luis_restaurando")
ATIVA = crc("luis_ativa")              # Ultimate do mod ativa (monitor ligado)
PENDENTE = crc("luis_pendente")        # direcional guardado e ainda não devolvido
ALIEN_MOD = crc("luis_alien")          # alien que o mod está transformando
FORMA_MOD = crc("luis_forma_mod")      # valor que o mod pôs em FORMA_ULT
TRAVA_MOD = crc("luis_trava_mod")      # a trava dos botões ligada é do mod
COPIA_DIRECIONAL = crc("luis_copia_direcional")
ESPERA = crc("luis_espera")
PARADO = crc("luis_parado")
BATIDA = crc("luis_batida")            # a roda rodou desde a última conferida
RECUSAS = crc("luis_recusas")          # quadros com SELECT recusado (jogo "ocupado")
QUADROS = crc("luis_quadros")          # quadros com a devolução parada
QUADROS_TRAVA = crc("luis_quadros_trava")  # quadros com a trava ligada
FALHAS = crc("luis_falhas")            # devoluções que empacaram seguidas
VIGIAS = crc("luis_vigias")
VIGIAS_SAIDA = crc("luis_vigias_saida")
REDE_Y = crc("luis_rede_y")            # altura na última conferida
REDE_POS = crc("luis_rede_pos")        # último lugar seguro (no chão)
REDE_QUEDA = crc("luis_rede_queda")    # conferidas seguidas caindo
REDE_FIRME = crc("luis_rede_firme")    # conferidas seguidas parado na mesma altura
REDE_VIVA = crc("luis_rede_viva")
GIGANTE = crc("luis_gigante")          # o mod está com o Gigante (carregado por ele)
GIG_CARREGADO = crc("luis_gig_carregado")  # o modelo do Gigante foi carregado pelo mod
QUADROS_INTERAGINDO = crc("luis_quadros_interagindo")  # quadros "interagindo" sem sair do lugar
INTRO_EM_CURSO = crc("luis_intro_em_curso")   # animação de transformação tocando
POSE_TRAVADA = crc("luis_pose_travada")        # o mod travou o movimento (playermgr:lockmovement)
DURACAO_POSE = 1.5     # movimento travado no começo da pose (a pose inteira tem ~6,5 s e era
                       # lenta demais: depois disso, andar ou atacar já interrompe)
BEN_GRANDE = crc("luis_ben_grande")            # Ben gigante ligado (R + SELECT)
R_SEGURO = crc("luis_r_seguro")                # R segurado no último quadro (F_SELECT não recebe o controle)
SEL_ANTES = crc("luis_sel_antes")              # SELECT no quadro anterior (para pegar o aperto)
FALA_ULTIMATES = 0xE8C0396D    # falante das Ultimates (scripts vo_<fase>.ds; cd_vozes.py completa)
PRIORIDADE_VO = 0xDA9FD054     # prioridade de fala que as fases usam
GRITOS = {"humongousaur": "humongousaur", "spidermonkey": "spidermonkey", "bigchill": "bigchill",
          "echo": "echoecho", "swampfire": "swampfire"}   # campo da tabela -> nome na fala
ESCALA_BEN = 1.8
# 1ª Ultimate de cada alien em cada fase: a animação que as fases usam nos eventos
# (alien "carregando" -> troca -> Ultimate posando). O Fogo-Fátuo não tem a animação.
INTRO = {  # alien: (prefixo do alien normal, prefixo da Ultimate, variável "já vi nesta fase")
    "humongousaur": ("humongousaur", "ulthumong", crc("luis_intro_hm")),
    "spidermonkey": ("spidermonkey", "ultspidermonkey", crc("luis_intro_sm")),
    "bigchill": ("bigchill", "ultbigchill", crc("luis_intro_bc")),
    "echo": ("echo", "ultechoecho", crc("luis_intro_ec")),
}
ESP_BEN = crc("luis_esp_ben")          # especiais do Gigante já registrados neste Ben
# golpes especiais do Gigante acrescentados no atk_bn.ddf pelo cd_anims.py --ben-gigante
ESPECIAIS_BEN = (crc("ben_elbow_smash"), crc("ben_fistpummel"), crc("ben_flying_heel"))
INT_X = crc("luis_int_x")
INT_Z = crc("luis_int_z")
LIMITE_INTERACAO = 300       # ~10 s a 30 quadros/s (rede de segurança; com as animações copiadas
                             # a Ultimate termina a interação sozinha)

FUNCOES_MOD = (F_GIG_ENTRAR, F_GIG_CARREGAR, F_GIG_MODELO, F_GIG_PRONTO, F_GIG_CB, F_SELECT, F_ENTRAR, F_CARREGAR, F_PRONTO, F_ATIVAR, F_MONITOR, F_FIM,
               F_SAIR, F_SAIR_SEGURO, F_DEVOLVIDO, F_VIGIA, F_VIGIA_SAIDA, F_DESTRAVA,
               F_RODA, F_ZONA, F_QUADRO, F_REDE, F_INTRO, F_INTRO_T, F_POSE, F_POSE_FIM, F_GRITO, F_UM)
VARIAVEIS_MOD = (GIGANTE, GIG_CARREGADO, SAINDO, RESTAURANDO, ATIVA, PENDENTE, ALIEN_MOD, FORMA_MOD, TRAVA_MOD,
                 COPIA_DIRECIONAL, ESPERA, PARADO, BATIDA, RECUSAS, QUADROS, QUADROS_TRAVA,
                 FALHAS, VIGIAS, VIGIAS_SAIDA, REDE_Y, REDE_POS, REDE_QUEDA, REDE_FIRME, REDE_VIVA,
                 QUADROS_INTERAGINDO, INT_X, INT_Z, ESP_BEN, INTRO_EM_CURSO, POSE_TRAVADA, BEN_GRANDE, R_SEGURO, SEL_ANTES) + tuple(v[2] for v in INTRO.values())
APLICA_HABILIDADES = 0x65661824   # liga/desliga as habilidades do jogador conforme a soma de bits
# (função da transformação na Ultimate, habilidades da Ultimate, habilidades do alien normal)
# Bits: 1 pular, 2/4/8 (nomes não identificados; só alguns aliens têm), 32 empurrar caixa,
#       64 correr, 128 planar, 1024 atacar, 2048 defender, 4096 teia.
#       As Ultimates só têm 1+64+1024+2048.
HABILIDADES_ULTIMATE = (
    (0xD322606E, 0x6A6B8C5D, 0x2110921C),   # Humungossauro Supremo <- Humungossauro (empurra caixa)
    (0x29A1FB23, 0x54553B00, 0x1F2E2541),   # Aranha Macaca Suprema <- Aranha Macaca (teia, 2/4/8)
    (0x9D32DDF9, 0xE81BB8F4, 0xE9678C14),   # Fogo Fátuo Supremo <- Fogo Fátuo (2/4/8)
    (0x18D05CF7, 0xF0B32374, 0x57F6C535),   # Gelo Fumaça Supremo <- Gelo Fumaça (plana, 2/4/8)
)                                           # (Eco Eco: as duas formas já têm as mesmas)
SUBSTITUIDAS = (H_UPD, GUARDAR_DIRECIONAL) + ZONAS_CAMERA + tuple(x[0] for x in HABILIDADES_ULTIMATE)
LIMITE_QUADROS = 450         # ~15 s a 30 quadros/s (7,5 s se o jogo rodar a 60)


def achar_funcao(funcs, h):
    r = [f for f in funcs if f[1] == h]
    if len(r) != 1:
        raise ValueError("função %08x não encontrada (esse é o globals.ds certo?)" % h)
    return r[0]


def remover_mod(d):
    """Se o arquivo já tem este mod (funções acrescentadas no fim), devolve o original."""
    ops, funcs = ler(d)
    mod = set(FUNCOES_MOD)
    idx = next((i for i, f in enumerate(funcs) if f[1] in mod), None)
    if idx is None:
        return d, 0
    resto = funcs[idx:]
    if any(f[1] not in mod and f[1] not in SUBSTITUIDAS for f in resto):
        raise ValueError("o fim do arquivo tem funções que não são do mod")
    corte = funcs[idx][0] + 4
    out = bytearray(d[:corte])
    struct.pack_into("<I", out, 4, struct.unpack_from("<I", out, 4)[0] - len(resto))
    return bytes(out), len(resto)


def conferir_original(d, ops, funcs):
    """Recusa arquivos alterados por versões antigas (que mexiam dentro das funções)."""
    p, _, _, fim = achar_funcao(funcs, FUNC_ULT)
    corpo = d[p + 16:fim]
    if instr(0x08, 0, 0, 0, FORMA_ULT)[4:] in corpo or instr(0x07, 0, 0, 0, EVENTO_ULT)[4:] not in corpo:
        raise ValueError("este globals.ds foi alterado por uma versão antiga do mod. Use o ORIGINAL "
                         "(o da pasta amostras3 / extraído da ISO original)")
    p, _, _, fim = achar_funcao(funcs, H_UPD)
    corpo = d[p + 16:fim]
    for h in (ARG_DESTRANSF, FUNC_DESTRANSF, ORIG_DPAD, ORIG_RODA):
        if struct.pack("<I", h) not in corpo:
            raise ValueError("switch_form_update não é a original. Use o globals.ds ORIGINAL")
    hashes = {f[1] for f in funcs}
    for o in ops:
        if o[1] in (0x05, 0x07, 0x08) and o[3]:
            hashes.add(o[3][0])
    choque = hashes & (set(FUNCOES_MOD) | set(VARIAVEIS_MOD))
    if choque:
        raise ValueError("nome do mod já existe no jogo: %s" % ", ".join("%08x" % h for h in choque))


def corpo_de(d, funcs, h):
    p, _, npar, fim = achar_funcao(funcs, h)
    return bytearray(d[p + 16:fim]), npar


def ops_de(corpo):
    ops = []
    _corpo(bytes(corpo), 0, len(corpo), ops, None)
    return ops


def ajustar_switch_form_update(d, funcs):
    """Cópia de switch_form_update com 4 ajustes (o resto fica igual ao jogo):
    a) SELECT (Ben ou alien) chama F_SELECT;  b) sem a checagem isabletotransform
    (ela só é verdadeira como Ben; F_SELECT confere para o Ben);  c) a roda do canto
    passa por F_RODA (que sempre repassa);  d) quando o jogo ignora os botões
    (travas), F_QUADRO confere se a trava ficou presa. O direcional fica original."""
    corpo, npar = corpo_de(d, funcs, H_UPD)
    ops = ops_de(corpo)
    pos = lambda o: o[0]

    # a) SELECT
    feito = False
    for i in range(len(ops) - 2):
        a, b, c = ops[i], ops[i + 1], ops[i + 2]
        if (a[1] == 0x07 and a[3] == (ARG_DESTRANSF,) and b[1] == 0x07 and b[3] == (FUNC_DESTRANSF,)
                and c[1] == 0x20 and c[2][0] == b[2][0] and c[2][1] == a[2][0] and c[2][2] == 1):
            r_arg, r_fn, r_dst = a[2][0], b[2][0], c[3][0]
            novo = instr(0x01, r_arg) + instr(0x07, r_fn, 0, 0, F_SELECT) + \
                instr(0x20, r_fn, r_arg, 1, r_dst) + NOP
            ini, fim = pos(a), pos(c) + 8
            if len(novo) != fim - ini or ops[i - 1][1] != 0x1F:
                raise ValueError("trecho do SELECT inesperado")
            corpo[ini:fim] = novo
            ant = ops[i - 1]           # separava Ben (tela de troca) de alien
            corpo[pos(ant):pos(ant) + 4] = NOP
            feito = True
            break
    if not feito:
        raise ValueError("não achei o trecho do botão SELECT")

    # b) isabletotransform
    feito = False
    h_iat = crc("isabletotransform")
    for i in range(len(ops) - 2):
        if ops[i][1] == 0x17 and ops[i][3] == (h_iat,):
            ch, nx = ops[i + 1], ops[i + 2]
            if ch[1] == 0x20 and ch[2][0] == ops[i][2][1] and nx[1] == 0x14 and nx[2][1] == ch[3][0]:
                corpo[pos(nx):pos(nx) + 4] = instr(0x06, nx[2][0], nx[2][2], 0)  # rc = ra
                feito = True
            break
    if not feito:
        raise ValueError("não achei a checagem isabletotransform")

    # (o caminho da forma Ultimate fica original: a roda mostra os golpes no HUD)
    if not any(o[1] == 0x17 and o[3] == (ULTIMO_NORMAL,) for o in ops):
        raise ValueError("não achei a checagem de alien normal")

    # c) roda do canto -> F_RODA (as 2 chamadas)
    n_roda = 0
    for o in ops:
        if o[1] == 0x07 and o[3] == (ORIG_RODA,):
            corpo[pos(o) + 4:pos(o) + 8] = struct.pack("<I", F_RODA)
            n_roda += 1
    if n_roda != 2:
        raise ValueError("esperava 2 chamadas da roda, achei %d" % n_roda)

    # d) a saída antecipada (travas, cena, morto...) passa por F_QUADRO.
    #    No ponto da saída: r5 = cena rodando, r7 = (0x2b2a4faf == nil),
    #    r10 = morto, r12 = câmera fixa (calculados nas palavras 0-31).
    esperado = [(0x07, TRANSF_EM_CURSO), (0x07, TRAVA_INPUT), (0x15,), (0x07, crc("cutscene")),
                (0x07, crc("cutscene")), (0x17, crc("isplaying")), (0x20,), (0x15,),
                (0x07, 0x2B2A4FAF), (0x01,), (0x10,), (0x15,), (0x07, OUTRA_TRAVA), (0x15,),
                (0x07, MORTO), (0x02,), (0x10,), (0x15,), (0x07, ZONA_ATIVA), (0x02,), (0x10,),
                (0x15,), (0x1F,), (0x21,)]
    for o, e in zip(ops, esperado):
        if o[1] != e[0] or (len(e) > 1 and o[3] != (e[1],)):
            raise ValueError("começo de switch_form_update diferente do esperado")
    regs = (ops[6][3][0], ops[10][2][2], ops[16][2][2], ops[20][2][2])
    if regs != (5, 7, 10, 12) or ops[22][2][1] != pos(ops[23]) // 4 + 1:
        raise ValueError("registradores da saída antecipada inesperados")
    saida = ops[23]
    fim_original = len(corpo) // 4          # aqui ficava o "retorna" final do jogo
    cauda = fim_original + 1
    corpo[pos(saida):pos(saida) + 4] = instr(0x1D, cauda & 0xFF, cauda >> 8, 0)
    corpo += RETORNA                         # o final original continua retornando
    corpo += b"".join([
        instr(0x15, 5, 7, 14),               # r14 = cena ou 0x2b2a4faf vazio
        instr(0x07, 15, 0, 0, OUTRA_TRAVA), instr(0x15, 14, 15, 14),
        instr(0x15, 14, 10, 14), instr(0x15, 14, 12, 14),   # ou morto ou câmera fixa
        instr(0x07, 16, 0, 0, F_QUADRO), instr(0x20, 16, 14, 1, 17),
        RETORNA,
    ])
    return bytes(corpo), npar


def ajustar_guardar_direcional(d, funcs):
    """Cópia da função que guarda o direcional. Se uma FASE começa um Ultimate Event
    enquanto o mod segura a cópia do direcional (pendente), entrega para a fase a
    cópia verdadeira (assim, no fim do evento, a fase devolve os aliens certos) e o
    mod sai de cena. Fora isso, é a função original."""
    corpo, npar = corpo_de(d, funcs, GUARDAR_DIRECIONAL)
    h_gform, h_gcur = crc("gformdata"), crc("gcurrentcharacter")
    prefixo = b"".join(montar([
        instr(0x07, 1, 0, 0, PENDENTE), ("se_nao", 1, "original"),
        instr(0x07, 2, 0, 0, COPIA_DIRECIONAL), ("se_nao", 2, "original"),
        instr(0x08, 2, 0, 0, BACKUP_JOGO),
        # tira a Ultimate do mod da memória (a fase vai carregar a dela)
        instr(0x07, 8, 0, 0, ALIEN_MOD), ("se_nao", 8, "limpa"),
        instr(0x07, 3, 0, 0, h_gform), instr(0x18, 3, 8, 4), instr(0x17, 4, 5, 0, CAMPO_ULT),
        ("se_nao", 5, "limpa"),
        instr(0x07, 6, 0, 0, h_gcur), instr(0x10, 6, 5, 7), ("se_nao", 7, "remove"),
        ("vai", "limpa"),
        ("rotulo", "remove"),
        instr(0x18, 3, 5, 4), instr(0x17, 4, 11, 0, crc("character")),
        instr(0x07, 10, 0, 0, CHARMGR), instr(0x07, 7, 0, 0, CHARMGR),
        instr(0x17, 7, 3, 0, crc("removecharacter")), instr(0x20, 3, 10, 2, 4),
        ("rotulo", "limpa"),
        instr(0x01, 6),
        *[instr(0x08, 6, 0, 0, v) for v in (PENDENTE, COPIA_DIRECIONAL, ATIVA, SAINDO,
                                            RESTAURANDO, ALIEN_MOD, FORMA_MOD)],
        instr(0x07, 1, 0, 0, TRAVA_MOD), ("se_nao", 1, "fim"),
        instr(0x08, 6, 0, 0, TRAVA_INPUT), instr(0x08, 6, 0, 0, TRAVA_MOD),
        ("rotulo", "fim"),
        RETORNA,
        ("rotulo", "original"),
    ]))
    return prefixo + realocar(bytes(corpo), len(prefixo) // 4), npar


def ajustar_zona(d, funcs, hz):
    """Áreas de câmera fixa: o jogo desliga o controle de troca (setinputcb(1, nil)).
    Na Ultimate do mod você ficava preso nela. Agora o controle vira F_ZONA, que só
    aceita SELECT para sair da Ultimate do mod."""
    corpo, npar = corpo_de(d, funcs, hz)
    h_im, h_sic = crc("inputmgr"), crc("setinputcb")
    antes = instr(0x01, 7) + instr(0x07, 2, 0, 0, h_im) + instr(0x17, 2, 0, 0, h_sic)
    depois = instr(0x07, 7, 0, 0, F_ZONA) + instr(0x17, 5, 0, 0, h_sic) + NOP
    i = bytes(corpo).find(antes)
    if i < 0 or i % 4 or instr(0x07, 5, 0, 0, h_im) not in bytes(corpo[:i]):
        raise ValueError("não achei o desligamento de controle em %08x" % hz)
    corpo[i:i + len(antes)] = depois
    return bytes(corpo), npar


def ajustar_habilidades(d, funcs, fh, mask_ult, mask_base):
    """Cópia da transformação na Ultimate usando as habilidades do alien normal
    (todas as das Ultimates já estão incluídas nas dele): assim a Ultimate empurra
    caixas, escala etc. como o alien normal. Vale também nos eventos das fases."""
    corpo, npar = corpo_de(d, funcs, fh)
    ops = ops_de(corpo)
    n = 0
    for a, b in zip(ops, ops[1:]):
        if (a[1] == 0x07 and a[3] == (mask_ult,) and b[1] == 0x07 and b[3] == (APLICA_HABILIDADES,)):
            corpo[a[0] + 4:a[0] + 8] = struct.pack("<I", mask_base)
            n += 1
    if n != 1:
        raise ValueError("habilidades da Ultimate %08x: trecho não encontrado" % fh)
    return bytes(corpo), npar


def texto(r, t):
    """r = string (instrução 0x04, texto em linha com zero no fim)"""
    b = t.encode("latin-1") + b"\0"
    return bytes((0x04, r, 0, 0)) + b + b"\0" * ((-len(b)) % 4)


def funcoes_do_mod(rede=True, gigante=True, hud_ben=False, intro=True):
    """Código das funções novas: {hash: lista de instruções}."""
    h_gform, h_gcur = crc("gformdata"), crc("gcurrentcharacter")
    h_player, h_person = crc("player"), crc("person")

    def g(r, h): return instr(0x07, r, 0, 0, h)
    def s(r, h): return instr(0x08, r, 0, 0, h)
    def nil(r): return instr(0x01, r)
    def sim(r): return instr(0x02, r, 1, 0)

    def tabela(dst):                           # rdst = tabela de ids dos aliens
        return [g(30, TABELA_ALIENS), instr(0x20, 30, 31, 0, dst)]

    def carrega_so_ultimate():
        # r9 = forma Ultimate. Carrega só os dados dela (como o jogo faz para cada forma
        # do direcional), sem descarregar nada; cada Ultimate é carregada uma vez por fase.
        return [
            g(13, crc("missionmgr")), g(14, crc("missionmgr")),
            instr(0x17, 14, 15, 0, crc("getcurrentmission")), instr(0x20, 15, 13, 1, 16),
            # a lista vale só para a fase atual (a troca de fase descarrega tudo)
            g(5, CARREGADAS_MISSAO), instr(0x10, 5, 16, 6), ("se_nao", 6, "ct"),
            g(5, CARREGADAS), ("se_nao", 5, "ct"), ("vai", "tem"),
            ("rotulo", "ct"), instr(0x16, 5, 0, 0), s(5, CARREGADAS), s(16, CARREGADAS_MISSAO),
            ("rotulo", "tem"),
            instr(0x18, 5, 9, 6), ("se_nao", 6, "ld"),
            *chamar0(F_PRONTO), RETORNA,                # já carregada: segue
            ("rotulo", "ld"),
            sim(6), instr(0x1A, 5, 9, 6),
            instr(0x18, 2, 9, 4),                       # r4 = gformdata[Ultimate]
            num(5, 2), s(5, CARGAS),
            instr(0x06, 16, 20, 0), g(21, PASTA_DADOS), instr(0x17, 4, 22, 0, crc("characterfile")),
            g(23, F_UM), instr(0x17, 16, 17, 0, crc("loaddata")), instr(0x20, 17, 20, 4, 18),
            instr(0x06, 16, 20, 0), g(21, PASTA_DESC), instr(0x17, 4, 22, 0, 0x7FB535F8),
            g(23, F_UM), instr(0x17, 16, 17, 0, crc("loaddesc")), instr(0x20, 17, 20, 4, 18),
        ]

    def repassa_baixo():
        # Xbox 360: repassa para a roda original com os argumentos em r3..r5, para a
        # pilha de registradores da máquina dos scripts crescer o mínimo (em r20 a roda
        # original rodava 20 registradores mais fundo a cada quadro).
        return [instr(0x07, 6, 0, 0, ORIG_RODA),
                instr(0x06, 0, 3, 0), instr(0x06, 1, 4, 0), instr(0x06, 2, 5, 0),
                instr(0x20, 6, 3, 3, 7)]

    def timer(func, segundos):                 # createtimer(func, segundos, 1)
        return [g(8, func), num(9, segundos), num(10, 1), g(6, crc("createtimer")),
                instr(0x20, 6, 8, 3, 7)]

    def eh_ben(dst):                           # rdst = é o Ben? (usa r11, r12, r17)
        return [*tabela(11), g(12, h_gcur), instr(0x17, 11, 17, 0, crc("ben")),
                instr(0x10, 12, 17, dst)]

    def e_especial(dst, tmp):                  # forma Ultimate (ou Gigante)? usa r11..r14
        itens = [*tabela(11), g(12, h_gcur), instr(0x02, dst, 0, 0)]
        for u in IDS_ULTIMATE + (crc("waybig"),):
            itens += [instr(0x17, 11, 13, 0, u), instr(0x10, 12, 13, tmp),
                      instr(0x15, dst, tmp, dst)]
        return itens

    def cena(dst):                             # rdst = cena do jogo rodando?
        return [g(28, crc("cutscene")), g(25, crc("cutscene")),
                instr(0x17, 25, 3, 0, crc("isplaying")), instr(0x20, 3, 28, 1, dst)]

    def fase(dst, t1, t2):
        """rdst = uma fase está num Ultimate Event (FORMA_ULT preenchida e não pelo mod)"""
        return [g(dst, FORMA_ULT), nil(t1), instr(0x11, dst, t1, t2),
                g(t1, FORMA_MOD), instr(0x11, dst, t1, t1), instr(0x14, t2, t1, dst)]

    def conta(var, reg, tmp, pfx):             # var = (var ou 0) + 1; reg = var
        return [g(reg, var), ("se_nao", reg, pfx + "0"), ("vai", pfx + "1"),
                ("rotulo", pfx + "0"), num(reg, 0), ("rotulo", pfx + "1"),
                num(tmp, 1), instr(0x0A, reg, tmp, reg), s(reg, var)]

    def maior(reg, limite, dst, tmp):          # rdst = reg > limite
        return [num(tmp, limite), instr(0x13, reg, tmp, dst)]

    def solta_trava_mod(pfx):                  # solta a trava dos botões, se for do mod
        return [g(1, TRAVA_MOD), ("se_nao", 1, pfx), nil(6), s(6, TRAVA_INPUT),
                s(6, TRAVA_MOD), ("rotulo", pfx)]

    def trava_movimento():
        return [g(28, crc("playermgr")), g(25, crc("playermgr")), instr(0x17, 25, 3, 0, crc("lockmovement")),
                instr(0x20, 3, 28, 1, 20), sim(6), s(6, POSE_TRAVADA)]

    def solta_movimento(pfx):
        return [g(1, POSE_TRAVADA), ("se_nao", 1, pfx), nil(6), s(6, POSE_TRAVADA),
                g(28, crc("playermgr")), g(25, crc("playermgr")), instr(0x17, 25, 3, 0, crc("unlockmovement")),
                instr(0x20, 3, 28, 1, 20), ("rotulo", pfx)]

    def intro_inicio():
        """1ª vez deste alien nesta fase: toca a animação de transformação e termina em F_INTRO."""
        itens = []
        for nome_, (pn, pu, var) in INTRO.items():
            itens += [
                *tabela(11), instr(0x17, 11, 17, 0, crc(nome_)), instr(0x10, 8, 17, 18),
                ("se_nao", 18, "x_" + nome_),
                # fase atual (o objeto da missão) já viu esta animação?
                g(28, crc("missionmgr")), g(25, crc("missionmgr")),
                instr(0x17, 25, 3, 0, crc("getcurrentmission")), instr(0x20, 3, 28, 1, 21),
                g(22, var), instr(0x10, 21, 22, 18), ("se_nao", 18, "n_" + nome_), ("vai", "sem_intro"),
                ("rotulo", "n_" + nome_),
                s(21, var), sim(18), s(18, INTRO_EM_CURSO),
                *trava_mod(), *trava_movimento(),
                g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, h_person), instr(0x20, 3, 28, 1, 20),
                instr(0x06, 20, 28, 0), instr(0x17, 20, 3, 0, crc("playanim")),
                instr(0x05, 29, 0, 0, crc(pn + "_ult_formchange_in_01")), num(30, 1), num(31, 0),
                g(32, F_INTRO), instr(0x20, 3, 28, 5, 24),
                *timer(F_INTRO_T, 2.5),                  # segurança: segue mesmo sem o aviso
                RETORNA,
                ("rotulo", "x_" + nome_),
            ]
        return itens + [("rotulo", "sem_intro")]

    def trava_mod():
        return [sim(6), s(6, TRAVA_INPUT), s(6, TRAVA_MOD)]

    def fim_mod(pfx):
        """Encerra o estado do mod (o que loadpreultimateform faz, sem chamar a fase:
        em Roma de dia ela dispara a continuação da fase)."""
        return [
            nil(6), s(6, SAINDO), s(6, RESTAURANDO), s(6, ALIEN_MOD),
            g(1, FORMA_ULT), g(2, FORMA_MOD), instr(0x10, 1, 2, 3), ("se_nao", 3, pfx + "f"),
            nil(6), s(6, FORMA_ULT),               # só se fui eu que preenchi
            ("rotulo", pfx + "f"),
            nil(6), s(6, FORMA_MOD),
            *solta_trava_mod(pfx + "t"),
            g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, h_person),
            instr(0x20, 3, 28, 1, 20),                                  # r20 = person
            instr(0x17, 20, 22, 0, crc("dontrender")), instr(0x06, 20, 26, 0),
            instr(0x02, 27, 0, 0), instr(0x20, 22, 26, 2, 23),          # dontrender(falso)
        ]

    seguro = []   # só transforma se não estiver atacando/interagindo/agarrado/sem movimento
    for k, metodo in enumerate(("isattacking", "isinteracting", "isstruggling")):
        seguro += [
            g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, h_person),
            instr(0x20, 3, 28, 1, 20),                                  # r20 = person
            instr(0x17, 20, 21, 0, crc(metodo)), instr(0x06, 20, 22, 0),
            instr(0x20, 21, 22, 1, 23),                                 # r23 = person.metodo()
            ("se_nao", 23, "ok%d" % k), RETORNA, ("rotulo", "ok%d" % k),
        ]
    seguro += [
        g(28, h_player), g(25, h_player), instr(0x17, 25, 21, 0, crc("isplayermovementdisabled")),
        instr(0x20, 21, 28, 1, 23), ("se_nao", 23, "ok_mov"), RETORNA, ("rotulo", "ok_mov"),
    ]

    def seguro_ou(falha):                      # mesmas checagens, mas pula para "falha"
        return [("vai", falha) if (isinstance(x, bytes) and x == RETORNA) else x for x in seguro]

    def inicia_rede():
        if not rede:
            return []
        return [
            nil(16), s(16, REDE_Y), s(16, REDE_POS), s(16, REDE_QUEDA), s(16, REDE_FIRME),
            g(16, REDE_VIVA), ("se_nao", 16, "rede_liga"),
            nil(16), s(16, REDE_VIVA),             # a rede que já roda confirma em 1 s
            ("vai", "rede_fim"),
            ("rotulo", "rede_liga"),
            sim(16), s(16, REDE_VIVA), *timer(F_REDE, 1),
            ("rotulo", "rede_fim"),
        ]

    def sair_pelo_alien():                     # volta a ser Ben (efeito do jogo) e sai
        return [sim(6), s(6, SAINDO), nil(6), s(6, ATIVA),
                g(8, F_SAIR), g(6, FUNC_DESTRANSF), instr(0x20, 6, 8, 1, 7)]

    def remove_ultimate(pfx):                  # tira a Ultimate do mod da memória
        if MANTER_ULTIMATE:
            return []
        return [
            g(8, ALIEN_MOD), ("se_nao", 8, pfx),
            g(2, h_gform), instr(0x18, 2, 8, 4), instr(0x17, 4, 5, 0, CAMPO_ULT),
            ("se_nao", 5, pfx),
            g(3, h_gcur), instr(0x10, 3, 5, 6), ("se_nao", 6, pfx + "r"), ("vai", pfx),
            ("rotulo", pfx + "r"),
            instr(0x18, 2, 5, 4), instr(0x17, 4, 11, 0, crc("character")),
            g(10, CHARMGR), g(7, CHARMGR), instr(0x17, 7, 3, 0, crc("removecharacter")),
            instr(0x20, 3, 10, 2, 4),
            ("rotulo", pfx),
        ]

    def missao(metodo, arquivo, cb=None):
        """missionmgr.getcurrentmission():metodo("l_tokd", arquivo[, cb])"""
        itens = [g(13, crc("missionmgr")), g(14, crc("missionmgr")),
                 instr(0x17, 14, 15, 0, crc("getcurrentmission")), instr(0x20, 15, 13, 1, 9),
                 texto(10, GIG_PASTA), texto(11, arquivo)]
        if cb is not None:
            itens += [g(12, cb)]
        itens += [instr(0x17, 9, 4, 0, crc(metodo)), instr(0x20, 4, 9, 4 if cb is not None else 3, 5)]
        return itens

    def descarrega_modelo(pfx):                 # só se o mod carregou
        return [g(16, GIG_CARREGADO), ("se_nao", 16, pfx), nil(16), s(16, GIG_CARREGADO),
                *missao("unloaddata", GIG_MODELO), ("rotulo", pfx)]

    def escala(valor):                          # player.person:setscale(valor)
        return [g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, h_person),
                instr(0x20, 3, 28, 1, 20), num(21, valor), instr(0x17, 20, 22, 0, crc("setscale")),
                instr(0x06, 20, 26, 0), instr(0x06, 21, 27, 0), instr(0x20, 22, 26, 2, 23)]

    f = {}
    if gigante:
        def remove_gigante(pfx):                # tira o Gigante da memória (fora dele)
            return [*tabela(11), instr(0x17, 11, 5, 0, crc("waybig")),
                    g(3, h_gcur), instr(0x10, 3, 5, 6), ("se_nao", 6, pfx + "r"), ("vai", pfx),
                    ("rotulo", pfx + "r"),
                    g(2, h_gform), instr(0x18, 2, 5, 4), instr(0x17, 4, 11, 0, crc("character")),
                    g(10, CHARMGR), g(7, CHARMGR), instr(0x17, 7, 3, 0, crc("removecharacter")),
                    instr(0x20, 3, 10, 2, 4),
                    ("rotulo", pfx)]
        f[F_GIG_ENTRAR] = [                     # Tartagira + SELECT
            g(6, FORMA_ULT), ("se_nao", 6, "e1"), RETORNA,      # evento de fase: a fase manda
            ("rotulo", "e1"),
            g(6, PENDENTE), ("se_nao", 6, "e2"), RETORNA,
            ("rotulo", "e2"),
            *seguro,
            g(6, LIMPA_TARTAGIRA), instr(0x20, 6, 8, 0, 7),    # desliga o redemoinho antes
            g(3, h_gcur), s(3, ALIEN_MOD), sim(6), s(6, GIGANTE),
            *trava_mod(),
            *conta(VIGIAS, 4, 5, "vg"), *timer(F_VIGIA, 15),
            g(8, F_GIG_CARREGAR), g(6, VOLTAR_BEN), instr(0x20, 6, 8, 1, 7),
            RETORNA,
        ]
        f[F_GIG_CARREGAR] = [                   # já como Ben: carrega o Gigante como alien do
            nil(6), s(6, TRANSF_EM_CURSO),
            g(8, ALIEN_MOD), ("se_nao", 8, "cancela"),          # direcional (pacote
            g(6, FORMA_ULT), ("se_nao", 6, "segue"), ("vai", "cancela"),   # global/g_wayb.psp
            ("rotulo", "segue"),                                # e golpes atk_wb.ddf)
            g(16, PENDENTE), ("se_nao", 16, "guarda"), ("vai", "carrega"),
            ("rotulo", "guarda"),
            *chamar0(GUARDAR_DIRECIONAL),
            g(16, BACKUP_JOGO), s(16, COPIA_DIRECIONAL),
            nil(16), s(16, BACKUP_JOGO), sim(16), s(16, PENDENTE),
            ("rotulo", "carrega"),
            *tabela(11), instr(0x17, 11, 9, 0, crc("waybig")),
            g(8, ALIEN_MOD), nil(10), nil(11), g(12, F_GIG_MODELO),
            g(6, PRECARREGAR), instr(0x20, 6, 8, 5, 7),
            RETORNA,
            ("rotulo", "cancela"),
            nil(6), s(6, ALIEN_MOD), s(6, GIGANTE),
            *solta_trava_mod("c1"),
            RETORNA,
        ]
        f[F_GIG_MODELO] = [                     # animações carregadas: agora o modelo
            g(8, ALIEN_MOD), ("se_nao", 8, "cancela"),
            g(6, FORMA_ULT), ("se_nao", 6, "carrega"),
            ("rotulo", "cancela"),
            nil(6), s(6, GIGANTE),
            *solta_trava_mod("c1"),
            RETORNA,
            ("rotulo", "carrega"),
            # O global/g_wayb.psp montado pelo cd_anims.py (--gigante) já tem modelo,
            # esqueleto e animações: vira direto, sem depender do pacote da fase final.
            g(8, ALIEN_MOD), g(6, F_GIG_PRONTO), instr(0x20, 6, 8, 1, 7),
            RETORNA,
        ]
        f[F_GIG_PRONTO] = [                     # (r0) modelo carregado
            g(8, ALIEN_MOD), ("se_nao", 8, "cancela"),
            g(6, GIGANTE), ("se_nao", 6, "cancela"),
            g(6, FORMA_ULT), ("se_nao", 6, "vira"),
            ("rotulo", "cancela"),
            nil(6), s(6, GIGANTE),                  # o direcional pendente é devolvido depois
            *descarrega_modelo("dm"),
            *solta_trava_mod("c1"),
            RETORNA,
            ("rotulo", "vira"),
            sim(19), s(19, ATIVA), num(19, 0), s(19, ESPERA), s(19, PARADO), nil(19), s(19, BATIDA),
            *timer(F_MONITOR, 1.5),
            *inicia_rede(),
            g(8, F_GIG_CB), g(6, TRANSF_GIGANTE), instr(0x20, 6, 8, 1, 7),
            *escala(ESCALA_GIGANTE),
            RETORNA,
        ]
        f[F_GIG_CB] = [                         # fim da animação de virar o Gigante
            nil(6), s(6, TRANSF_EM_CURSO),
            *solta_trava_mod("s1"),
            RETORNA,
        ]
    f[F_SELECT] = [                             # SELECT como Ben ou alien normal
        # direcional ainda não devolvido? devolve antes de tudo
        g(16, PENDENTE), ("se_nao", 16, "ben"),
        g(19, SAINDO), g(18, RESTAURANDO), instr(0x15, 19, 18, 19),
        ("se_nao", 19, "d1"), RETORNA,                      # já está devolvendo
        ("rotulo", "d1"),
        *fase(19, 17, 18), ("se_nao", 19, "d2"), RETORNA,   # a fase está no comando
        ("rotulo", "d2"),
        nil(18), s(18, ATIVA),                              # (monitor perdido: desliga)
        *eh_ben(18), ("se_nao", 18, "d_alien"),
        *chamar0(F_SAIR), RETORNA,
        ("rotulo", "d_alien"),
        *chamar0(F_SAIR_SEGURO), RETORNA,
        # Ben: tela de troca de aliens, como no jogo original (se puder transformar)
        ("rotulo", "ben"),
        *eh_ben(18), ("se_nao", 18, "alien"),
        *([
            # R + SELECT: Ben gigante (liga/desliga). O R vem do quadro anterior (a roda
            # guarda), porque esta função não recebe o controle.
            g(18, R_SEGURO), ("se_nao", 18, "tela"),
            g(18, BEN_GRANDE), ("se_nao", 18, "cresce"),
            nil(18), s(18, BEN_GRANDE), *escala(1), RETORNA,
            ("rotulo", "cresce"),
            sim(18), s(18, BEN_GRANDE), *escala(ESCALA_BEN), RETORNA,
            ("rotulo", "tela"),
        ] if hud_ben else []),
        g(28, h_player), g(25, h_player), instr(0x17, 25, 21, 0, crc("isabletotransform")),
        instr(0x20, 21, 28, 1, 23), ("se_nao", 23, "fim"),
        g(28, crc("overlay")), g(29, crc("characterpresetscreen_enter")), g(25, crc("overlay")),
        instr(0x17, 25, 3, 0, crc("runuser")), instr(0x20, 3, 28, 2, 4),
        g(28, 0x23F332A3), g(25, 0x801B4AF7), instr(0x20, 25, 28, 1, 3),
        RETORNA,
        ("rotulo", "alien"),                                # alien: entra na Ultimate
        *chamar0(F_ENTRAR),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_ENTRAR] = [
        g(2, h_gform), g(3, h_gcur), instr(0x18, 2, 3, 4), instr(0x17, 4, 5, 0, CAMPO_ULT),
        ("se_nao", 5, "sem_ult"),         # sem Ultimate: só a Tartagira vira o Gigante
        g(6, FORMA_ULT), ("se_nao", 6, "e1"), ("vai", "fim"),   # evento de fase: a fase manda
        ("rotulo", "e1"),
        g(6, PENDENTE), ("se_nao", 6, "e2"), ("vai", "fim"),
        ("rotulo", "e2"),
        *seguro,
        g(3, h_gcur), s(3, ALIEN_MOD),
        *trava_mod(),                     # botões travados durante o carregamento
        *conta(VIGIAS, 4, 5, "vg"),
        *timer(F_VIGIA, 15),
        g(8, F_CARREGAR), g(6, VOLTAR_BEN), instr(0x20, 6, 8, 1, 7),   # Ben, depois carregar
        RETORNA,
        ("rotulo", "sem_ult"),
        *([*tabela(11), g(12, h_gcur), instr(0x17, 11, 17, 0, crc("terraspin")),
           instr(0x10, 12, 17, 18), ("se_nao", 18, "fim"), *chamar0(F_GIG_ENTRAR)] if gigante else []),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_CARREGAR] = [                           # já como Ben
        nil(6), s(6, TRANSF_EM_CURSO),          # (a volta para o Ben com callback do mod não
        g(8, ALIEN_MOD), ("se_nao", 8, "cancela"),   #  desliga essa trava)
        g(6, FORMA_ULT), ("se_nao", 6, "segue"), ("vai", "cancela"),   # uma fase começou
        ("rotulo", "segue"),
        g(16, PENDENTE), ("se_nao", 16, "guarda"), ("vai", "carrega"),
        ("rotulo", "guarda"),                   # guarda o direcional só uma vez
        *([nil(16), s(16, COPIA_DIRECIONAL), sim(16), s(16, PENDENTE)] if SEM_TROCA else [
            *chamar0(GUARDAR_DIRECIONAL),
            g(16, BACKUP_JOGO), s(16, COPIA_DIRECIONAL),    # a cópia fica só com o mod
            nil(16), s(16, BACKUP_JOGO), sim(16), s(16, PENDENTE)]),
        ("rotulo", "carrega"),
        g(8, ALIEN_MOD), g(2, h_gform), instr(0x18, 2, 8, 4), instr(0x17, 4, 9, 0, CAMPO_ULT),
        *(carrega_so_ultimate() if SEM_TROCA else [
            nil(10), nil(11), g(12, F_PRONTO),
            g(6, PRECARREGAR), instr(0x20, 6, 8, 5, 7)]),     # carrega alien + Ultimate
        RETORNA,
        ("rotulo", "cancela"),
        *solta_trava_mod("c1"), nil(6), s(6, ALIEN_MOD),
        RETORNA,
    ]
    f[F_PRONTO] = [                             # carregou
        g(8, ALIEN_MOD), ("se_nao", 8, "cancela"),
        g(6, FORMA_ULT), ("se_nao", 6, "segue"), ("vai", "cancela"),
        ("rotulo", "segue"),
        g(6, VIRAR_ALIEN), instr(0x20, 6, 8, 1, 7),     # vira o alien
        *timer(F_ATIVAR, 1),
        RETORNA,
        ("rotulo", "cancela"),
        *solta_trava_mod("c1"),
        RETORNA,
    ]
    f[F_UM] = [                                 # (sem trocar o direcional) 1 parte pronta
        g(1, CARGAS), ("se_nao", 1, "fim"),
        num(2, 1), instr(0x0B, 1, 2, 1), s(1, CARGAS),
        num(2, 0), instr(0x10, 1, 2, 3), ("se_nao", 3, "fim"),
        nil(1), s(1, CARGAS),
        *chamar0(F_PRONTO),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_ATIVAR] = [                             # 1 s depois de virar o alien
        g(8, ALIEN_MOD), ("se_nao", 8, "fim"),          # entrada cancelada: nada
        sim(19), s(19, ATIVA), num(19, 0), s(19, ESPERA), s(19, PARADO), nil(19), s(19, BATIDA),
        *timer(F_MONITOR, 1.5),                         # o monitor devolve se algo falhar
        *inicia_rede(),
        g(6, FORMA_ULT), ("se_nao", 6, "a1"), ("vai", "aborta"),
        ("rotulo", "a1"),
        g(8, ALIEN_MOD), g(3, h_gcur), instr(0x10, 3, 8, 4), ("se_nao", 4, "aborta"),
        g(2, h_gform), instr(0x18, 2, 8, 5), instr(0x17, 5, 6, 0, CAMPO_ULT),
        ("se_nao", 6, "aborta"),
        *(intro_inicio() if intro else []),
        # o mesmo que a função da Ultimate do jogo faz no evento (sem mexer nela)
        s(8, FORMA_ULT), s(8, FORMA_MOD),
        *trava_mod(),
        *chamar0(crc("switch_to_ultimate")),
        *timer(F_GRITO, 0.5),
        RETORNA,
        ("rotulo", "aborta"),
        *solta_trava_mod("ab"),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_INTRO_T] = [g(6, F_INTRO), nil(7), instr(0x20, 6, 7, 1, 8), RETORNA]
    f[F_INTRO] = [                              # fim da animação (ou o timer de segurança)
        g(1, INTRO_EM_CURSO), ("se_nao", 1, "fim"),     # já tratada
        nil(1), s(1, INTRO_EM_CURSO),
        g(8, ALIEN_MOD), ("se_nao", 8, "aborta"),
        g(6, FORMA_ULT), ("se_nao", 6, "i1"), ("vai", "aborta"),   # a fase começou um evento
        ("rotulo", "i1"),
        g(3, h_gcur), instr(0x10, 3, 8, 4), ("se_nao", 4, "aborta"),
        # brilho na tela, como nos eventos das fases
        g(28, crc("overlay")), g(25, crc("overlay")), instr(0x17, 25, 3, 0, crc("setgloweffect")),
        num(29, 3), num(30, 1), num(31, 0), instr(0x20, 3, 28, 4, 20),
        s(8, FORMA_ULT), s(8, FORMA_MOD),
        *chamar0(crc("switch_to_ultimate")),
        *timer(F_GRITO, 0.5),
        # a pose de chegada sai um instante depois, com o corpo da Ultimate já trocado
        *timer(F_POSE, 0.4),
        ("vai", "fim"),
        ("rotulo", "aborta"),
        *solta_trava_mod("ia"),
        *solta_movimento("im"),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_POSE] = [
        g(8, ALIEN_MOD), ("se_nao", 8, "solta"),
        g(1, ATIVA), ("se_nao", 1, "solta"),
        *[x for nome_, (pn, pu, var) in INTRO.items() for x in (
            *tabela(11), instr(0x17, 11, 17, 0, crc(nome_)), instr(0x10, 8, 17, 18),
            ("se_nao", 18, "p_" + nome_),
            g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, h_person), instr(0x20, 3, 28, 1, 20),
            instr(0x06, 20, 28, 0), instr(0x17, 20, 3, 0, crc("playanim")),
            instr(0x05, 29, 0, 0, crc(pu + "_transform_01")), instr(0x20, 3, 28, 2, 24),
            ("vai", "espera"),
            ("rotulo", "p_" + nome_))],
        ("rotulo", "solta"),
        *solta_movimento("ps"),
        RETORNA,
        ("rotulo", "espera"),
        *timer(F_POSE_FIM, DURACAO_POSE),
        RETORNA,
    ]
    f[F_POSE_FIM] = [*solta_movimento("pf"), RETORNA]
    # player:playvo_ex(player, falante das Ultimates, "<alien>_name_callout", prioridade, 0)
    f[F_GRITO] = [
        g(8, ALIEN_MOD), ("se_nao", 8, "fim"),
        g(9, FALA_ULTIMATES), ("se_nao", 9, "fim"),      # fase sem script de vozes: nada
        *[x for campo, nome_ in GRITOS.items() for x in (
            *tabela(11), instr(0x17, 11, 17, 0, crc(campo)), instr(0x10, 8, 17, 18),
            ("se_nao", 18, "g_" + campo),
            g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, crc("playvo_ex")),
            instr(0x06, 9, 29, 0), instr(0x05, 30, 0, 0, crc(nome_ + "_name_callout")),
            g(31, PRIORIDADE_VO), num(32, 0), instr(0x20, 3, 28, 5, 20),
            ("vai", "fim"),
            ("rotulo", "g_" + campo))],
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_MONITOR] = [                            # a cada 1,5 s com a Ultimate do mod
        g(1, ATIVA), ("se_nao", 1, "fim"),
        g(1, INTRO_EM_CURSO), ("se_nao", 1, "m0"), ("vai", "rearma"),   # animação tocando
        ("rotulo", "m0"),
        *e_especial(15, 14), ("se_nao", 15, "acabou"),
        g(2, BATIDA), ("se_nao", 2, "parado"),          # a roda continua rodando?
        nil(2), s(2, BATIDA), num(2, 0), s(2, PARADO), ("vai", "rearma"),
        ("rotulo", "parado"),                           # ~4,5 s sem resposta: destrava
        *conta(PARADO, 4, 5, "p"), *maior(4, 3, 7, 6), ("se_nao", 7, "rearma"),
        num(2, 0), s(2, PARADO), *chamar0(F_DESTRAVA),
        ("rotulo", "rearma"),
        *timer(F_MONITOR, 1.5),
        RETORNA,
        ("rotulo", "acabou"),
        *chamar0(F_FIM),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_FIM] = [                                # a Ultimate acabou sem o SELECT
        g(1, PENDENTE), ("se_nao", 1, "nada"),          # nada a devolver
        g(1, SAINDO), g(2, RESTAURANDO), instr(0x15, 1, 2, 1),
        ("se_nao", 1, "f1"),
        ("rotulo", "nada"),
        nil(6), s(6, ATIVA), RETORNA,                   # (a saída já está em andamento)
        ("rotulo", "f1"),
        *fase(1, 2, 3), ("se_nao", 1, "f2"), ("vai", "espera"),   # evento da fase: espera
        ("rotulo", "f2"),
        *conta(ESPERA, 4, 5, "e"),
        # o jogo no meio de uma troca (trava que não é do mod): espera até ~9 s
        g(1, TRAVA_INPUT), g(2, TRAVA_MOD), instr(0x0F, 2, 2, 0), instr(0x14, 1, 2, 1),
        g(2, TRANSF_EM_CURSO), instr(0x15, 1, 2, 3),
        ("se_nao", 3, "sem_trava"),
        *maior(4, 6, 7, 6), ("se_nao", 7, "espera"), ("vai", "age"),
        ("rotulo", "sem_trava"),
        # FORMA_ULT ainda com o alien do mod: pode ser uma fase começando um evento com
        # o mesmo alien. Espera ~4,5 s (a fase entrega o direcional nesse tempo).
        g(1, FORMA_ULT), ("se_nao", 1, "age"),
        *maior(4, 2, 7, 6), ("se_nao", 7, "espera"), ("vai", "age"),
        ("rotulo", "espera"),
        *timer(F_MONITOR, 1.5),
        RETORNA,
        ("rotulo", "age"),
        nil(19), s(19, ATIVA),
        *eh_ben(18), ("se_nao", 18, "alien"),
        *chamar0(F_SAIR), RETORNA,
        ("rotulo", "alien"),
        *sair_pelo_alien(),
        *conta(VIGIAS_SAIDA, 4, 5, "vs"), *timer(F_VIGIA_SAIDA, 10),
        RETORNA,
    ]
    f[F_SAIR] = [                               # já como Ben: devolve o direcional
        g(1, RESTAURANDO), ("se_nao", 1, "segue"), RETORNA,
        ("rotulo", "segue"),
        *solta_movimento("sm"),                 # saiu no meio da pose
        sim(6), s(6, SAINDO), nil(6), s(6, ATIVA),
        nil(6), s(6, TRANSF_EM_CURSO),          # (a volta para o Ben com callback do mod
                                                #  não desliga essa trava)
        *remove_ultimate("rm"),
        *([g(16, GIGANTE), ("se_nao", 16, "nao_gig"),            # Gigante: tamanho normal e
           *escala(1), *remove_gigante("rg"), *descarrega_modelo("dm"),   # tira da memória; depois
           nil(6), s(6, GIGANTE),                                 # devolve o direcional
           ("rotulo", "nao_gig")] if gigante else []),
        g(16, PENDENTE), ("se_nao", 16, "nada"),
        sim(6), s(6, RESTAURANDO),
        *trava_mod(),                           # direcional parado durante o carregamento
        g(6, COPIA_DIRECIONAL), ("se_nao", 6, "sem_copia"), s(6, BACKUP_JOGO),
        ("rotulo", "sem_copia"),
        *(chamar0(F_DEVOLVIDO) if SEM_TROCA else [
            g(20, F_DEVOLVIDO), g(6, RESTAURAR_DIRECIONAL), instr(0x20, 6, 20, 1, 7)]),
        *conta(VIGIAS_SAIDA, 4, 5, "vs"), *timer(F_VIGIA_SAIDA, 10),
        RETORNA,
        ("rotulo", "nada"),                     # nada a devolver: só finaliza
        *fim_mod("n"),
        RETORNA,
    ]
    f[F_DEVOLVIDO] = [                          # direcional de volta
        nil(6), s(6, PENDENTE), s(6, COPIA_DIRECIONAL), num(6, 0), s(6, FALHAS),
        *fim_mod("d"),
        RETORNA,
    ]
    f[F_SAIR_SEGURO] = [                        # sai se for seguro; SELECT segurado
        g(1, SAINDO), g(2, RESTAURANDO), instr(0x15, 1, 2, 1),      # (~1,5 s) sai mesmo
        ("se_nao", 1, "checa"), RETORNA,                            # assim
        ("rotulo", "checa"),
        *seguro_ou("recusa"),
        ("rotulo", "forca"),
        num(4, 0), s(4, RECUSAS),
        *sair_pelo_alien(),
        *conta(VIGIAS_SAIDA, 4, 5, "vs"), *timer(F_VIGIA_SAIDA, 10),
        RETORNA,
        ("rotulo", "recusa"),                   # o jogo diz que está ocupado (ex.: depois
        *conta(RECUSAS, 4, 5, "r"),             # do ataque especial fica "atacando")
        *maior(4, 40, 7, 6), ("se_nao", 7, "espera"), ("vai", "forca"),
        ("rotulo", "espera"),
        RETORNA,
    ]
    f[F_VIGIA] = [                              # 15 s após entrar
        g(4, VIGIAS), ("se_nao", 4, "v0"), num(5, 1), instr(0x0B, 4, 5, 4), s(4, VIGIAS),
        num(5, 0), instr(0x13, 4, 5, 7), ("se_nao", 7, "v0"), RETORNA,   # há uma entrada mais nova
        ("rotulo", "v0"),
        num(4, 0), s(4, VIGIAS),
        g(1, SAINDO), g(2, RESTAURANDO), instr(0x15, 1, 2, 1), ("se_nao", 1, "v1"), RETORNA,
        ("rotulo", "v1"),
        g(1, TRAVA_MOD), g(2, TRAVA_INPUT), instr(0x14, 1, 2, 1), ("se_nao", 1, "fim"),
        nil(6), s(6, TRAVA_INPUT), s(6, TRAVA_MOD), s(6, TRANSF_EM_CURSO),   # entrada empacou
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_VIGIA_SAIDA] = [                        # 10 s após sair
        g(4, VIGIAS_SAIDA), ("se_nao", 4, "v0"), num(5, 1), instr(0x0B, 4, 5, 4),
        s(4, VIGIAS_SAIDA), num(5, 0), instr(0x13, 4, 5, 7), ("se_nao", 7, "v0"), RETORNA,
        ("rotulo", "v0"),
        num(4, 0), s(4, VIGIAS_SAIDA),
        g(1, RESTAURANDO), g(2, SAINDO), instr(0x15, 1, 2, 1), ("se_nao", 1, "fim"),
        nil(6), s(6, RESTAURANDO), s(6, SAINDO), s(6, TRANSF_EM_CURSO),   # empacou
        *solta_trava_mod("st"),
        *conta(FALHAS, 4, 5, "fa"),
        *e_especial(15, 14), ("se_nao", 15, "fim"),
        # continua na Ultimate (a volta para o Ben não aconteceu): religa o monitor
        sim(6), s(6, ATIVA), num(6, 0), s(6, PARADO), s(6, ESPERA),
        *timer(F_MONITOR, 1.5),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_DESTRAVA] = [                           # Ultimate do mod sem resposta
        *cena(4), ("se_nao", 4, "solta"), RETORNA,      # cena do jogo: as travas são dele
        ("rotulo", "solta"),
        nil(6), s(6, TRAVA_INPUT), s(6, TRAVA_MOD), s(6, TRANSF_EM_CURSO),
        RETORNA,
    ]
    f[F_RODA] = [                               # roda do canto (r0, r1, r2): sempre repassa
        nil(16), s(16, TRAVA_MOD),              # aqui os botões estão livres: trava do mod
        num(16, 0), s(16, QUADROS_TRAVA),       # nenhuma, contador da trava zerado
        *e_especial(15, 14), ("se_nao", 15, "normal"),
        sim(16), s(16, BATIDA),                 # "estou vivo" (para o monitor)
        g(16, PENDENTE), ("se_nao", 16, "repassa"),     # Ultimate de evento da fase: não mexe
        g(19, SAINDO), g(18, RESTAURANDO), instr(0x15, 19, 18, 19), ("se_nao", 19, "i0"),
        ("vai", "repassa"),                             # já está saindo
        ("rotulo", "i0"),
        # Sem as animações de interação (pacote g_u*.psp original) a Ultimate fica presa
        # "interagindo" para sempre, sem sair do lugar. Se isso durar ~10 s, volta para o
        # Ben (o objeto pode ser usado de novo). Com cd_anims.py ela interage de verdade.
        g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, h_person),
        instr(0x20, 3, 28, 1, 20), instr(0x17, 20, 21, 0, crc("isinteracting")),
        instr(0x06, 20, 22, 0), instr(0x20, 21, 22, 1, 23),
        ("se_nao", 23, "i_livre"),
        g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, crc("position")),
        instr(0x20, 3, 28, 1, 20),
        instr(0x17, 20, 21, 0, crc("x")), instr(0x17, 20, 22, 0, crc("z")),
        g(24, INT_X), instr(0x10, 21, 24, 25), g(24, INT_Z), instr(0x10, 22, 24, 26),
        instr(0x14, 25, 26, 25), s(21, INT_X), s(22, INT_Z),
        ("se_nao", 25, "i_livre"),                      # andou: está empurrando etc.
        *conta(QUADROS_INTERAGINDO, 4, 5, "ic"), *maior(4, LIMITE_INTERACAO, 7, 6),
        ("se_nao", 7, "sel"),
        num(4, 0), s(4, QUADROS_INTERAGINDO), s(4, RECUSAS),
        *sair_pelo_alien(),
        *conta(VIGIAS_SAIDA, 4, 5, "ivs"), *timer(F_VIGIA_SAIDA, 10),
        ("vai", "repassa"),
        ("rotulo", "i_livre"),
        num(4, 0), s(4, QUADROS_INTERAGINDO),
        ("rotulo", "sel"),
        instr(0x17, 0, 16, 0, crc(BOTAO_TROCA)), ("se_nao", 16, "repassa"),
        *chamar0(F_SAIR_SEGURO),
        ("vai", "repassa"),
        ("rotulo", "normal"),                   # Ben/alien: direcional ainda pendente?
        g(16, PENDENTE), ("se_nao", 16, "zera"),
        *fase(19, 17, 18), ("se_nao", 19, "n1"), ("vai", "zera"),   # evento da fase
        ("rotulo", "n1"),
        g(19, ATIVA), g(18, SAINDO), instr(0x15, 19, 18, 19), g(18, RESTAURANDO),
        instr(0x15, 19, 18, 19), ("se_nao", 19, "auto"),
        # o monitor/devolução deviam cuidar; se ficou parado ~15 s, assume que se perdeu
        *conta(QUADROS, 4, 5, "q"), *maior(4, LIMITE_QUADROS, 7, 6), ("se_nao", 7, "repassa"),
        nil(6), s(6, ATIVA), s(6, SAINDO), s(6, RESTAURANDO),
        ("rotulo", "auto"),
        g(4, FALHAS), ("se_nao", 4, "a1"), *maior(4, 2, 7, 6), ("se_nao", 7, "a1"),
        ("vai", "zera"),                        # 3 devoluções empacaram: só pelo SELECT
        ("rotulo", "a1"),
        num(4, 0), s(4, QUADROS),
        *eh_ben(18), ("se_nao", 18, "a_alien"),
        *chamar0(F_SAIR), ("vai", "repassa"),
        ("rotulo", "a_alien"),
        *chamar0(F_SAIR_SEGURO), ("vai", "repassa"),
        ("rotulo", "zera"),
        num(4, 0), s(4, QUADROS),
        ("rotulo", "repassa"),
        *([
            # Ben com os golpes do Gigante: segurando o botão de especiais (r0.0x643ccfe7),
            # a roda mostra os golpes do Gigante. O jogo só desenha os especiais quando o
            # personagem atual não é o Ben, então durante a chamada ele "vira" o Gigante.
            instr(0x17, 0, 18, 0, BOTAO_ESPECIAIS), s(18, R_SEGURO),   # para o R + SELECT
            # Ben gigante: o tamanho é reaplicado a cada quadro (se o jogo o desfizer)
            *eh_ben(26), ("se_nao", 26, "bg_fim"),
            g(26, BEN_GRANDE), ("se_nao", 26, "bg_fim"), *escala(ESCALA_BEN),
            ("rotulo", "bg_fim"),
            # sempre que o jogador vira o Ben (o jogo apaga os golpes a cada troca),
            # registra os especiais do Gigante uma vez
            *eh_ben(18), ("se_nao", 18, "esp_limpa"),
            g(27, ESP_BEN), ("se_nao", 27, "esp_add"), ("vai", "esp_ok"),
            ("rotulo", "esp_add"),
            *[x for hsp in ESPECIAIS_BEN for x in (
                g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, crc("addstartattack")),
                instr(0x05, 29, 0, 0, hsp), instr(0x20, 3, 28, 2, 20))],
            sim(27), s(27, ESP_BEN),
            ("vai", "esp_ok"),
            ("rotulo", "esp_limpa"),
            nil(27), s(27, ESP_BEN), ("vai", "rp"),
            ("rotulo", "esp_ok"),
            instr(0x17, 0, 18, 0, BOTAO_ESPECIAIS), ("se_nao", 18, "rp"),
            g(26, h_gcur), *tabela(11), instr(0x17, 11, 17, 0, crc("waybig")), s(17, h_gcur),
            instr(0x06, 0, 20, 0), instr(0x06, 1, 21, 0), instr(0x06, 2, 22, 0),
            g(23, ORIG_RODA), instr(0x20, 23, 20, 3, 24),
            s(26, h_gcur),
            RETORNA,
            ("rotulo", "rp"),
        ] if hud_ben else []),
        *(repassa_baixo() if BOTAO_TROCA == "btn_r3" else [
            instr(0x06, 0, 20, 0), instr(0x06, 1, 21, 0), instr(0x06, 2, 22, 0),
            g(23, ORIG_RODA), instr(0x20, 23, 20, 3, 24)]),
        RETORNA,
    ]
    f[F_ZONA] = [                               # câmera fixa (o jogo tira o controle de troca)
        *e_especial(15, 14), ("se_nao", 15, "fim"),
        sim(16), s(16, BATIDA),
        g(16, PENDENTE), ("se_nao", 16, "fim"),         # só a Ultimate do mod
        instr(0x17, 0, 16, 0, crc(BOTAO_TROCA)), ("se_nao", 16, "fim"),
        *chamar0(F_SAIR_SEGURO),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_QUADRO] = [                             # r0 = outro motivo (cena, morto, câmera...)
        ("se_nao", 0, "q1"), ("vai", "zera"),
        ("rotulo", "q1"),
        g(1, TRANSF_EM_CURSO), g(2, TRAVA_INPUT), g(3, TRAVA_MOD), instr(0x14, 2, 3, 3),
        instr(0x15, 1, 3, 4), ("se_nao", 4, "livre"),   # transformação ou trava do mod
        *conta(QUADROS_TRAVA, 4, 5, "c"), *maior(4, LIMITE_QUADROS, 7, 6),
        ("se_nao", 7, "fim"),
        # presa há ~15 s com o jogo rodando: solta (o que estava em andamento se perdeu)
        nil(6), s(6, TRANSF_EM_CURSO), s(6, SAINDO), s(6, RESTAURANDO),
        *solta_trava_mod("st"),
        ("vai", "zera"),
        ("rotulo", "livre"),
        g(2, TRAVA_INPUT), ("se_nao", 2, "l1"), ("vai", "zera"),
        ("rotulo", "l1"),
        nil(6), s(6, TRAVA_MOD),               # o jogo soltou a trava: não é mais do mod
        ("rotulo", "zera"),
        num(4, 0), s(4, QUADROS_TRAVA),
        ("rotulo", "fim"),
        RETORNA,
    ]
    f[F_REDE] = [                               # a cada 1 s, só com o mod em ação
        sim(1), s(1, REDE_VIVA),
        g(1, PENDENTE), g(2, ATIVA), instr(0x15, 1, 2, 1), ("se_nao", 1, "desliga"),
        g(1, MORTO), ("se_nao", 1, "vivo"), ("vai", "agenda"),   # morreu: o jogo cuida
        ("rotulo", "vivo"),
        *cena(4), ("se_nao", 4, "jogo"),
        nil(6), s(6, REDE_Y), s(6, REDE_QUEDA), ("vai", "agenda"),
        ("rotulo", "jogo"),
        g(28, h_player), g(25, h_player), instr(0x17, 25, 3, 0, crc("position")),
        instr(0x20, 3, 28, 1, 20),              # r20 = posição
        instr(0x17, 20, 21, 0, crc("y")),       # r21 = altura agora
        g(22, REDE_Y), s(21, REDE_Y),           # r22 = altura antes
        ("se_nao", 22, "agenda"),
        num(23, 4), instr(0x0A, 21, 23, 24), instr(0x13, 22, 24, 5),   # caiu mais de 4 em 1 s?
        ("se_nao", 5, "firme"),
        nil(6), s(6, REDE_FIRME),
        *conta(REDE_QUEDA, 4, 6, "q"), *maior(4, 3, 7, 6),            # 4 s seguidos caindo
        ("se_nao", 7, "agenda"),
        nil(6), s(6, REDE_QUEDA), s(6, REDE_Y),
        g(29, REDE_POS), ("se_nao", 29, "agenda"),
        g(28, crc("playermgr")), g(25, crc("playermgr")),
        instr(0x17, 25, 3, 0, crc("beam")), instr(0x20, 3, 28, 2, 4),   # volta ao seguro
        ("vai", "agenda"),
        ("rotulo", "firme"),
        nil(6), s(6, REDE_QUEDA),
        instr(0x0A, 22, 23, 24), instr(0x13, 21, 24, 5),              # subindo (pulo)?
        ("se_nao", 5, "parado"),
        nil(6), s(6, REDE_FIRME), ("vai", "agenda"),
        ("rotulo", "parado"),
        g(4, REDE_FIRME), ("se_nao", 4, "primeira"),   # 2 conferidas firme: lugar seguro
        s(20, REDE_POS), ("vai", "agenda"),
        ("rotulo", "primeira"),
        sim(6), s(6, REDE_FIRME),
        ("rotulo", "agenda"),
        *timer(F_REDE, 1),
        RETORNA,
        ("rotulo", "desliga"),                  # o mod terminou: a rede para
        nil(1), *[s(1, v) for v in (REDE_VIVA, REDE_Y, REDE_POS, REDE_QUEDA, REDE_FIRME)],
        RETORNA,
    ]
    if not rede:
        del f[F_REDE]
    return {h: montar(itens) for h, itens in f.items()}


def cmd_ultimate_livre(origem, destino, rede=True, habilidades=True, gigante=False, hud_ben=False, intro=True):
    global BOTAO_TROCA, SEM_TROCA, MANTER_ULTIMATE
    d0 = open(origem, "rb").read()
    x360 = d0[:4] == MAGIC[::-1]          # Xbox 360 / PS3: script big-endian
    if x360:
        d0 = trocar_ordem(d0, ">", "<")
        BOTAO_TROCA = "btn_r3"            # no 360 o jogo troca de alien com o R3 (gld_xbx.ds)
        print("  script do Xbox 360 (big-endian): convertido; botão da Ultimate = R3")
        if intro:
            intro = False                 # a animação longa de transformação travou no 360
            print("  Xbox 360: sem a animação longa de transformação (vira direto)")
        # Testado no Xenia: trocar os aliens do direcional no meio da fase corrompe a
        # memória do 360 (crashes em lugares diferentes). Carregando só a Ultimate, sem
        # descarregar nada, não travou.
        SEM_TROCA = MANTER_ULTIMATE = True
        print("  Xbox 360: carrega só a Ultimate (o direcional não é trocado nem descarregado)")
        if rede:
            rede = False                  # usa playermgr.beam, que os scripts do 360 não usam
            print("  Xbox 360: sem a rede de segurança contra quedas")
        if hud_ben or gigante:
            raise ValueError("--ben-gigante e --gigante ainda não existem para o Xbox 360")
    else:
        BOTAO_TROCA = "btn_select"
    d, tirou = remover_mod(d0)
    if tirou:
        print("  (o arquivo já tinha o mod: %d funções do fim retiradas antes)" % tirou)
    ops, funcs = ler(d)
    conferir_original(d, ops, funcs)
    print("  globals.ds original: %d funções (nenhuma é alterada)" % len(funcs))

    novas = []
    for h, corpo in funcoes_do_mod(rede, gigante, hud_ben, intro).items():
        novas.append((h, NPAR_MOD.get(h, 0), b"".join(corpo)))
    print("  %d funções novas do mod (nomes luis_f_...)" % len(novas))
    corpo, npar = ajustar_switch_form_update(d, funcs)
    novas.append((H_UPD, npar, corpo))
    print("  switch_form_update: SELECT -> mod, roda -> mod, direcional original")
    corpo, npar = ajustar_guardar_direcional(d, funcs)
    novas.append((GUARDAR_DIRECIONAL, npar, corpo))
    print("  guardar direcional: entrega a cópia certa se uma fase começar um evento")
    for hz in ZONAS_CAMERA:
        corpo, npar = ajustar_zona(d, funcs, hz)
        novas.append((hz, npar, corpo))
    print("  câmera fixa: SELECT ainda sai da Ultimate do mod (%d)" % len(ZONAS_CAMERA))
    if habilidades:
        for fh, mu, mb in HABILIDADES_ULTIMATE:
            corpo, npar = ajustar_habilidades(d, funcs, fh, mu, mb)
            novas.append((fh, npar, corpo))
        print("  Ultimates com as habilidades do alien normal (empurrar caixa, teia, planar...): %d"
              % len(HABILIDADES_ULTIMATE))

    saida = bytearray(d)
    for h, npar, corpo in novas:
        saida += registro(h, npar, corpo)
    struct.pack_into("<I", saida, 4, struct.unpack_from("<I", saida, 4)[0] + len(novas))
    ler(bytes(saida))  # confere se o script continua válido
    saida_le = bytes(saida)
    if bytes(saida[:len(d)]) != d[:4] + struct.pack("<I", len(funcs) + 1 + len(novas)) + d[8:]:
        raise ValueError("o começo do arquivo mudou (não devia)")
    if x360:
        saida = trocar_ordem(bytes(saida), "<", ">")   # volta para big-endian
        if trocar_ordem(saida, ">", "<") != bytes(saida_le):
            raise ValueError("a volta para big-endian não bateu (não devia)")
    with open(destino, "wb") as fo:
        fo.write(saida)
    print("%s criado (%d bytes; original %d + %d do mod no fim)" % (
        destino, len(saida), len(d), len(saida) - len(d)))


def cmd_verificar_funcoes(iso, saida):
    """Procura, em TODOS os arquivos do jogo, referências às funções do globals.ds
    (e aos nomes novos do mod, que não podem aparecer em lugar nenhum)."""
    import re
    import cd_analisador as A
    with open(iso, "rb") as f:
        magic = f.read(4)
    leitor = A.LeitorCSO(iso) if magic == b"CISO" else A.LeitorISO(iso)
    lista = A.listar_iso(leitor)

    def ler_item(item):
        _, lba, tam = item
        return leitor.ler(lba * A.SETOR, tam)

    g = [it for it in lista if it[0].lower().endswith("global/scripts/globals.ds")]
    if len(g) != 1:
        raise ValueError("não achei global/scripts/globals.ds na ISO")
    d = ler_item(g[0])
    ops, funcs = ler(d)
    cand = [f for f in funcs if d.count(struct.pack("<I", f[1])) == 1]
    padroes = {f[1]: struct.pack("<I", f[1]) for f in cand}
    nomes_mod = {}
    for nome in list(globals()):
        v = globals()[nome]
        if isinstance(v, int) and v in set(FUNCOES_MOD) | set(VARIAVEIS_MOD):
            nomes_mod[v] = nome
    for h in nomes_mod:
        padroes[h] = struct.pack("<I", h)
    refs = {h: [] for h in padroes}
    pular = (".pmf", ".at3", ".fsb", ".fev", ".png", ".ttf", ".sfo")
    alvo = [it for it in lista if not it[0].lower().endswith(pular)
            and not it[0].lower().endswith(("global/scripts/globals.ds", "global/scripts/e3global.ds"))
            and "/SYSDIR/" not in it[0].upper()]
    print("Procurando %d nomes em %d arquivos (pode levar alguns minutos)..." % (len(padroes), len(alvo)))
    for k, it in enumerate(alvo):
        dados = ler_item(it)
        nome_arq = it[0].replace("PSP_GAME/USRDIR/", "")
        for h, pk in padroes.items():
            n = dados.count(pk)
            if n:
                refs[h].append("%s:%d" % (nome_arq, n))
        # referência pelo NOME (texto): o jogo calcula o hash na hora
        for txt in set(re.findall(rb"[A-Za-z_][A-Za-z0-9_]{2,63}", dados)):
            h = zlib.crc32(txt.lower())
            if h in padroes:
                refs[h].append("%s:nome=%s" % (nome_arq, txt.decode()))
        if k % 50 == 0:
            print("  %d/%d" % (k, len(alvo)))
    choques = [h for h in nomes_mod if refs[h]]
    with open(saida, "w") as f:
        f.write("# funcao npar palavras referencias\n")
        for fn in cand:
            f.write("%08x %d %d %s\n" % (fn[1], fn[2], (fn[3] - fn[0]) // 4 - 4,
                                          " ".join(refs[fn[1]]) or "-"))
        f.write("# nomes novos do mod (precisam ficar sem referência)\n")
        for h, nome in sorted(nomes_mod.items(), key=lambda x: x[1]):
            f.write("%08x mod %s %s\n" % (h, nome, " ".join(refs[h]) or "-"))
    livres = sum(1 for h in refs if not refs[h] and h not in nomes_mod)
    print("%s criado: %d funções do jogo sem nenhuma referência" % (saida, livres))
    if choques:
        print("ATENÇÃO: %d nomes do mod aparecem no jogo: %s" % (
            len(choques), ", ".join(nomes_mod[h] for h in choques)))
    else:
        print("Nomes do mod: nenhum aparece nos arquivos do jogo (sem conflito)")


FLAGS_ESPECIAL_ULT = (0x41EB0, 0x41E30, 0x41EBC, 0x51EB4, 0x41E34, 0x55EB4, 0x41E3C)


def cmd_especiais_ultimate(pasta_origem, pasta_destino):
    """Experimento: os golpes especiais das Ultimates não têm o bit 0x4 que todos
    os especiais dos aliens normais têm (ex.: Humungossauro 0x41eb4, Ultimate
    0x41eb0). Liga esse bit nos especiais das 5 Ultimates (atk_u?.ddf)."""
    for nome in ("atk_ub", "atk_ue", "atk_uf", "atk_uh", "atk_us"):
        d = bytearray(open(os.path.join(pasta_origem, nome + ".ddf"), "rb").read())
        n = 0
        for i in range(0, len(d) - 3, 4):
            v = struct.unpack_from("<I", d, i)[0]
            if v in FLAGS_ESPECIAL_ULT:
                if not v & 4:
                    struct.pack_into("<I", d, i, v | 4)
                n += 1
        if n != 4:
            raise ValueError("%s: esperava 4 especiais, achei %d (arquivo diferente?)" % (nome, n))
        os.makedirs(pasta_destino, exist_ok=True)
        with open(os.path.join(pasta_destino, nome + ".ddf"), "wb") as f:
            f.write(d)
        print("  %s.ddf: 4 especiais ajustados" % nome)


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
        elif len(a) >= 3 and a[0] == "ultimate-livre":
            opc = a[3:]
            if "--sem-trocar-direcional" in opc:
                global SEM_TROCA
                SEM_TROCA = True
                print("  (diagnóstico: carrega só a Ultimate, sem trocar os aliens do direcional)")
            if "--manter-ultimate" in opc:
                global MANTER_ULTIMATE
                MANTER_ULTIMATE = True
                print("  (diagnóstico: ao sair, a Ultimate fica na memória)")
            cmd_ultimate_livre(a[1], a[2], rede="--sem-rede" not in opc,
                               habilidades="--sem-habilidades" not in opc,
                               gigante="--gigante" in opc, hud_ben="--ben-gigante" in opc,
                               intro="--sem-intro" not in opc)
            if "--ben-gigante" in opc:
                print("  (Ben com golpes do Gigante: segurar o botão de especiais mostra os golpes na roda;"
                      " coloque também os a_plyr.psp do cd_anims.py --ben-gigante)")
            if "--gigante" in opc:
                print("  (Tartagira -> Gigante ligado: coloque também o global/g_wayb.psp do cd_anims.py --gigante)")
            if "--sem-rede" in opc:
                print("  (rede de segurança desligada)")
            if "--sem-habilidades" in opc:
                print("  (Ultimates com as habilidades originais)")
            if "--funcoes" in opc:
                print("  (--funcoes não é mais necessário: o mod não usa funções do jogo)")
        elif len(a) == 3 and a[0] == "verificar-funcoes":
            cmd_verificar_funcoes(a[1], a[2])
        elif len(a) == 3 and a[0] == "especiais-ultimate":
            cmd_especiais_ultimate(a[1], a[2])
        else:
            print(__doc__)
            sys.exit(1)
    except (OSError, ValueError) as e:
        sys.exit("Erro: %s" % e)


if __name__ == "__main__":
    main()
