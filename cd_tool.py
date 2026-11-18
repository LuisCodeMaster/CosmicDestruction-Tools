#!/usr/bin/env python3
"""
cd_tool - Kit de modding do Ben 10 Ultimate Alien: Cosmic Destruction (PSP)
Ferramenta 2: textos e arquivos de dados (.ddf)

COMANDOS
  Textos (psp_us.txt, psp_sp.txt, ...):
    python cd_tool.py texto-exportar psp_us.txt textos.txt
    python cd_tool.py texto-importar psp_us.txt textos.txt psp_us_novo.txt

  Dados binários (atk_hm.ddf, player.ddf, missions.ddf, ...):
    python cd_tool.py ddf-exportar atk_hm.ddf atk_hm.json
    python cd_tool.py ddf-importar atk_hm.json atk_hm_novo.ddf

  Comparar dois .ddf (ex: Humungossauro normal x Ultimate):
    python cd_tool.py ddf-comparar atk_hm.ddf atk_uh.ddf

Opção para todos os comandos ddf: --nomes lista.txt
  (arquivo com um nome por linha; o programa descobre quais hashes eles resolvem)

FORMATOS DESCOBERTOS
  Todo arquivo começa com 0x1BADBABE.
  Textos:  [hash u32][tamanho u32][texto + \\0] ... repetido
  DDF:     registros [hash nome][hash tipo][hash desc][qtd][ptr][tamanho][dados]
  Os hashes são CRC32 do nome em minúsculas (ex: crc32("attack")).

Só usa a biblioteca padrão do Python 3.8+.
"""
import json
import os
import re
import struct
import sys
import zlib

MAGIC = b"\xbe\xba\xad\x1b"

# Nomes já confirmados (crc32 bate). Adicione outros com --nomes.
NOMES_CONHECIDOS = """
attack special special1 special2 special3 special4 knockback hm_flurry
ground down tail hard gwen player playermgr mission timeouttracker
rushmore military paris rome_day rome_night china tokyo_day tokyo_night test_level
humungousaur ultimate_humungousaur spidermonkey ultimate_spidermonkey bigchill
ultimate_bigchill echoecho ultimate_echoecho swampfire ultimate_swampfire
waterhazard terraspin nrg armodrillo ampfibian rath fourarms ben
""".split()


def crc(nome):
    return zlib.crc32(nome.lower().encode("latin-1"))


def carregar_nomes(extra=None):
    nomes = list(NOMES_CONHECIDOS)
    if extra:
        with open(extra, encoding="utf-8", errors="replace") as f:
            for linha in f:
                for w in re.findall(r"[A-Za-z0-9_\\/.\-]+", linha):
                    nomes.append(w)
    tabela = {}
    for n in nomes:
        tabela.setdefault(crc(n), n.lower())
    return tabela


def checar_magic(dados, caminho):
    if dados[:4] != MAGIC:
        sys.exit("Erro: %s não começa com 0x1BADBABE (não é um arquivo desse formato)" % caminho)


# ----------------------------------------------------------------------
# TEXTOS
# ----------------------------------------------------------------------

def ler_textos(dados):
    p, itens = 4, []
    while p < len(dados):
        h, n = struct.unpack_from("<II", dados, p)
        s = dados[p + 8:p + 8 + n]
        p += 8 + n
        itens.append((h, s[:-1] if s.endswith(b"\0") else s))
    return itens


def escapar(s):
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def desescapar(s):
    saida, i = [], 0
    mapa = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\"}
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] in mapa:
            saida.append(mapa[s[i + 1]])
            i += 2
        else:
            saida.append(s[i])
            i += 1
    return "".join(saida)


def texto_exportar(origem, destino):
    dados = open(origem, "rb").read()
    checar_magic(dados, origem)
    itens = ler_textos(dados)
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Textos de %s - %d frases\n" % (os.path.basename(origem), len(itens)))
        f.write("# Formato: HASH|texto   (edite só o texto depois do |)\n")
        f.write("# Quebra de linha = \\n. Linhas começando com # são ignoradas.\n")
        for h, s in itens:
            f.write("%08x|%s\n" % (h, escapar(s.decode("latin-1"))))
    print("%d frases exportadas para %s" % (len(itens), destino))


def texto_importar(original, editado, destino):
    dados = open(original, "rb").read()
    checar_magic(dados, original)
    itens = ler_textos(dados)
    novos = {}
    with open(editado, encoding="utf-8") as f:
        for num, linha in enumerate(f, 1):
            linha = linha.rstrip("\n")
            if not linha or linha.startswith("#"):
                continue
            if "|" not in linha:
                sys.exit("Erro na linha %d: falta o |" % num)
            h, txt = linha.split("|", 1)
            try:
                novos[int(h, 16)] = desescapar(txt)
            except ValueError:
                sys.exit("Erro na linha %d: hash inválido '%s'" % (num, h))
    saida = bytearray(MAGIC)
    trocados, sem_suporte = 0, set()
    for h, s in itens:
        if h in novos:
            t = novos[h]
            try:
                b = t.encode("latin-1")
            except UnicodeEncodeError:
                for c in t:
                    try:
                        c.encode("latin-1")
                    except UnicodeEncodeError:
                        sem_suporte.add(c)
                b = t.encode("latin-1", "replace")
            if b != s:
                trocados += 1
            s = b
        s += b"\0"
        saida += struct.pack("<II", h, len(s)) + s
    with open(destino, "wb") as f:
        f.write(saida)
    print("%s criado. %d frases alteradas." % (destino, trocados))
    if sem_suporte:
        print("AVISO: caracteres fora do latin-1 viraram '?':", "".join(sorted(sem_suporte)))


# ----------------------------------------------------------------------
# DDF
# ----------------------------------------------------------------------

def ler_ddf(dados):
    p, regs = 4, []
    while p + 24 <= len(dados):
        cab = struct.unpack_from("<6I", dados, p)
        tam = cab[5]
        regs.append((cab, dados[p + 24:p + 24 + tam]))
        p += 24 + tam
    sobra = dados[p:]
    return regs, sobra


def f32(v):
    return struct.unpack("<f", struct.pack("<I", v))[0]


def float_curto(v):
    """Menor representação decimal que volta exatamente ao mesmo float32."""
    f = f32(v)
    for casas in range(1, 10):
        s = "%.*g" % (casas, f)
        if struct.pack("<f", float(s)) == struct.pack("<I", v):
            return float(s)
    return f


def palavra_para_json(v, nomes):
    """Converte 4 bytes em algo legível e que volta exatamente igual."""
    if v == 0:
        return 0
    if v in nomes:
        return "#" + nomes[v]
    if v < 0x10000:
        return v
    f = f32(v)
    exp = (v >> 23) & 0xFF
    if 100 < exp < 150:  # float com magnitude razoável (~1e-8 a ~1e7)
        return float_curto(v)
    return "0x%08x" % v


def json_para_palavra(x):
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x & 0xFFFFFFFF
    if isinstance(x, float):
        return struct.unpack("<I", struct.pack("<f", x))[0]
    if isinstance(x, str):
        if x.startswith("#"):
            return crc(x[1:])
        if x.lower().startswith("0x"):
            return int(x, 16)
        if x.lower().startswith("i:"):
            return int(x[2:]) & 0xFFFFFFFF
        if x.lower().startswith("f:"):
            return struct.unpack("<I", struct.pack("<f", float(x[2:])))[0]
    raise ValueError("valor inválido: %r" % (x,))


def nome_hash(v, nomes):
    return "#" + nomes[v] if v in nomes else "0x%08x" % v


def ddf_exportar(origem, destino, nomes):
    dados = open(origem, "rb").read()
    checar_magic(dados, origem)
    regs, sobra = ler_ddf(dados)
    saida = {
        "_info": "Gerado por cd_tool. Numeros com ponto = float; inteiros = int; "
                 "'#nome' = hash crc32; '0x...' = valor cru. Edite os valores e use ddf-importar.",
        "arquivo": os.path.basename(origem),
        "registros": [],
        "sobra_hex": sobra.hex(),
    }
    resolvidos = 0
    for cab, corpo in regs:
        n = len(corpo) // 4
        palavras = struct.unpack("<%dI" % n, corpo[:n * 4])
        campos = [palavra_para_json(v, nomes) for v in palavras]
        resolvidos += sum(1 for c in campos if isinstance(c, str) and c.startswith("#"))
        saida["registros"].append({
            "nome": nome_hash(cab[0], nomes),
            "tipo": nome_hash(cab[1], nomes),
            "desc": nome_hash(cab[2], nomes),
            "qtd": cab[3],
            "ptr": "0x%08x" % cab[4],
            "campos": campos,
            "resto_hex": corpo[n * 4:].hex(),
        })
    with open(destino, "w", encoding="utf-8") as f:
        f.write("{\n")
        f.write(' "_info": %s,\n' % json.dumps(saida["_info"], ensure_ascii=False))
        f.write(' "arquivo": %s,\n' % json.dumps(saida["arquivo"]))
        f.write(' "sobra_hex": %s,\n' % json.dumps(saida["sobra_hex"]))
        f.write(' "registros": [\n')
        for i, r in enumerate(saida["registros"]):
            campos = r.pop("campos")
            cab = json.dumps(r, ensure_ascii=False)[:-1]
            linhas = []
            for j in range(0, len(campos), 8):
                linhas.append("   " + ", ".join(json.dumps(c) for c in campos[j:j + 8]))
            f.write("  %s,\n   \"campos\": [  // %d campos\n%s\n  ]}%s\n" % (
                cab, len(campos), ",\n".join(linhas), "," if i < len(saida["registros"]) - 1 else ""))
        f.write(" ]\n}\n")
    print("%d registros exportados para %s (%d hashes com nome conhecido)" % (len(regs), destino, resolvidos))


def ler_json_com_comentarios(caminho):
    texto = open(caminho, encoding="utf-8").read()
    texto = re.sub(r"//[^\n]*", "", texto)
    return json.loads(texto)


def ddf_importar(origem, destino):
    j = ler_json_com_comentarios(origem)
    saida = bytearray(MAGIC)
    for i, r in enumerate(j["registros"]):
        try:
            corpo = b"".join(struct.pack("<I", json_para_palavra(c)) for c in r["campos"])
            corpo += bytes.fromhex(r.get("resto_hex", ""))
            cab = struct.pack("<6I",
                              json_para_palavra(r["nome"]), json_para_palavra(r["tipo"]),
                              json_para_palavra(r["desc"]), r["qtd"],
                              json_para_palavra(r["ptr"]), len(corpo))
        except (ValueError, KeyError, struct.error) as e:
            sys.exit("Erro no registro %d: %s" % (i, e))
        saida += cab + corpo
    saida += bytes.fromhex(j.get("sobra_hex", ""))
    with open(destino, "wb") as f:
        f.write(saida)
    print("%s criado (%d registros, %d bytes)" % (destino, len(j["registros"]), len(saida)))


def ddf_comparar(a, b, nomes):
    ra, _ = ler_ddf(open(a, "rb").read())
    rb, _ = ler_ddf(open(b, "rb").read())
    print("%s: %d registros | %s: %d registros\n" % (a, len(ra), b, len(rb)))
    na = max(len(c) for c, _ in ra) if ra else 0
    tam = min(len(ra[0][1]), len(rb[0][1])) // 4 if ra and rb else 0
    print("Campo a campo (valores de todos os registros de cada arquivo):")
    for k in range(tam):
        va = sorted({palavra_para_json(struct.unpack_from("<I", d, k * 4)[0], nomes) for _, d in ra}, key=str)
        vb = sorted({palavra_para_json(struct.unpack_from("<I", d, k * 4)[0], nomes) for _, d in rb}, key=str)
        marca = "  " if va == vb else "<>"
        print("%s campo %2d | %-45s | %s" % (marca, k, str(va)[:45], str(vb)[:60]))


# ----------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    extra = None
    if "--nomes" in args:
        i = args.index("--nomes")
        extra = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]
    nomes = carregar_nomes(extra)
    try:
        if cmd == "texto-exportar" and len(resto) == 2:
            texto_exportar(*resto)
        elif cmd == "texto-importar" and len(resto) == 3:
            texto_importar(*resto)
        elif cmd == "ddf-exportar" and len(resto) == 2:
            ddf_exportar(resto[0], resto[1], nomes)
        elif cmd == "ddf-importar" and len(resto) == 2:
            ddf_importar(*resto)
        elif cmd == "ddf-comparar" and len(resto) == 2:
            ddf_comparar(resto[0], resto[1], nomes)
        else:
            print(__doc__)
            sys.exit(1)
    except OSError as e:
        sys.exit("Erro: %s" % e)


if __name__ == "__main__":
    main()
