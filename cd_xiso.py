#!/usr/bin/env python3
"""
cd_xiso - lê a .iso de jogo de Xbox 360 (sistema de arquivos XDVDFS)

O cd_analisador.py lê ISOs de PSP (ISO 9660); o disco de Xbox usa outro formato.
Este programa lista e extrai os arquivos, e diz se os scripts .ds estão abertos.

Uso:
    python cd_xiso.py jogo.iso                              lista e gera xiso_lista.txt
    python cd_xiso.py jogo.iso --extrair pasta              extrai tudo
    python cd_xiso.py jogo.iso --extrair pasta --so "*.ds" "*.ddf" "*/scripts/*"
Depois de extrair, o cd_analisador.py funciona na pasta (python cd_analisador.py pasta).

Formato: setores de 2048 bytes; o descritor do volume ("MICROSOFT*XBOX*MEDIA") fica no setor 32
da partição do jogo, que começa em 0 (imagem já recortada) ou num destes deslocamentos do disco:
0x18300000 (XGD1), 0xFD90000 (XGD2), 0x2080000 (XGD3). Diretórios são árvores binárias de
registros: u16 esquerda, u16 direita (em palavras de 4 bytes), u32 setor, u32 tamanho, u8 atributos
(0x10 = pasta), u8 tamanho do nome, nome. Tudo little-endian.

Só usa a biblioteca padrão do Python 3.8+.
"""
import argparse
import fnmatch
import os
import struct
import sys
from collections import Counter

SETOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
PARTICOES = (0, 0xFD90000, 0x2080000, 0x18300000)


class Disco:
    def __init__(self, caminho):
        self.f = open(caminho, "rb")
        self.tamanho = os.path.getsize(caminho)
        for base in PARTICOES:
            self.f.seek(base + 32 * SETOR)
            if self.f.read(20) == MAGIC:
                self.base = base
                break
        else:
            raise SystemExit("Não achei o descritor do Xbox (%s) nessa ISO." % MAGIC.decode())
        self.f.seek(self.base + 32 * SETOR + 20)
        self.raiz, self.raiz_tam = struct.unpack("<II", self.f.read(8))

    def ler(self, setor, pos, n):
        self.f.seek(self.base + setor * SETOR + pos)
        return self.f.read(n)

    def pasta(self, setor, tam, prefixo=""):
        """Percorre a árvore de uma pasta; devolve (caminho, setor, tamanho, é_pasta)."""
        if tam == 0:
            return []
        dados = self.ler(setor, 0, tam)
        saida, pilha, vistos = [], [0], set()
        while pilha:
            o = pilha.pop()
            if o in vistos or o + 14 > len(dados):
                continue
            vistos.add(o)
            esq, dir_, s, t, atr, n = struct.unpack_from("<HHIIBB", dados, o)
            if esq == 0xFFFF:          # enchimento no fim do setor
                continue
            nome = dados[o + 14:o + 14 + n].decode("latin-1")
            caminho = prefixo + nome
            saida.append((caminho, s, t, bool(atr & 0x10)))
            if atr & 0x10:
                saida += self.pasta(s, t, caminho + "/")
            if esq:
                pilha.append(esq * 4)
            if dir_:
                pilha.append(dir_ * 4)
        return saida

    def arquivos(self):
        return [(c, s, t) for c, s, t, p in self.pasta(self.raiz, self.raiz_tam) if not p]

    def extrair(self, setor, tam, destino):
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        with open(destino, "wb") as out:
            pos = 0
            while pos < tam:
                n = min(4 << 20, tam - pos)
                out.write(self.ler(setor, pos, n))
                pos += n


def tipo(cab):
    tabela = {b"\xbe\xba\xad\x1b": "script/dados LE (como no PSP)", b"\x1b\xad\xba\xbe": "script/dados BE (como no PS3)",
              b"vaps": "pacote vaps (BE)", b"spav": "pacote spav (LE)", b"FSB4": "sons FSB4", b"FEV1": "eventos FMOD",
              b"BIKi": "vídeo Bink", b"XEX2": "executável XEX2", b"NPD\0": "criptografado (NPD/sdat)"}
    return tabela.get(cab[:4], "outro (%s)" % cab[:4].hex(" "))


def main():
    ap = argparse.ArgumentParser(description="Lê a .iso de Xbox 360 (XDVDFS).")
    ap.add_argument("iso")
    ap.add_argument("--extrair", metavar="PASTA")
    ap.add_argument("--so", nargs="+", metavar="PADRAO")
    a = ap.parse_args()

    d = Disco(a.iso)
    print("Partição do jogo em 0x%X. Lendo os diretórios..." % d.base)
    arqs = d.arquivos()
    total = sum(t for _, _, t in arqs)
    print("%d arquivos, %.1f GB." % (len(arqs), total / 1e9))

    linhas, tipos, ext = [], Counter(), Counter()
    scripts = {}
    for c, s, t in sorted(arqs):
        tp = tipo(d.ler(s, 0, 16)) if t else "vazio"
        tipos[tp] += 1
        ext[c.rsplit(".", 1)[-1].lower() if "." in c.rsplit("/", 1)[-1] else "(sem)"] += 1
        linhas.append("%12d  %-36s %s" % (t, tp, c))
        if c.lower().endswith(("globals.ds", "gld_x360.ds", "gld_xbox.ds", "frontend.ds", "globals.ds.sdat")):
            scripts[c] = tp
    with open("xiso_lista.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")

    print("\nPor tipo (assinatura):")
    for k, v in tipos.most_common():
        print("  %-36s %d" % (k, v))
    print("Por extensão:", ", ".join("%s %d" % kv for kv in ext.most_common(15)))
    print("\nScripts principais:")
    for c, tp in sorted(scripts.items()):
        print("  %-50s %s" % (c, tp))
    if not scripts:
        print("  nenhum globals.ds/frontend.ds com esse nome (veja xiso_lista.txt)")
    print("\nLista completa em xiso_lista.txt")

    if a.extrair:
        feitos = 0
        for c, s, t in arqs:
            if a.so and not any(fnmatch.fnmatch(c.lower(), p.lower()) for p in a.so):
                continue
            d.extrair(s, t, os.path.join(a.extrair, *c.split("/")))
            feitos += 1
        print("%d arquivos extraídos em %s" % (feitos, a.extrair))


if __name__ == "__main__":
    main()
