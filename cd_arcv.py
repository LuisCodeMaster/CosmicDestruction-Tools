#!/usr/bin/env python3
"""
cd_arcv - abre o pacote ARCV do Ben 10 Alien Force: Vilgax Attacks (PSP, ULUS-10488)

No Vilgax Attacks quase o jogo inteiro fica num arquivo só, PSP_GAME/USRDIR/psp_ben10.bin.
Formato (descoberto em 22/11/2026):
    0x00  "ARCV"
    0x04  u32  quantidade de arquivos
    0x08  u32  tamanho total do pacote
    0x0C  registros de 12 bytes, ordenados pelo hash:
          u32 posição (múltiplo de 0x800), u32 tamanho, u32 crc32(caminho em minúsculas)
O pacote guarda só o hash do nome. Os nomes são os mesmos caminhos do Cosmic Destruction
("global/scripts/globals.ds"), então o kit descobre os nomes tentando caminhos candidatos:
padrões conhecidos, nomes achados dentro dos próprios arquivos e, se você tiver, a lista
de arquivos de outra ISO (--nomes-de, por exemplo a do Cosmic Destruction).

Uso (Termux):
    python cd_arcv.py vilgax.iso                         lista e gera arcv_lista.txt
    python cd_arcv.py vilgax.iso --nomes-de cosmic.iso   usa os nomes da outra ISO também
    python cd_arcv.py vilgax.iso --extrair saida         extrai tudo
    python cd_arcv.py vilgax.iso --extrair saida --so "global/scripts/*"
    python cd_arcv.py vilgax.iso --procurar alienx        procura um nome em todos os arquivos
    python cd_arcv.py vilgax.iso --colocar pasta_mod saida.iso
        coloca na cópia da ISO os arquivos da pasta_mod (caminho de dentro do pacote, como
        global/scripts/globals.ds, ou _sem_nome/XXXXXXXX.bin). Cada arquivo novo precisa caber no
        espaço do antigo dentro do pacote (até o começo do arquivo seguinte); a ISO original não muda.
Também aceita o psp_ben10.bin já extraído no lugar da ISO.
Arquivos sem nome descoberto saem como _sem_nome/XXXXXXXX.bin (o hash).
A primeira vez demora (procura os nomes); os nomes ficam em arcv_nomes.txt e as próximas vezes são rápidas.

Só usa a biblioteca padrão do Python 3.8+.
"""
import argparse
import fnmatch
import os
import re
import struct
import sys
import zlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cd_analisador import LeitorISO, LeitorCSO, listar_iso, SETOR  # noqa: E402

PACOTE = "psp_game/usrdir/psp_ben10.bin"
CACHE = "arcv_nomes.txt"      # nomes descobertos na primeira vez (lista de caminhos, sem dados do jogo)

EXTENSOES = ("psp", "ds", "ddf", "txt", "fsb", "at", "cre", "ttf", "cnf", "prx", "dat", "bin")
SCRIPTS_GLOBAIS = (
    "globals ai_gen debug frontend gld_psp gld_w32 sgdebug sgstatsp utppstat char e3global "
    "e3frtend e3cdisp circdisp effects halo missions player psp rain sndbnk sounds universe "
    "archetyp filt_us filt_fr filt_ge filt_it filt_sp text_us text_fr text_ge text_it text_sp"
).split()
ALIENS = (
    "ben bigchill brainstorm chromastone echoecho goop humungousaur jetray spidermonkey "
    "swampfire cannonbolt alienx upchuck rath fourarms heatblast diamondhead"
).split()
# códigos de 2 letras dos aliens no Vilgax Attacks (global/a_XX.psp, e_XX.psp)
CODIGOS = "bc bs cb cs ec gp hm jr sf sm bn ax uc ben plyr".split()


class Fatia:
    """Lê um pedaço de outro leitor como se fosse um arquivo só."""
    def __init__(self, leitor, inicio, tamanho):
        self.leitor, self.inicio, self.tamanho = leitor, inicio, tamanho

    def ler(self, offset, n):
        n = max(0, min(n, self.tamanho - offset))
        return self.leitor.ler(self.inicio + offset, n)


def abrir(caminho):
    """Devolve (leitor do pacote ARCV, lista de caminhos da ISO ou [])."""
    if os.path.isdir(caminho):
        alvo = os.path.join(caminho, *PACOTE.split("/"))
        if not os.path.exists(alvo):
            alvo = os.path.join(caminho, "psp_ben10.bin")
        return LeitorISO(alvo), []
    with open(caminho, "rb") as f:
        cab = f.read(4)
    if cab == b"ARCV":
        return LeitorISO(caminho), []
    leitor = LeitorCSO(caminho) if cab == b"CISO" else LeitorISO(caminho)
    arquivos = listar_iso(leitor)
    for nome, lba, tam in arquivos:
        if nome.lower() == PACOTE:
            return Fatia(leitor, lba * SETOR, tam), [a[0].lower() for a in arquivos]
    raise SystemExit("Não achei %s nessa ISO. É mesmo o Vilgax Attacks?" % PACOTE)


def ler_tabela(pac):
    cab = pac.ler(0, 12)
    if cab[:4] != b"ARCV":
        raise SystemExit("O pacote não começa com ARCV.")
    n, total = struct.unpack_from("<II", cab, 4)
    dados = pac.ler(12, 12 * n)
    return [struct.unpack_from("<3I", dados, 12 * i) for i in range(n)], total


def nomes_da_iso(caminho):
    leitor = LeitorCSO(caminho) if open(caminho, "rb").read(4) == b"CISO" else LeitorISO(caminho)
    saida = set()
    for nome, _, _ in listar_iso(leitor):
        nome = nome.lower()
        if nome.startswith("psp_game/usrdir/"):
            nome = nome[16:]
        saida.add(nome)
    return saida


RE_NOME = re.compile(rb"[A-Za-z0-9_\\/.\-]{3,64}")


def palavras(dados):
    """Pedaços de texto dentro de um arquivo que podem ser nomes de arquivo."""
    for m in RE_NOME.finditer(dados):
        t = m.group().decode("ascii").lower().replace("\\", "/").strip("./")
        if t:
            yield t


def descobrir_nomes(pac, tabela, extras, caminhos_iso, log=print):
    por_hash = {h: (o, s) for o, s, h in tabela}
    achados = {}

    cabecas = {}

    def combina(nome, h):
        """O nome só vale se a extensão combina com o que o arquivo é de verdade.
        Sem isso, pedaços aleatórios de dados batem com algum hash por coincidência."""
        if ".pmf" in nome or "/" in nome and not all(re.fullmatch(r"[a-z0-9_]+", p) for p in nome.split("/")[:-1]):
            return False
        if h not in cabecas:
            o, s = por_hash[h]
            cabecas[h] = tipo(pac.ler(o, 16))
        t = cabecas[h]
        ext = nome.rsplit(".", 1)[-1] if "." in nome else ""
        if t.startswith("script"):
            return ext in ("ds", "ddf", "at", "cnf", "cre", "dat")
        if t.startswith("spav"):
            return ext == "psp"
        if t.startswith("FSB4"):
            return ext == "fsb"
        if t == "texto":
            return ext in ("txt", "ddf", "cnf", "cre", "ini", "dat")
        if t.startswith("CARC"):
            return False          # ainda não sabemos a extensão dos CARC: melhor sem nome que nome errado
        return True               # outros tipos (fontes, módulos, áudio): aceita

    def tentar(nome):
        nome = nome.strip("/")
        h = zlib.crc32(nome.encode("latin-1", "replace"))
        if h in por_hash and h not in achados and combina(nome, h):
            achados[h] = nome
            return True
        return False

    pastas = {"global", "global/scripts", "global/sounds", "global/vo", "global/fx"}
    for c in caminhos_iso:                        # as pastas de vídeo dão os nomes das fases
        partes = c.split("/")
        for p in partes:
            if p.startswith("l_"):
                pastas |= {p, p + "/scripts", p + "/sounds"}
    bases = {"a_plyr.psp", "global.psp", "gtex_s.psp", "ben10.ttf", "credits.cre"}
    for b in SCRIPTS_GLOBAIS:
        bases |= {b + ".ds", b + ".ddf", b + ".txt", b + ".at"}
    for c in CODIGOS:
        bases |= {"a_%s.psp" % c, "e_%s.psp" % c, "g_%s.psp" % c, "atk_%s.ddf" % c, "a_%s_s.psp" % c}
    for a in ALIENS:
        bases |= {"g_%s.psp" % a, "g_%s_ult.psp" % a, "atk_%s.ddf" % a, "a_%s.psp" % a}
    for p in list(pastas):
        if p.startswith("l_") and "/" not in p:
            bases.add(p + ".psp")
            bases |= {"%s_%s.psp" % (p, x) for x in "abcdefghijklmnopqrstuvwxyz"}
            bases |= {"%s_%s.psp" % (p, x) for x in ("ks", "kv", "fx", "snd", "ui")}
            bases |= {"vo_%s.ds" % p[2:], "vo_%s.fsb" % p[2:], "%s.ds" % p[2:], "%s.ds" % p}
    for e in extras:
        if "/" in e:
            pastas.add(e.rsplit("/", 1)[0])
        bases.add(e.rsplit("/", 1)[-1])
        tentar(e)

    feitas = set()      # pastas já combinadas com todos os nomes

    def rodada():
        antes = len(achados)
        for p in sorted(pastas - feitas):
            for b in bases:
                tentar(p + "/" + b)
            feitas.add(p)
        for b in bases:
            tentar(b)
        return len(achados) - antes

    rodada()
    # procura nomes dentro dos arquivos pequenos (scripts e listas citam outros arquivos).
    # Lê cada arquivo uma vez só; depois as voltas só combinam pastas e nomes.
    log("  lendo os arquivos pequenos atrás de nomes...")
    textos = set()
    for o, s, h in tabela:
        if s <= 2 * 1024 * 1024:
            textos.update(palavras(pac.ler(o, s)))
    feitas.clear()      # chegaram nomes novos: todas as pastas precisam ser combinadas de novo
    for t in textos:
        if tentar(t):
            continue
        b = t.rsplit("/", 1)[-1]
        if "." in b:
            bases.add(b)
        else:
            bases.update(b + "." + x for x in EXTENSOES)
    for volta in range(5):
        for n in achados.values():
            if "/" in n:
                pastas.add(n.rsplit("/", 1)[0])
        novas_pastas = len(pastas - feitas)
        ganho = rodada()
        log("  volta %d: %d nomes no total (%d pastas novas)" % (volta + 1, len(achados), novas_pastas))
        if not ganho:
            break
    return achados


def tipo(cab):
    if cab[:4] == b"\xbe\xba\xad\x1b":
        return "script .ds (0x1BADBABE)"
    if cab[:4] == b"CARC":
        return "CARC (pacote dentro do pacote)"
    if cab[:4] == b"FSB4":
        return "FSB4 (sons)"
    if cab[:4] == b"spav" or cab[:4] == b"vaps":
        return "spav (pacote .psp)"
    imprimivel = sum(32 <= c < 127 or c in (9, 10, 13) for c in cab)
    if cab and imprimivel == len(cab):
        return "texto"
    return "outro (%s)" % cab[:4].hex(" ")


def variantes(nome):
    """Jeitos como um nome pode aparecer: texto e crc32 (o jogo guarda muitos nomes só como hash)."""
    n = nome.lower()
    juntos = n.replace(" ", "").replace("_", "").replace("-", "")
    formas = {n, juntos, n.replace(" ", "_"), n.replace("_", " ")}
    if len(juntos) > 4 and juntos.startswith("alien"):
        formas |= {"alien_" + juntos[5:], "alien " + juntos[5:]}
    textos = {f.encode() for f in formas if len(f) >= 4}
    hashes = {}
    for f in formas:
        for v in (f, "ben_" + f, f + "_name_callout", "g_" + f + ".psp", "a_" + f + ".psp", "atk_" + f + ".ddf"):
            hashes[struct.pack("<I", zlib.crc32(v.encode()))] = v
    return textos, hashes


def procurar(pac, tabela, nomes, alvos):
    textos, hashes = set(), {}
    for alvo in alvos:
        t, h = variantes(alvo)
        textos |= t
        hashes.update(h)
    print("\nProcurando %s em %d arquivos (lê o pacote inteiro, demora alguns minutos)..." % (", ".join(alvos), len(tabela)))
    print("Texto achado é sinal forte. Hash achado fora de script pode ser coincidência.")
    achou = 0
    for n, (o, s, h) in enumerate(sorted(tabela)):
        nome = nomes.get(h, "_sem_nome/%08x.bin" % h)
        cab = pac.ler(o, 16)
        t = tipo(cab)
        pos, resto = 0, b""
        vistos = set()
        while pos < s:
            pedaco = pac.ler(o + pos, min(4 << 20, s - pos))
            bloco = resto + pedaco
            minus = bloco.lower()
            base = pos - len(resto)
            for tx in textos:
                i = minus.find(tx)
                while i >= 0:
                    if ("t", base + i) not in vistos:
                        vistos.add(("t", base + i))
                        trecho = bloco[max(0, i - 24):i + len(tx) + 24]
                        print("  TEXTO  %-34s +0x%08x  %r" % (nome, base + i, trecho))
                        achou += 1
                    i = minus.find(tx, i + 1)
            for hb, v in hashes.items():
                i = bloco.find(hb)
                while i >= 0:
                    if ("h", base + i) not in vistos:
                        vistos.add(("h", base + i))
                        print("  HASH   %-34s +0x%08x  crc32(%s)  [%s]" % (nome, base + i, v, t))
                        achou += 1
                    i = bloco.find(hb, i + 1)
            resto = bloco[-64:]
            pos += len(pedaco)
        if n % 50 == 0:
            print("  ... %d de %d arquivos" % (n, len(tabela)))
    print("Procura terminada: %d ocorrências." % achou)
    if not achou:
        print("Nada encontrado. Obs.: o conteúdo dos CARC é comprimido e não entra nesta procura.")


def colocar(iso, pasta, saida, nomes):
    """Troca arquivos do ARCV numa cópia da ISO, no espaço que cada um já ocupa."""
    import shutil
    if os.path.abspath(iso) == os.path.abspath(saida):
        raise SystemExit("A saída precisa ser outro arquivo (a ISO original não é alterada).")
    with open(iso, "rb") as f:
        if f.read(4) == b"CISO":
            raise SystemExit("Para colocar arquivos, use a .iso (não a .cso).")
    leitor = LeitorISO(iso)
    inicio = None
    for nome, lba, tam in listar_iso(leitor):
        if nome.lower() == PACOTE:
            inicio = lba * SETOR
    if inicio is None:
        raise SystemExit("Não achei %s nessa ISO." % PACOTE)
    pac = Fatia(leitor, inicio, 1 << 40)
    tabela, total = ler_tabela(pac)
    por_nome = {v: h for h, v in nomes.items()}
    pos_tab = {h: i for i, (o, s, h) in enumerate(tabela)}
    fins = sorted(o for o, s, h in tabela) + [total]
    trocas = []
    for raiz, _, arqs in os.walk(pasta):
        for n in arqs:
            caminho = os.path.join(raiz, n)
            rel = os.path.relpath(caminho, pasta).replace("\\", "/").lower()
            m = re.fullmatch(r"(?:.*/)?_sem_nome/([0-9a-f]{8})\.bin", rel)
            h = int(m.group(1), 16) if m else por_nome.get(rel, zlib.crc32(rel.encode()))
            if h not in pos_tab:
                raise SystemExit("%s não existe no pacote." % rel)
            o, s, _ = tabela[pos_tab[h]]
            espaco = next(f for f in fins if f > o) - o
            novo = open(caminho, "rb").read()
            if len(novo) > espaco:
                raise SystemExit("%s tem %d bytes e o espaço dele no pacote é %d (sobram %d de menos).\n"
                                 "Diminua o arquivo e tente de novo." % (rel, len(novo), espaco, len(novo) - espaco))
            trocas.append((rel, h, o, s, novo, espaco))
    if not trocas:
        raise SystemExit("A pasta %s está vazia." % pasta)
    print("Copiando a ISO (pode demorar um pouco)...")
    shutil.copyfile(iso, saida)
    with open(saida, "r+b") as f:
        for rel, h, o, s, novo, espaco in trocas:
            f.seek(inicio + o)
            f.write(novo + b"\0" * (max(s, len(novo)) - len(novo)))
            f.seek(inicio + 12 + 12 * pos_tab[h] + 4)
            f.write(struct.pack("<I", len(novo)))
            print("  %s: %d -> %d bytes (espaço %d)" % (rel, s, len(novo), espaco))
    print("%s criado com %d arquivos trocados." % (saida, len(trocas)))


def main():
    ap = argparse.ArgumentParser(description="Abre o pacote ARCV do Vilgax Attacks (psp_ben10.bin).")
    ap.add_argument("origem", help="ISO/CSO do Vilgax Attacks, pasta extraída ou o psp_ben10.bin")
    ap.add_argument("--nomes-de", action="append", default=[], help="outra ISO cuja lista de arquivos ajuda a achar nomes")
    ap.add_argument("--extrair", metavar="PASTA", help="extrai os arquivos para esta pasta")
    ap.add_argument("--so", nargs="+", metavar="PADRAO", help="só extrai os arquivos que batem com estes padrões")
    ap.add_argument("--procurar", nargs="+", metavar="NOME", help="procura estes nomes (texto e hash) dentro de todos os arquivos")
    ap.add_argument("--colocar", nargs=2, metavar=("PASTA_MOD", "SAIDA_ISO"), help="coloca os arquivos da pasta numa cópia da ISO")
    ap.add_argument("--redescobrir", action="store_true", help="procura os nomes de novo em vez de usar arcv_nomes.txt")
    a = ap.parse_args()

    print("Lendo %s ..." % a.origem)
    pac, caminhos_iso = abrir(a.origem)
    tabela, total = ler_tabela(pac)
    print("Pacote ARCV: %d arquivos, %.1f MB." % (len(tabela), total / 1048576))

    extras = set()
    for outra in a.nomes_de:
        print("Pegando nomes de %s ..." % outra)
        extras |= nomes_da_iso(outra)
    hashes = {h for _, _, h in tabela}
    if os.path.exists(CACHE) and not a.redescobrir:
        nomes = {}
        with open(CACHE, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and zlib.crc32(linha.encode("latin-1", "replace")) in hashes:
                    nomes[zlib.crc32(linha.encode("latin-1", "replace"))] = linha
        print("Usando os nomes já descobertos em %s (%d). Para procurar de novo: --redescobrir" % (CACHE, len(nomes)))
    else:
        print("Descobrindo nomes (demora alguns minutos; só na primeira vez)...")
        nomes = descobrir_nomes(pac, tabela, extras, caminhos_iso)
        with open(CACHE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(nomes.values())) + "\n")

    linhas, tipos = [], Counter()
    for o, s, h in sorted(tabela, key=lambda e: e[0]):
        t = tipo(pac.ler(o, 16))
        tipos[t] += 1
        linhas.append("%08x  %10d  %10d  %-32s %s" % (h, o, s, t, nomes.get(h, "?")))
    with open("arcv_lista.txt", "w", encoding="utf-8") as f:
        f.write("hash      posição     tamanho     %-32s nome\n" % "tipo")
        f.write("\n".join(linhas) + "\n")

    print("\nNomes descobertos: %d de %d" % (len(nomes), len(tabela)))
    print("Tipos (pela assinatura):")
    for t, n in tipos.most_common():
        print("  %-36s %d" % (t, n))
    gl = zlib.crc32(b"global/scripts/globals.ds")
    for o, s, h in tabela:
        if h == gl:
            ok = pac.ler(o, 4) == b"\xbe\xba\xad\x1b"
            print("\nglobals.ds: %d bytes, %s" % (s, "MESMO formato de script do Cosmic Destruction"
                                                   if ok else "assinatura diferente: %s" % pac.ler(o, 4).hex(" ")))
    print("Lista completa salva em arcv_lista.txt")

    if a.colocar:
        colocar(a.origem, a.colocar[0], a.colocar[1], nomes)
        return

    if a.procurar:
        procurar(pac, tabela, nomes, a.procurar)

    if a.extrair:
        feitos = 0
        for o, s, h in tabela:
            nome = nomes.get(h, "_sem_nome/%08x.bin" % h)
            if a.so and not any(fnmatch.fnmatch(nome, p.lower()) for p in a.so):
                continue
            destino = os.path.join(a.extrair, *nome.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                pos = 0
                while pos < s:
                    pedaco = pac.ler(o + pos, min(4 << 20, s - pos))
                    f.write(pedaco)
                    pos += len(pedaco)
            feitos += 1
        print("%d arquivos extraídos em %s" % (feitos, a.extrair))


if __name__ == "__main__":
    main()
