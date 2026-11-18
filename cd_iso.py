#!/usr/bin/env python3
"""
cd_iso - Kit de modding do Ben 10 Ultimate Alien: Cosmic Destruction (PSP)
Ferramenta 4: coloca arquivos modificados dentro da ISO

USO
  python cd_iso.py jogo.iso jogo_mod.iso pasta_mod

  A pasta_mod tem os arquivos modificados com o caminho de dentro do jogo, por exemplo:
      pasta_mod/global/g_hm.psp
      pasta_mod/global/scripts/atk_hm.ddf
  (pode começar em PSP_GAME/USRDIR/... ou só a parte final do caminho, desde que
   ela aponte para um arquivo só)

  A ISO original não é alterada: o programa cria jogo_mod.iso.
  Aceita .iso ou .cso como entrada (a saída é sempre .iso).

  Arquivo do mesmo tamanho ou menor: substitui no lugar.
  Arquivo maior: vai para o fim da ISO e o índice é atualizado.

Só usa a biblioteca padrão do Python 3.8+.
"""
import os
import shutil
import struct
import sys
import zlib

SETOR = 2048


def copiar_para_iso(origem, destino):
    with open(origem, "rb") as f:
        magic = f.read(4)
    if magic != b"CISO":
        print("Copiando a ISO (pode demorar um pouco)...")
        shutil.copyfile(origem, destino)
        return
    print("Descomprimindo o CSO para ISO (pode demorar)...")
    with open(origem, "rb") as f, open(destino, "wb") as out:
        cab = f.read(24)
        _, _, total, bloco, _, align = struct.unpack("<4sIQIBB", cab[:22])
        nb = (total + bloco - 1) // bloco
        idx = struct.unpack("<%dI" % (nb + 1), f.read(4 * (nb + 1)))
        for i in range(nb):
            a, b = idx[i], idx[i + 1]
            ini = (a & 0x7FFFFFFF) << align
            fim = (b & 0x7FFFFFFF) << align
            f.seek(ini)
            d = f.read(fim - ini)
            if not a & 0x80000000:
                d = zlib.decompress(d, -15)
            out.write(d[:bloco])
            if i % 20000 == 0:
                print("  %d%%" % (i * 100 // nb))


def listar(f):
    """Devolve {caminho_minusculo: (posição do registro no arquivo, lba, tamanho)}."""
    f.seek(16 * SETOR)
    pvd = f.read(SETOR)
    if pvd[1:6] != b"CD001":
        sys.exit("Erro: não é uma ISO válida")
    arquivos = {}

    def ler_dir(lba, tam, prefixo, prof=0):
        if prof > 32:
            return
        f.seek(lba * SETOR)
        dados = f.read(tam)
        pos = 0
        while pos < len(dados):
            n = dados[pos]
            if n == 0:
                pos = (pos // SETOR + 1) * SETOR
                continue
            reg = dados[pos:pos + n]
            elba = struct.unpack_from("<I", reg, 2)[0]
            etam = struct.unpack_from("<I", reg, 10)[0]
            flags = reg[25]
            nome = reg[33:33 + reg[32]]
            pos_reg = lba * SETOR + pos
            pos += n
            if nome in (b"\x00", b"\x01"):
                continue
            nome = nome.decode("ascii", "replace").split(";")[0]
            caminho = (prefixo + "/" + nome).lstrip("/")
            if flags & 2:
                ler_dir(elba, etam, caminho, prof + 1)
            else:
                arquivos[caminho.lower()] = (pos_reg, elba, etam)

    raiz = pvd[156:190]
    ler_dir(struct.unpack_from("<I", raiz, 2)[0], struct.unpack_from("<I", raiz, 10)[0], "")
    return arquivos


def achar(arquivos, rel):
    rel = rel.replace("\\", "/").lower().strip("/")
    if rel in arquivos:
        return rel
    candidatos = [c for c in arquivos if c.endswith("/" + rel)]
    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1:
        sys.exit("Erro: '%s' é ambíguo, existe em:\n  %s\nUse o caminho mais completo."
                 % (rel, "\n  ".join(candidatos)))
    return None


def escrever_u32_ambos(f, pos, valor):
    f.seek(pos)
    f.write(struct.pack("<I", valor) + struct.pack(">I", valor))


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    origem, destino, pasta = sys.argv[1:]
    if os.path.abspath(origem) == os.path.abspath(destino):
        sys.exit("Erro: a saída precisa ser um arquivo diferente da ISO original")
    if not os.path.isdir(pasta):
        sys.exit("Erro: pasta %s não existe" % pasta)

    mods = []
    for raiz, _, nomes in os.walk(pasta):
        for n in nomes:
            p = os.path.join(raiz, n)
            mods.append((os.path.relpath(p, pasta), p))
    if not mods:
        sys.exit("Erro: a pasta %s está vazia" % pasta)

    copiar_para_iso(origem, destino)
    with open(destino, "r+b") as f:
        arquivos = listar(f)
        f.seek(0, 2)
        fim = f.tell()
        trocados = 0
        for rel, p in sorted(mods):
            chave = achar(arquivos, rel)
            if not chave:
                print("  AVISO: %s não existe no jogo, ignorado" % rel)
                continue
            pos_reg, lba, tam = arquivos[chave]
            novo = open(p, "rb").read()
            espaco = ((tam + SETOR - 1) // SETOR) * SETOR
            if len(novo) <= espaco:
                destino_lba = lba
                onde = "no lugar"
            else:
                destino_lba = (fim + SETOR - 1) // SETOR
                fim = destino_lba * SETOR + ((len(novo) + SETOR - 1) // SETOR) * SETOR
                onde = "no fim da ISO"
            f.seek(destino_lba * SETOR)
            f.write(novo)
            sobra = (-len(novo)) % SETOR
            if sobra:
                f.write(b"\0" * sobra)
            escrever_u32_ambos(f, pos_reg + 2, destino_lba)
            escrever_u32_ambos(f, pos_reg + 10, len(novo))
            arquivos[chave] = (pos_reg, destino_lba, len(novo))
            trocados += 1
            print("  %s (%d bytes, %s)" % (chave, len(novo), onde))
        f.seek(0, 2)
        total_setores = f.tell() // SETOR
        escrever_u32_ambos(f, 16 * SETOR + 80, total_setores)
    print("\n%s criado com %d arquivos trocados." % (destino, trocados))


if __name__ == "__main__":
    try:
        main()
    except OSError as e:
        sys.exit("Erro: %s" % e)
