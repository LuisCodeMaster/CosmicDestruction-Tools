#!/usr/bin/env python3
"""
trocar_nome - troca um nome (de alien, golpe, personagem...) em toda a tradução do
Ben 10 Ultimate Alien: Cosmic Destruction e gera a ISO traduzida de novo.

Uso (na pasta do mod, onde ficam o traducao_pt.txt e as ISOs):
    python ferramentas/trocar_nome.py                        acha a ISO da pasta (pergunta se houver várias)
    python ferramentas/trocar_nome.py "jogo (Mod).iso"       usa essa ISO como base
    python ferramentas/trocar_nome.py "base.iso" "saida.iso" escolhe também o nome da ISO gerada
A ISO gerada leva " PT-BR" no nome (ex.: "jogo (Mod) PT-BR.iso").

O programa pergunta o nome atual e o nome novo, mostra onde ele aparece, guarda uma cópia
do arquivo antes de mudar (traducao_pt_backup.txt), troca a forma normal e a em maiúsculas
(Friagem/FRIAGEM), coloca a tradução no psp_us.txt e gera a ISO.

Só usa a biblioteca padrão do Python 3.8+.
"""
import glob
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TRADUCAO = "traducao_pt.txt"
BACKUP = "traducao_pt_backup.txt"
PASTA_SAIDA = os.path.join("traducao", "global", "scripts")
ORIGINAIS = [
    "cd_trabalho/extraido/PSP_GAME/USRDIR/global/scripts/psp_us.txt",
    "cd_trabalho/extraido/psp_game/usrdir/global/scripts/psp_us.txt",
]


def perguntar(texto):
    try:
        return input(texto).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit("Cancelado.")


def ler():
    with open(TRADUCAO, encoding="utf-8") as f:
        return f.read().split("\n")


def salvar(linhas):
    with open(TRADUCAO, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(linhas))


def padrao(nome):
    # só a palavra inteira: trocar "Eco" não mexe em "Ecoar"
    return re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(nome))


def ocorrencias(linhas, nome):
    p = padrao(nome)
    achadas = []
    for i, l in enumerate(linhas):
        if l.startswith("#") or "|" not in l:
            continue
        texto = l.split("|", 1)[1]
        n = len(p.findall(texto))
        if n:
            achadas.append((i, n))
    return achadas


def trocar(linhas, velho, novo):
    p = padrao(velho)
    total = 0
    for i, l in enumerate(linhas):
        if l.startswith("#") or "|" not in l:
            continue
        h, texto = l.split("|", 1)
        novo_texto, n = p.subn(lambda m: novo, texto)
        if n:
            linhas[i] = h + "|" + novo_texto
            total += n
    return total


def escolher_iso(args):
    """A ISO pode vir no comando; senão, procura as .iso/.cso da pasta (e pergunta se houver várias)."""
    if args:
        base = args[0]
        if not os.path.isfile(base):
            sys.exit("Não achei o arquivo %s." % base)
    else:
        isos = sorted(f for f in set(glob.glob("*.iso") + glob.glob("*.ISO") + glob.glob("*.cso") + glob.glob("*.CSO"))
                      if "pt-br" not in f.lower())
        if not isos:
            return None, None
        if len(isos) == 1:
            base = isos[0]
        else:
            print("Qual ISO usar como base? (a ISO com o mod, se você tiver)")
            for i, f in enumerate(isos, 1):
                print("  %d) %s" % (i, f))
            while True:
                r = perguntar("Número: ")
                if r.isdigit() and 1 <= int(r) <= len(isos):
                    base = isos[int(r) - 1]
                    break
    saida = args[1] if len(args) > 1 else os.path.splitext(base)[0] + " PT-BR.iso"
    return base, saida


def main():
    print("=== Trocar um nome na tradução do Cosmic Destruction ===\n")
    if not os.path.exists(TRADUCAO):
        sys.exit("Não achei o %s nesta pasta. Rode o programa de dentro da pasta do mod:\n"
                 '    cd "/sdcard/Ben 10 Mod"' % TRADUCAO)
    original = next((o for o in ORIGINAIS if os.path.exists(o)), None)
    if not original:
        sys.exit("Não achei o psp_us.txt original em cd_trabalho/extraido. Rode antes o cd_kit.py\n"
                 "ou extraia com o cd_analisador.py (--so \"*psp_us.txt\").")
    base, saida = escolher_iso(sys.argv[1:])
    if not base:
        sys.exit("Não achei nenhuma .iso nesta pasta. Rode assim:\n"
                 '    python trocar_nome.py "nome da ISO.iso"')
    print("ISO base: %s\nISO que vai ser gerada: %s" % (base, saida))

    linhas = ler()
    trocas = []
    while True:
        print()
        velho = perguntar("Qual o nome atual? (Enter vazio para terminar): ")
        if not velho:
            break
        formas = [velho] + ([velho.upper()] if velho.upper() != velho else [])
        achou = {f: ocorrencias(linhas, f) for f in formas}
        total = sum(n for f in formas for _, n in achou[f])
        if not total:
            print("  '%s' não aparece na tradução. Confira maiúsculas e acentos." % velho)
            continue
        for f in formas:
            if achou[f]:
                print("  '%s' aparece %d vez(es). Exemplo:" % (f, sum(n for _, n in achou[f])))
                i = achou[f][0][0]
                print("    " + linhas[i].split("|", 1)[1][:110])
        novo = perguntar("Qual o nome novo? ")
        if not novo:
            print("  Nada mudou.")
            continue
        try:
            novo.encode("latin-1")
        except UnicodeEncodeError:
            print("  O nome tem uma letra que a fonte do jogo não mostra. Use só letras e acentos comuns.")
            continue
        if perguntar("  Trocar '%s' por '%s'? (s/n): " % (velho, novo)).lower() not in ("s", "sim"):
            print("  Nada mudou.")
            continue
        if not trocas:
            shutil.copyfile(TRADUCAO, BACKUP)
            print("  Cópia de segurança salva em %s" % BACKUP)
        n = trocar(linhas, velho, novo)
        if velho.upper() != velho:
            n += trocar(linhas, velho.upper(), novo.upper())
        salvar(linhas)
        trocas.append((velho, novo, n))
        print("  Pronto: %d troca(s)." % n)

    if not trocas:
        print("Nenhuma troca feita. A ISO não foi gerada de novo.")
        return

    print("\nTrocas feitas:")
    for v, n_, q in trocas:
        print("  %s -> %s (%d)" % (v, n_, q))
    print("\nColocando a tradução no jogo...")
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(AQUI, "cd_tool.py"), "texto-importar",
                        original, TRADUCAO, os.path.join(PASTA_SAIDA, "psp_us.txt")])
    if r.returncode:
        sys.exit("Deu erro ao colocar a tradução. Para voltar ao arquivo de antes:\n    cp %s %s"
                 % (BACKUP, TRADUCAO))
    print("\nGerando a ISO (%s)..." % saida)
    r = subprocess.run([sys.executable, os.path.join(AQUI, "cd_iso.py"), base, saida, "traducao"])
    if r.returncode:
        sys.exit("Deu erro ao gerar a ISO.")
    print("\nTudo pronto! Abra no PPSSPP: %s" % saida)
    print("Se não gostar, volte ao arquivo de antes com:  cp %s %s" % (BACKUP, TRADUCAO))


if __name__ == "__main__":
    main()
