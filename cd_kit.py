#!/usr/bin/env python3
"""
cd_kit - menu do kit de modding do Ben 10 Ultimate Alien: Cosmic Destruction (PSP, ULUS-10542)

Junta todas as ferramentas num menu: você escolhe o que quer no mod e o kit
extrai da SUA ISO só os arquivos necessários, monta tudo e gera a ISO nova.

USO
  python cd_kit.py                 abre o menu (acha a ISO/CSO na pasta)
  python cd_kit.py jogo.iso        abre o menu com essa ISO
  python cd_kit.py jogo.iso --tudo monta direto com todas as opções ligadas

Precisa, na mesma pasta: cd_analisador.py, cd_iso.py, cd_scripts.py, cd_anims.py, cd_vozes.py
A ISO original nunca é alterada. Arquivos de trabalho ficam em cd_trabalho/.
"""
import glob
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TRABALHO = "cd_trabalho"
EXTRAIDO = os.path.join(TRABALHO, "extraido")
MOD = os.path.join(TRABALHO, "mod")
USRDIR = os.path.join(EXTRAIDO, "PSP_GAME", "USRDIR")
FERRAMENTAS = ["cd_analisador.py", "cd_iso.py", "cd_scripts.py", "cd_anims.py", "cd_vozes.py"]

# o que cada opção precisa extrair da ISO
PADROES = [
    "*global/scripts/globals.ds",       # script principal (mod Ultimate)
    "*global/scripts/gld_psp.ds",       # botões do PSP (usado pelos testes do simulador)
    "*global/g_*.psp",                  # pacotes dos aliens e das Ultimates
    "*l_tokd/g_wayb.psp",               # modelo do Gigante
    "*l_tokd/l_tokd.psp",               # esqueletos do Gigante e do Ben
    "*l_tokd/scripts/atk_wb.ddf",
    "*global/a_plyr.psp",               # animações do Ben
    "*global/scripts/atk_*.ddf",        # golpes
    "*vo/vo_eng.psp",                   # bancos de voz das fases
    "*scripts/vo_*.ds",                 # scripts de voz das fases
]

OPCOES = [  # (chave, nome no menu, ligada por padrão)
    ("ultimate", "Ultimate a qualquer momento (SELECT)", True),
    ("interacoes", "Ultimates interagindo com o cenário (caixas, beiradas...)", True),
    ("intro", "Animação de transformação na 1ª Ultimate de cada fase", True),
    ("vozes", "Ultimates gritando o nome em todas as fases", True),
    ("gigante", "Tartagira + SELECT vira o Gigante (experimental)", False),
    ("ben", "Ben com os golpes do Gigante (R = roda de especiais, R + SELECT = Ben gigante)", False),
]


def rodar(*args):
    cmd = [sys.executable, os.path.join(AQUI, args[0])] + list(args[1:])
    print("  > " + " ".join(os.path.basename(a) if i == 0 else a for i, a in enumerate(cmd[1:])))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("\nErro no passo acima (%s). Nada foi colocado na ISO." % args[0])


def achar_iso(args):
    if args:
        return args[0]
    isos = sorted(set(glob.glob("*.iso") + glob.glob("*.cso") + glob.glob("*.ISO") + glob.glob("*.CSO")))
    isos = [i for i in isos if "(Mod" not in i]
    if not isos:
        raise SystemExit("Nenhuma .iso/.cso nesta pasta. Use: python cd_kit.py \"jogo.iso\"")
    if len(isos) == 1:
        return isos[0]
    for i, p in enumerate(isos, 1):
        print("  %d) %s" % (i, p))
    while True:
        r = input("Qual é o Cosmic Destruction? ").strip()
        if r.isdigit() and 1 <= int(r) <= len(isos):
            return isos[int(r) - 1]


def menu(escolha):
    while True:
        print("\n=== O que vai no mod? ===")
        for i, (k, nome, _) in enumerate(OPCOES, 1):
            print("  %d) [%s] %s" % (i, "x" if escolha[k] else " ", nome))
        print("  M) montar a ISO   L) limpar arquivos de trabalho   S) sair")
        r = input("Número para ligar/desligar, ou M/L/S: ").strip().upper()
        if r == "M":
            return True
        if r == "S":
            return False
        if r == "L":
            shutil.rmtree(TRABALHO, ignore_errors=True)
            print("  cd_trabalho/ apagado (será extraído de novo).")
        elif r.isdigit() and 1 <= int(r) <= len(OPCOES):
            k = OPCOES[int(r) - 1][0]
            escolha[k] = not escolha[k]
            if k in ("gigante", "ben", "intro", "interacoes") and escolha[k]:
                escolha["ultimate"] = True          # essas dependem do script do mod


def extrair(iso):
    if os.path.exists(os.path.join(USRDIR, "global", "scripts", "globals.ds")):
        print("[1] Arquivos do jogo já extraídos (L no menu para extrair de novo).")
        return
    print("[1] Extraindo da ISO só o que o mod usa...")
    rodar("cd_analisador.py", iso, "--extrair", EXTRAIDO, "--so", *PADROES)
    minusculas(EXTRAIDO)


def minusculas(raiz):
    """Algumas ISOs guardam os nomes em MAIÚSCULAS; as ferramentas usam minúsculas."""
    for pasta, dirs, arqs in os.walk(raiz, topdown=False):
        for n in arqs + dirs:
            if n != n.lower() and not (n.startswith("PSP_GAME") or n == "USRDIR"):
                os.rename(os.path.join(pasta, n), os.path.join(pasta, n.lower()))
    for n in ("psp_game", "usrdir"):           # a raiz fica PSP_GAME/USRDIR, como sempre
        for pasta, dirs, _ in os.walk(raiz):
            for d in dirs:
                if d == n:
                    os.rename(os.path.join(pasta, d), os.path.join(pasta, d.upper()))


def montar(iso, escolha, destino):
    shutil.rmtree(MOD, ignore_errors=True)
    glob_mod = os.path.join(MOD, "global")
    os.makedirs(os.path.join(glob_mod, "scripts"), exist_ok=True)
    g = os.path.join(USRDIR, "global")
    tokd = os.path.join(USRDIR, "l_tokd")
    passo = 2
    if escolha["interacoes"]:
        print("[%d] Animações de interação nas Ultimates..." % passo); passo += 1
        rodar("cd_anims.py", "--pasta", g, "--saida", glob_mod)
    if escolha["gigante"]:
        print("[%d] Pacote completo do Gigante..." % passo); passo += 1
        rodar("cd_anims.py", "--gigante", tokd, g, "--saida", glob_mod)
    if escolha["ben"]:
        print("[%d] Ben com os golpes do Gigante..." % passo); passo += 1
        rodar("cd_anims.py", "--ben-gigante", os.path.join(g, "a_plyr.psp"), tokd, g, "--saida", MOD)
    if escolha["ultimate"]:
        print("[%d] Script do mod (globals.ds)..." % passo); passo += 1
        opc = []
        if escolha["gigante"]:
            opc.append("--gigante")
        if escolha["ben"]:
            opc.append("--ben-gigante")
        if not escolha["intro"]:
            opc.append("--sem-intro")
        rodar("cd_scripts.py", "ultimate-livre", os.path.join(g, "scripts", "globals.ds"),
              os.path.join(glob_mod, "scripts", "globals.ds"), *opc)
    if escolha["vozes"]:
        print("[%d] Gritos das Ultimates nas fases..." % passo); passo += 1
        rodar("cd_vozes.py", EXTRAIDO, EXTRAIDO, MOD)
    n = sum(len(f) for _, _, f in os.walk(MOD))
    if not n:
        raise SystemExit("Nenhuma opção ligada: nada para colocar na ISO.")
    print("[%d] Montando a ISO nova (%d arquivos trocados)..." % (passo, n))
    rodar("cd_iso.py", iso, destino, MOD)
    print("\nPronto! Abra no PPSSPP: %s" % destino)
    print("(carregue o save do próprio jogo, não um save state)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    faltam = [f for f in FERRAMENTAS if not os.path.exists(os.path.join(AQUI, f))]
    if faltam:
        raise SystemExit("Faltam na pasta do kit: " + ", ".join(faltam))
    print(__doc__.split("USO")[0].strip())
    iso = achar_iso(args)
    if not os.path.isfile(iso):
        raise SystemExit("Arquivo não encontrado: " + iso)
    escolha = {k: padrao for k, _, padrao in OPCOES}
    if "--tudo" in sys.argv:
        escolha = {k: True for k in escolha}
    elif not menu(escolha):
        return
    destino = args[1] if len(args) > 1 else os.path.splitext(iso)[0] + " (Mod).iso"
    extrair(iso)
    montar(iso, escolha, destino)


if __name__ == "__main__":
    main()
