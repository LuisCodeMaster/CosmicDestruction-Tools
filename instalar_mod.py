#!/usr/bin/env python3
"""
instalar_mod - Instalador automático do mod "Ultimate a qualquer momento"
Ben 10 Ultimate Alien: Cosmic Destruction (PSP, ULUS-10542)

USO
  python instalar_mod.py                      procura a ISO/CSO na pasta atual
  python instalar_mod.py jogo.iso             usa essa ISO (ou .cso)
  python instalar_mod.py jogo.iso saida.iso   escolhe o nome da ISO nova

  Opção: --sem-rede  desliga a rede de segurança contra quedas.

O programa faz tudo sozinho:
  1. confere se a ISO é o Cosmic Destruction americano (ULUS-10542);
  2. copia a ISO (ou descomprime o CSO) para uma ISO nova;
  3. lê o globals.ds de dentro dela e aplica o mod;
  4. coloca o globals.ds modificado na ISO nova e confere o resultado.

A sua ISO original nunca é alterada. Precisa ficar na mesma pasta que
cd_scripts.py e cd_iso.py. Só usa a biblioteca padrão do Python 3.8+.
"""
import glob
import os
import shutil
import struct
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
try:
    import cd_iso
    import cd_scripts
except ImportError as e:
    sys.exit("Erro: coloque instalar_mod.py na mesma pasta que cd_scripts.py e cd_iso.py (%s)" % e)

SETOR = cd_iso.SETOR
CODIGO_JOGO = b"ULUS10542"
GLOBALS = "psp_game/usrdir/global/scripts/globals.ds"
SUFIXO = " (Ultimate Mod)"


def pausa():
    # no Windows, aberto com duplo clique, a janela não fecha antes de dar para ler
    if os.name == "nt" and not os.environ.get("PROMPT"):
        try:
            input("\nAperte Enter para fechar...")
        except EOFError:
            pass


def erro(msg):
    print("\nErro: " + msg)
    pausa()
    sys.exit(1)


def escolher_iso():
    achadas = sorted(p for p in glob.glob("*.iso") + glob.glob("*.cso") + glob.glob("*.ISO") + glob.glob("*.CSO")
                     if SUFIXO not in p)
    achadas = list(dict.fromkeys(achadas))
    if not achadas:
        erro("nenhuma .iso ou .cso nesta pasta (%s).\nRode o programa na pasta do jogo ou passe o "
             "caminho: python instalar_mod.py \"jogo.iso\"" % os.getcwd())
    if len(achadas) == 1:
        return achadas[0]
    print("Achei mais de um jogo nesta pasta:")
    for i, p in enumerate(achadas, 1):
        print("  %d) %s" % (i, p))
    while True:
        try:
            r = input("Qual é o Cosmic Destruction? (número): ").strip()
        except EOFError:
            erro("escolha cancelada")
        if r.isdigit() and 1 <= int(r) <= len(achadas):
            return achadas[int(r) - 1]


def ler_cso(caminho, ini, tam):
    """Lê 'tam' bytes a partir de 'ini' de um CSO, sem descomprimir tudo."""
    import zlib
    with open(caminho, "rb") as f:
        cab = f.read(24)
        _, _, total, bloco, _, align = struct.unpack("<4sIQIBB", cab[:22])
        nb = (total + bloco - 1) // bloco
        idx = struct.unpack("<%dI" % (nb + 1), f.read(4 * (nb + 1)))
        out = bytearray()
        b = ini // bloco
        while len(out) < (ini % bloco) + tam and b < nb:
            a, c = idx[b], idx[b + 1]
            f.seek((a & 0x7FFFFFFF) << align)
            d = f.read(((c & 0x7FFFFFFF) << align) - ((a & 0x7FFFFFFF) << align))
            out += (d if a & 0x80000000 else zlib.decompress(d, -15))[:bloco]
            b += 1
        return bytes(out[ini % bloco:ini % bloco + tam])


def conferir_jogo(caminho):
    with open(caminho, "rb") as f:
        cso = f.read(4) == b"CISO"
    if cso:
        cab = ler_cso(caminho, 0x8000, 0x800 * 2)
        if cab[1:6] != b"CD001":
            erro("o CSO não parece ser um jogo de PSP")
        inicio = ler_cso(caminho, 0, 0x90000)          # área do UMD_DATA.BIN / PARAM.SFO
        return CODIGO_JOGO in inicio
    with open(caminho, "rb") as f:
        f.seek(16 * SETOR)
        if f.read(6)[1:6] != b"CD001":
            erro("%s não é uma ISO de PSP válida" % caminho)
        arquivos = cd_iso.listar(f)
        for nome in ("umd_data.bin", "psp_game/param.sfo"):
            if nome in arquivos:
                _, lba, tam = arquivos[nome]
                f.seek(lba * SETOR)
                if CODIGO_JOGO in f.read(min(tam, 4096)):
                    return True
    return False


def trocar_arquivo(f, arquivos, chave, novo):
    """Mesmo método do cd_iso.py: no lugar se couber, senão no fim da ISO."""
    pos_reg, lba, tam = arquivos[chave]
    espaco = ((tam + SETOR - 1) // SETOR) * SETOR
    f.seek(0, 2)
    fim = f.tell()
    if len(novo) <= espaco:
        destino_lba = lba
    else:
        destino_lba = (fim + SETOR - 1) // SETOR
    f.seek(destino_lba * SETOR)
    f.write(novo)
    sobra = (-len(novo)) % SETOR
    if sobra:
        f.write(b"\0" * sobra)
    cd_iso.escrever_u32_ambos(f, pos_reg + 2, destino_lba)
    cd_iso.escrever_u32_ambos(f, pos_reg + 10, len(novo))
    f.seek(0, 2)
    cd_iso.escrever_u32_ambos(f, 16 * SETOR + 80, f.tell() // SETOR)
    return destino_lba != lba


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opc = [a for a in sys.argv[1:] if a.startswith("--")]
    if any(o in ("--ajuda", "--help", "-h") for o in opc):
        print(__doc__)
        return
    rede = "--sem-rede" not in opc

    print("=== Instalador do mod Ultimate a qualquer momento (Ben 10 Cosmic Destruction PSP) ===\n")
    origem = args[0] if args else escolher_iso()
    if not os.path.isfile(origem):
        erro("arquivo não encontrado: %s" % origem)
    base = os.path.splitext(origem)[0]
    destino = args[1] if len(args) > 1 else base + SUFIXO + ".iso"
    if os.path.abspath(origem) == os.path.abspath(destino):
        erro("a ISO nova precisa ter outro nome")
    print("Jogo:       %s" % origem)
    print("ISO nova:   %s\n" % destino)

    print("[1/4] Conferindo o jogo...")
    if not conferir_jogo(origem):
        erro("esta não parece ser a versão americana (ULUS-10542) do Cosmic Destruction.\n"
             "O mod só foi feito e testado para ela.")
    print("      ULUS-10542 encontrado.")

    tam = os.path.getsize(origem)
    with open(origem, "rb") as f:
        if f.read(4) == b"CISO":
            f.seek(8)
            tam = struct.unpack("<Q", f.read(8))[0]
    livre = shutil.disk_usage(os.path.dirname(os.path.abspath(destino))).free
    if livre < tam + 64 * 1024 * 1024:
        erro("pouco espaço livre: precisa de uns %d MB e tem %d MB" % (tam >> 20, livre >> 20))

    print("[2/4] Criando a ISO nova (pode levar alguns minutos)...")
    cd_iso.copiar_para_iso(origem, destino)

    try:
        with open(destino, "r+b") as f:
            arquivos = cd_iso.listar(f)
            if GLOBALS not in arquivos:
                raise ValueError("globals.ds não encontrado dentro da ISO")
            _, lba, t = arquivos[GLOBALS]
            f.seek(lba * SETOR)
            original = f.read(t)

            print("[3/4] Aplicando o mod no globals.ds...")
            with tempfile.TemporaryDirectory() as tmp:
                a, b = os.path.join(tmp, "globals.ds"), os.path.join(tmp, "globals_mod.ds")
                with open(a, "wb") as fo:
                    fo.write(original)
                cd_scripts.cmd_ultimate_livre(a, b, rede=rede)
                with open(b, "rb") as fi:
                    novo = fi.read()

            print("[4/4] Colocando o script na ISO nova...")
            trocar_arquivo(f, arquivos, GLOBALS, novo)

            # conferência final: o índice da ISO aponta para o script novo e ele é válido
            arquivos = cd_iso.listar(f)
            _, lba, t = arquivos[GLOBALS]
            f.seek(lba * SETOR)
            lido = f.read(t)
            if lido != novo:
                raise ValueError("a conferência do script dentro da ISO falhou")
            cd_scripts.ler(lido)
    except (ValueError, OSError, struct.error) as e:
        try:
            os.remove(destino)
        except OSError:
            pass
        erro(str(e))

    print("\nPronto! Abra no PPSSPP: %s" % destino)
    print("Dica: carregue o save do próprio jogo, não um save state do PPSSPP.")
    if not rede:
        print("(rede de segurança contra quedas desligada)")
    pausa()


if __name__ == "__main__":
    main()
