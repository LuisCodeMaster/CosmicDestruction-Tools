#!/usr/bin/env python3
"""
cd_texturas - Kit de modding do Ben 10 Ultimate Alien: Cosmic Destruction (PSP)
Ferramenta 3: texturas dos arquivos .psp (formato "spav")

COMANDOS
  Listar as texturas de um arquivo:
    python cd_texturas.py listar g_hm.psp

  Exportar todas as texturas para PNG:
    python cd_texturas.py exportar g_hm.psp pasta_png

  Importar os PNG editados e gerar um .psp novo:
    python cd_texturas.py importar g_hm.psp pasta_png g_hm_novo.psp

REGRAS PARA EDITAR
  - Mantenha o mesmo nome de arquivo e o MESMO tamanho (largura x altura).
  - Pode usar qualquer cor: o programa reduz para 256 cores sozinho.
  - Transparência do PNG é mantida.
  - Só os PNG que você mudou são reimportados; os outros ficam iguais.

FORMATO DESCOBERTO
  .psp = contêiner "spav" com blocos (tipo, tamanho, offset). Bloco tipo 0 = texturas.
  Textura = cabeçalho de 128 bytes + pixels 8 bits (com swizzle do PSP
  em blocos de 16x8) + paleta de 256 cores RGBA.

Só usa a biblioteca padrão do Python 3.8+.
"""
import os
import struct
import sys
import zlib

MAGIC = b"spav"


# ----------------------------------------------------------------------
# PNG (leitura e escrita, só biblioteca padrão)
# ----------------------------------------------------------------------

def png_salvar(caminho, w, h, rgba):
    linhas = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def bloco(tipo, dados):
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))
    with open(caminho, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(bloco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(bloco(b"IDAT", zlib.compress(linhas, 9)))
        f.write(bloco(b"IEND", b""))


def png_ler(caminho):
    """Lê PNG 8 bits (cinza, RGB, paleta, cinza+alfa, RGBA), sem entrelaçamento. Devolve w, h, RGBA."""
    dados = open(caminho, "rb").read()
    if dados[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("não é PNG")
    p, idat, plte, trns = 8, b"", None, None
    while p < len(dados):
        n, tipo = struct.unpack_from(">I4s", dados, p)
        corpo = dados[p + 8:p + 8 + n]
        p += 12 + n
        if tipo == b"IHDR":
            w, h, prof, cor, _, _, entrel = struct.unpack(">IIBBBBB", corpo)
        elif tipo == b"PLTE":
            plte = corpo
        elif tipo == b"tRNS":
            trns = corpo
        elif tipo == b"IDAT":
            idat += corpo
        elif tipo == b"IEND":
            break
    if prof != 8 or entrel:
        raise ValueError("use PNG de 8 bits por canal, sem entrelaçamento (%s)" % caminho)
    canais = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[cor]
    bruto = zlib.decompress(idat)
    passo = w * canais
    saida = bytearray()
    ant = bytearray(passo)
    pos = 0
    for _ in range(h):
        filtro = bruto[pos]
        linha = bytearray(bruto[pos + 1:pos + 1 + passo])
        pos += 1 + passo
        for i in range(passo):
            a = linha[i - canais] if i >= canais else 0
            b = ant[i]
            c = ant[i - canais] if i >= canais else 0
            if filtro == 1:
                linha[i] = (linha[i] + a) & 255
            elif filtro == 2:
                linha[i] = (linha[i] + b) & 255
            elif filtro == 3:
                linha[i] = (linha[i] + ((a + b) >> 1)) & 255
            elif filtro == 4:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                linha[i] = (linha[i] + pr) & 255
        saida += linha
        ant = linha
    rgba = bytearray()
    for i in range(w * h):
        px = saida[i * canais:(i + 1) * canais]
        if cor == 6:
            rgba += px
        elif cor == 2:
            rgba += px + b"\xff"
        elif cor == 0:
            rgba += bytes((px[0], px[0], px[0], 255))
        elif cor == 4:
            rgba += bytes((px[0], px[0], px[0], px[1]))
        elif cor == 3:
            k = px[0]
            al = trns[k] if trns and k < len(trns) else 255
            rgba += plte[k * 3:k * 3 + 3] + bytes((al,))
    return w, h, bytes(rgba)


# ----------------------------------------------------------------------
# Swizzle do PSP (blocos de 16 bytes x 8 linhas)
# ----------------------------------------------------------------------

def desembaralhar(px, larg_bytes, h):
    out = bytearray(len(px))
    i = 0
    for by in range(h // 8):
        for bx in range(larg_bytes // 16):
            for r in range(8):
                o = (by * 8 + r) * larg_bytes + bx * 16
                out[o:o + 16] = px[i:i + 16]
                i += 16
    return bytes(out)


def embaralhar(px, larg_bytes, h):
    out = bytearray(len(px))
    i = 0
    for by in range(h // 8):
        for bx in range(larg_bytes // 16):
            for r in range(8):
                o = (by * 8 + r) * larg_bytes + bx * 16
                out[i:i + 16] = px[o:o + 16]
                i += 16
    return bytes(out)


# ----------------------------------------------------------------------
# Quantização para 256 cores (median cut)
# ----------------------------------------------------------------------

def quantizar(cores_px, max_cores=256):
    """cores_px: lista de tuplas RGBA. Devolve (paleta, índices)."""
    unicas = {}
    for c in cores_px:
        unicas[c] = unicas.get(c, 0) + 1
    if len(unicas) <= max_cores:
        pal = list(unicas)
        idx = {c: i for i, c in enumerate(pal)}
        return pal, [idx[c] for c in cores_px]
    caixas = [list(unicas.items())]
    while len(caixas) < max_cores:
        caixas.sort(key=lambda cx: max(max(c[0][k] for c in cx) - min(c[0][k] for c in cx) for k in range(4))
                    if len(cx) > 1 else -1)
        cx = caixas.pop()
        if len(cx) < 2:
            caixas.append(cx)
            break
        k = max(range(4), key=lambda k: max(c[0][k] for c in cx) - min(c[0][k] for c in cx))
        cx.sort(key=lambda c: c[0][k])
        total = sum(c[1] for c in cx)
        acc, corte = 0, 1
        for j, c in enumerate(cx):
            acc += c[1]
            if acc >= total / 2:
                corte = max(1, min(len(cx) - 1, j + 1))
                break
        caixas.append(cx[:corte])
        caixas.append(cx[corte:])
    pal = []
    mapa = {}
    for cx in caixas:
        t = sum(c[1] for c in cx)
        media = tuple(int(round(sum(c[0][k] * c[1] for c in cx) / t)) for k in range(4))
        for c, _ in cx:
            mapa[c] = len(pal)
        pal.append(media)
    return pal, [mapa[c] for c in cores_px]


# ----------------------------------------------------------------------
# Contêiner spav
# ----------------------------------------------------------------------

def tabela(dados, base):
    n = struct.unpack_from("<I", dados, base + 8)[0]
    cab = struct.unpack_from("<I", dados, base + 0x1C)[0]
    t0 = base + 0x20 + struct.unpack_from("<I", dados, base + 0x2C)[0]
    tam_ent = struct.unpack_from("<I", dados, base + 0x30)[0] or 12
    ents = [struct.unpack_from("<III", dados, t0 + tam_ent * i) for i in range(n)]
    return cab, ents


def achar_texturas(dados, base=0, tamanho=None, prof=0):
    """Percorre o spav e devolve [(posição absoluta, tamanho, hash)] das texturas."""
    achadas = []
    if dados[base:base + 4] != MAGIC or prof > 6:
        return achadas
    tipo = struct.unpack_from("<I", dados, base + 0x14)[0]
    eh_container = struct.unpack_from("<H", dados, base + 0x0C)[0] == 8
    cab, ents = tabela(dados, base)
    if eh_container:
        for _, tam, off in ents:
            achadas += achar_texturas(dados, base + cab + off, tam, prof + 1)
    elif tipo == 0:
        for h, tam, off in ents:
            achadas.append((base + cab + off, tam & 0xFFFFFF, h))
    return achadas


def info_textura(dados, pos, tam):
    w, h = struct.unpack_from("<HH", dados, pos + 6)
    if tam == 128 + w * h + 1024:
        bpp = 8
    elif tam == 128 + w * h // 2 + 64:
        bpp = 4
    else:
        bpp = None
    # todas as texturas do jogo usam swizzle (com 16 bytes de largura ele não muda nada)
    larg_bytes = w if bpp == 8 else w // 2
    return w, h, bpp, larg_bytes >= 16 and h % 8 == 0


def decodificar(dados, pos, tam):
    w, h, bpp, sw = info_textura(dados, pos, tam)
    if bpp is None:
        return None
    if bpp == 8:
        px = dados[pos + 128:pos + 128 + w * h]
        pal = dados[pos + 128 + w * h:pos + 128 + w * h + 1024]
        if sw:
            px = desembaralhar(px, w, h)
        idx = px
    else:
        px = dados[pos + 128:pos + 128 + w * h // 2]
        pal = dados[pos + 128 + w * h // 2:pos + 128 + w * h // 2 + 64]
        if sw:
            px = desembaralhar(px, w // 2, h)
        idx = bytearray()
        for b in px:
            idx += bytes((b & 15, b >> 4))
    rgba = b"".join(pal[i * 4:i * 4 + 4] for i in idx)
    return w, h, rgba


def codificar(w, h, rgba, bpp, sw, pal_original):
    cores = [tuple(rgba[i * 4:i * 4 + 4]) for i in range(w * h)]
    maxc = 256 if bpp == 8 else 16
    # se todas as cores existem na paleta original, reaproveita (fica idêntico)
    origem = [tuple(pal_original[i * 4:i * 4 + 4]) for i in range(maxc)]
    mapa = {}
    for i, c in enumerate(origem):
        mapa.setdefault(c, i)
    if all(c in mapa for c in set(cores)):
        pal, idx = origem, [mapa[c] for c in cores]
    else:
        pal, idx = quantizar(cores, maxc)
        pal = pal + [(0, 0, 0, 0)] * (maxc - len(pal))
    if bpp == 8:
        px = bytes(idx)
        if sw:
            px = embaralhar(px, w, h)
    else:
        px = bytes((idx[i] & 15) | ((idx[i + 1] & 15) << 4) for i in range(0, len(idx), 2))
        if sw:
            px = embaralhar(px, w // 2, h)
    return px + b"".join(bytes(c) for c in pal)


# ----------------------------------------------------------------------
# Comandos
# ----------------------------------------------------------------------

def abrir(caminho):
    dados = open(caminho, "rb").read()
    if dados[:4] != MAGIC:
        sys.exit("Erro: %s não é um arquivo spav" % caminho)
    return dados


def nome_png(h):
    return "%08x.png" % h


def cmd_listar(arq):
    dados = abrir(arq)
    tex = achar_texturas(dados)
    print("%d texturas em %s" % (len(tex), arq))
    for pos, tam, h in tex:
        w, hh, bpp, sw = info_textura(dados, pos, tam)
        print("  %s  %4dx%-4d  %s bits  %s" % (nome_png(h), w, hh, bpp or "?", "swizzle" if sw else ""))


def cmd_exportar(arq, pasta):
    dados = abrir(arq)
    os.makedirs(pasta, exist_ok=True)
    n = 0
    for pos, tam, h in achar_texturas(dados):
        r = decodificar(dados, pos, tam)
        if not r:
            print("  pulei %s (formato ainda não suportado)" % nome_png(h))
            continue
        png_salvar(os.path.join(pasta, nome_png(h)), *r)
        n += 1
    print("%d texturas exportadas para %s" % (n, pasta))


def cmd_importar(arq, pasta, destino):
    dados = bytearray(abrir(arq))
    trocadas = 0
    for pos, tam, h in achar_texturas(bytes(dados)):
        caminho = os.path.join(pasta, nome_png(h))
        if not os.path.exists(caminho):
            continue
        w, hh, bpp, sw = info_textura(dados, pos, tam)
        if bpp is None:
            continue
        atual = decodificar(bytes(dados), pos, tam)
        pw, ph, rgba = png_ler(caminho)
        if (pw, ph) != (w, hh):
            sys.exit("Erro: %s tem %dx%d, mas precisa ter %dx%d" % (caminho, pw, ph, w, hh))
        if rgba == atual[2]:
            continue  # não mudou
        npx = w * hh if bpp == 8 else w * hh // 2
        pal_orig = dados[pos + 128 + npx:pos + 128 + npx + (1024 if bpp == 8 else 64)]
        novo = codificar(w, hh, rgba, bpp, sw, pal_orig)
        dados[pos + 128:pos + 128 + len(novo)] = novo
        trocadas += 1
        print("  trocada: %s" % nome_png(h))
    with open(destino, "wb") as f:
        f.write(dados)
    print("%s criado. %d texturas trocadas." % (destino, trocadas))


def main():
    a = sys.argv[1:]
    try:
        if len(a) == 2 and a[0] == "listar":
            cmd_listar(a[1])
        elif len(a) == 3 and a[0] == "exportar":
            cmd_exportar(a[1], a[2])
        elif len(a) == 4 and a[0] == "importar":
            cmd_importar(a[1], a[2], a[3])
        else:
            print(__doc__)
            sys.exit(1)
    except (OSError, ValueError) as e:
        sys.exit("Erro: %s" % e)


if __name__ == "__main__":
    main()
