#!/usr/bin/env python3
"""
Analisador de arquivos - Ben 10 Ultimate Alien: Cosmic Destruction (PSP)
Kit de modding - ferramenta 1

Abre a ISO/CSO (ou uma pasta já extraída), lista todos os arquivos,
identifica o formato de cada um pela assinatura (magic) e procura
texturas (GIM) e modelos (GMO) escondidos dentro de pacotes.

Uso (PC ou Termux no celular):
    python cd_analisador.py jogo.iso
    python cd_analisador.py jogo.cso
    python cd_analisador.py pasta_extraida/
    python cd_analisador.py jogo.iso --extrair saida/      (extrai os arquivos da ISO)
    python cd_analisador.py jogo.iso --recortar recortes/  (salva GIM/GMO achados dentro de pacotes)
    python cd_analisador.py jogo.iso --extrair amostras --so "global/g_uhm.psp" "*atk_uh*"
                                                           (extrai só os arquivos escolhidos)

Só usa a biblioteca padrão do Python 3.8+.
"""
import argparse
import json
import math
import os
import struct
import sys
import zlib
from collections import Counter, defaultdict

SETOR = 2048

# ----------------------------------------------------------------------
# Leitura de ISO e CSO
# ----------------------------------------------------------------------

class LeitorISO:
    def __init__(self, caminho):
        self.f = open(caminho, "rb")
        self.tamanho = os.path.getsize(caminho)

    def ler(self, offset, n):
        self.f.seek(offset)
        return self.f.read(n)


class LeitorCSO:
    """CSO (CISO) v1: blocos comprimidos com deflate puro."""
    def __init__(self, caminho):
        self.f = open(caminho, "rb")
        cab = self.f.read(24)
        if cab[:4] != b"CISO":
            raise ValueError("não é um CSO válido")
        _, _, total, bloco, versao, align = struct.unpack("<4sIQIBB", cab[:22])
        self.tamanho = total
        self.bloco = bloco
        self.align = align
        nblocos = (total + bloco - 1) // bloco
        self.indice = struct.unpack("<%dI" % (nblocos + 1), self.f.read(4 * (nblocos + 1)))
        self.cache = {}

    def _bloco(self, i):
        if i in self.cache:
            return self.cache[i]
        a, b = self.indice[i], self.indice[i + 1]
        cru = a & 0x80000000
        ini = (a & 0x7FFFFFFF) << self.align
        fim = (b & 0x7FFFFFFF) << self.align
        self.f.seek(ini)
        dados = self.f.read(fim - ini)
        if not cru:
            dados = zlib.decompress(dados, -15)
        dados = dados[:self.bloco]
        if len(self.cache) > 256:
            self.cache.clear()
        self.cache[i] = dados
        return dados

    def ler(self, offset, n):
        saida = bytearray()
        while n > 0 and offset < self.tamanho:
            i, dentro = divmod(offset, self.bloco)
            pedaco = self._bloco(i)[dentro:dentro + n]
            if not pedaco:
                break
            saida += pedaco
            offset += len(pedaco)
            n -= len(pedaco)
        return bytes(saida)


def listar_iso(leitor):
    """Percorre o sistema de arquivos ISO9660 e devolve (caminho, lba, tamanho)."""
    pvd = leitor.ler(16 * SETOR, SETOR)
    if pvd[1:6] != b"CD001":
        raise ValueError("não achei o descritor ISO9660 (setor 16)")
    raiz = pvd[156:156 + 34]
    arquivos = []

    def ler_dir(lba, tam, prefixo, profundidade=0):
        if profundidade > 32:
            return
        dados = leitor.ler(lba * SETOR, tam)
        pos = 0
        while pos < len(dados):
            n = dados[pos]
            if n == 0:  # pula para o próximo setor
                pos = (pos // SETOR + 1) * SETOR
                continue
            reg = dados[pos:pos + n]
            ext_lba = struct.unpack_from("<I", reg, 2)[0]
            ext_tam = struct.unpack_from("<I", reg, 10)[0]
            flags = reg[25]
            nlen = reg[32]
            nome = reg[33:33 + nlen]
            pos += n
            if nome in (b"\x00", b"\x01"):
                continue
            nome = nome.decode("ascii", "replace").split(";")[0]
            caminho = prefixo + "/" + nome
            if flags & 2:
                ler_dir(ext_lba, ext_tam, caminho, profundidade + 1)
            else:
                arquivos.append((caminho.lstrip("/"), ext_lba, ext_tam))

    lba = struct.unpack_from("<I", raiz, 2)[0]
    tam = struct.unpack_from("<I", raiz, 10)[0]
    ler_dir(lba, tam, "")
    return arquivos


# ----------------------------------------------------------------------
# Identificação de formatos
# ----------------------------------------------------------------------

ASSINATURAS = [
    (b"MIG.00.1PSP", "GIM - textura PSP"),
    (b"OMG.00.1PSP", "GMO - modelo 3D PSP"),
    (b"\x7fELF", "ELF - executável/módulo (descriptografado)"),
    (b"~PSP", "PRX/EBOOT criptografado"),
    (b"\x00PSF", "SFO - informações do jogo"),
    (b"PSMF", "PMF - vídeo"),
    (b"VAGp", "VAG - áudio"),
    (b"\x89PNG", "PNG - imagem"),
    (b"DDS ", "DDS - textura"),
    (b"GIF8", "GIF - imagem"),
    (b"PK\x03\x04", "ZIP"),
    (b"\x1f\x8b", "GZIP"),
    (b"PPHD", "PHD - banco de som PSP"),
    (b"SSCF", "SSCF - áudio"),
    (b"MThd", "MIDI"),
    (b"OggS", "OGG - áudio"),
]

EMBUTIDOS = {b"MIG.00.1PSP": "GIM", b"OMG.00.1PSP": "GMO"}


def entropia(dados):
    if not dados:
        return 0.0
    c = Counter(dados)
    t = len(dados)
    return -sum(v / t * math.log2(v / t) for v in c.values())


def parece_texto(dados):
    if not dados:
        return False
    ok = sum(1 for b in dados if b in (9, 10, 13) or 32 <= b < 127)
    return ok / len(dados) > 0.95


def identificar(cab):
    for sig, nome in ASSINATURAS:
        if cab.startswith(sig):
            return nome
    if cab[:4] == b"RIFF":
        if b"WAVE" in cab[8:12]:
            return "RIFF/WAVE - áudio (provavelmente AT3)"
        return "RIFF"
    if len(cab) >= 2 and cab[0] == 0x78 and cab[1] in (0x01, 0x5E, 0x9C, 0xDA):
        return "ZLIB - dados comprimidos"
    if parece_texto(cab[:256]):
        return "Texto"
    return None


def tabela_de_offsets(cab, tamanho):
    """Heurística: arquivo começa com contagem + lista crescente de offsets?"""
    if len(cab) < 16:
        return None
    n = struct.unpack_from("<I", cab, 0)[0]
    if not 1 < n < 20000:
        return None
    for passo in (4, 8, 12, 16):
        vals = []
        for i in range(min(n, 32)):
            p = 4 + i * passo
            if p + 4 > len(cab):
                break
            vals.append(struct.unpack_from("<I", cab, p)[0])
        if len(vals) >= 3 and all(a < b for a, b in zip(vals, vals[1:])) and vals[-1] <= tamanho:
            return "possível pacote: %d entradas, passo %d bytes" % (n, passo)
    return None


def procurar_embutidos(ler, tamanho, limite=256 * 1024 * 1024):
    """Procura GIM/GMO dentro do arquivo. Devolve lista (tipo, offset, tamanho)."""
    achados = []
    pedaco = 4 * 1024 * 1024
    sobra = 16
    pos = 0
    fim = min(tamanho, limite)
    while pos < fim:
        dados = ler(pos, min(pedaco + sobra, fim - pos))
        if not dados:
            break
        for sig, tipo in EMBUTIDOS.items():
            i = dados.find(sig)
            while i != -1:
                if i < pedaco or pos + pedaco >= fim:
                    off = pos + i
                    cab = ler(off, 24)
                    tam = None
                    if len(cab) >= 24:
                        t = 16 + struct.unpack_from("<I", cab, 20)[0]
                        if 32 <= t <= tamanho - off:
                            tam = t
                    achados.append((tipo, off, tam))
                i = dados.find(sig, i + 1)
        pos += pedaco
    # remove duplicados
    vistos, unicos = set(), []
    for a in achados:
        if a[1] not in vistos:
            vistos.add(a[1])
            unicos.append(a)
    return unicos


# ----------------------------------------------------------------------
# Principal
# ----------------------------------------------------------------------

def coletar(origem):
    """Devolve (lista_de_arquivos, funcao_ler(arquivo, offset, n))."""
    if os.path.isdir(origem):
        lista = []
        for raiz, _, nomes in os.walk(origem):
            for nome in nomes:
                p = os.path.join(raiz, nome)
                rel = os.path.relpath(p, origem).replace(os.sep, "/")
                lista.append((rel, p, os.path.getsize(p)))

        def ler(item, off, n):
            with open(item[1], "rb") as f:
                f.seek(off)
                return f.read(n)
        return lista, ler, None

    with open(origem, "rb") as f:
        magic = f.read(4)
    leitor = LeitorCSO(origem) if magic == b"CISO" else LeitorISO(origem)
    lista = listar_iso(leitor)

    def ler(item, off, n):
        _, lba, tam = item
        n = max(0, min(n, tam - off))
        return leitor.ler(lba * SETOR + off, n)
    return lista, ler, leitor


def humano(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.0f %s" % (n, u) if u == "B" else "%.1f %s" % (n, u)
        n /= 1024
    return "%.1f TB" % n


def main():
    ap = argparse.ArgumentParser(description="Analisador de arquivos do Ben 10 Cosmic Destruction (PSP)")
    ap.add_argument("origem", help="ISO, CSO ou pasta extraída")
    ap.add_argument("--extrair", metavar="PASTA", help="extrai todos os arquivos da ISO/CSO")
    ap.add_argument("--recortar", metavar="PASTA", help="salva os GIM/GMO achados dentro de pacotes")
    ap.add_argument("--so", nargs="+", metavar="PADRAO",
                    help="analisa/extrai só os arquivos cujo caminho bate com o padrão (ex: '*g_uhm.psp' '*atk_*')")
    ap.add_argument("--saida", default="relatorio", help="nome base do relatório (padrão: relatorio)")
    args = ap.parse_args()

    print("Lendo", args.origem, "...")
    lista, ler, _ = coletar(args.origem)
    if args.so:
        import fnmatch
        def bate(caminho, padrao):
            c, p = caminho.lower(), padrao.lower().replace("\\", "/").lstrip("/")
            return fnmatch.fnmatch(c, p) or fnmatch.fnmatch(c, "*/" + p)
        lista = [i for i in lista if any(bate(i[0], p) for p in args.so)]
        if not lista:
            print("Nenhum arquivo bateu com --so", " ".join(args.so))
            sys.exit(1)
    print("%d arquivos encontrados.\n" % len(lista))

    resultado = []
    por_formato = defaultdict(lambda: [0, 0])
    por_ext = defaultdict(lambda: [0, 0])
    total_emb = Counter()

    for idx, item in enumerate(lista, 1):
        caminho, tam = item[0], item[2]
        cab = ler(item, 0, 512)
        fmt = identificar(cab)
        pacote = None if fmt else tabela_de_offsets(cab, tam)
        amostra = ler(item, 0, 65536)
        ent = round(entropia(amostra), 2)
        emb = procurar_embutidos(lambda o, n: ler(item, o, n), tam)
        emb_dentro = [e for e in emb if e[1] != 0]
        for e in emb_dentro:
            total_emb[e[0]] += 1

        if fmt is None:
            if ent > 7.8:
                fmt = "Desconhecido (comprimido/criptografado?)"
            else:
                fmt = "Desconhecido"

        ext = os.path.splitext(caminho)[1].upper() or "(sem extensão)"
        por_formato[fmt][0] += 1
        por_formato[fmt][1] += tam
        por_ext[ext][0] += 1
        por_ext[ext][1] += tam

        resultado.append({
            "arquivo": caminho,
            "tamanho": tam,
            "formato": fmt,
            "magic_hex": cab[:16].hex(" "),
            "magic_txt": "".join(chr(b) if 32 <= b < 127 else "." for b in cab[:16]),
            "entropia": ent,
            "pacote": pacote,
            "embutidos": [{"tipo": t, "offset": o, "tamanho": s} for t, o, s in emb_dentro],
        })

        if args.extrair and len(item) == 3 and not os.path.isdir(args.origem):
            destino = os.path.join(args.extrair, *caminho.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                off = 0
                while off < tam:
                    bloco = ler(item, off, 1024 * 1024)
                    if not bloco:
                        break
                    f.write(bloco)
                    off += len(bloco)

        if args.recortar:
            for t, o, s in emb_dentro:
                if not s:
                    continue
                base = caminho.replace("/", "_")
                destino = os.path.join(args.recortar, "%s@%08X.%s" % (base, o, t.lower()))
                os.makedirs(args.recortar, exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(ler(item, o, s))

        if idx % 50 == 0:
            print("  %d/%d analisados..." % (idx, len(lista)))

    # ---------------- relatório ----------------
    linhas = []
    linhas.append("RELATÓRIO - Ben 10 Ultimate Alien: Cosmic Destruction")
    linhas.append("Origem: %s" % args.origem)
    linhas.append("Arquivos: %d | Tamanho total: %s" % (len(lista), humano(sum(i[2] for i in lista))))
    linhas.append("")
    linhas.append("== POR FORMATO ==")
    for fmt, (n, t) in sorted(por_formato.items(), key=lambda x: -x[1][1]):
        linhas.append("  %-45s %5d arquivos  %10s" % (fmt, n, humano(t)))
    linhas.append("")
    linhas.append("== POR EXTENSÃO ==")
    for ext, (n, t) in sorted(por_ext.items(), key=lambda x: -x[1][1]):
        linhas.append("  %-20s %5d arquivos  %10s" % (ext, n, humano(t)))
    linhas.append("")
    linhas.append("== TEXTURAS/MODELOS DENTRO DE PACOTES ==")
    if total_emb:
        for t, n in total_emb.items():
            linhas.append("  %s: %d encontrados" % (t, n))
        linhas.append("  Arquivos que mais contêm:")
        top = sorted(resultado, key=lambda r: -len(r["embutidos"]))[:15]
        for r in top:
            if r["embutidos"]:
                c = Counter(e["tipo"] for e in r["embutidos"])
                linhas.append("    %-50s %s" % (r["arquivo"], ", ".join("%d %s" % (v, k) for k, v in c.items())))
    else:
        linhas.append("  Nenhum GIM/GMO embutido encontrado (podem estar comprimidos).")
    linhas.append("")
    linhas.append("== ARQUIVOS (maiores primeiro) ==")
    for r in sorted(resultado, key=lambda r: -r["tamanho"]):
        extra = ""
        if r["pacote"]:
            extra += "  [" + r["pacote"] + "]"
        if r["embutidos"]:
            extra += "  [%d embutidos]" % len(r["embutidos"])
        linhas.append("  %-50s %10s  ent=%.2f  %s  |%s|%s" % (
            r["arquivo"], humano(r["tamanho"]), r["entropia"], r["formato"], r["magic_txt"], extra))

    texto = "\n".join(linhas)
    with open(args.saida + ".txt", "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    with open(args.saida + ".json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)

    print("\n" + "\n".join(linhas[:40]))
    print("\nRelatório completo salvo em %s.txt e %s.json" % (args.saida, args.saida))
    print("Mande esses dois arquivos pro Claude.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as e:
        print("Erro:", e)
        sys.exit(1)
