#!/usr/bin/env python3
"""
cd_kit360 - menu do kit de modding do Ben 10 Ultimate Alien: Cosmic Destruction (Xbox 360)

Igual ao cd_kit.py do PSP: você escolhe o que quer no mod e o kit monta tudo.
No 360 o jogo roda a partir da PASTA extraída (no Xenia, abra o default.xex dela),
então o kit aplica o mod direto nessa pasta e guarda os originais à parte.

USO
  python cd_kit360.py jogo.iso PASTA_DO_JOGO
      jogo.iso       a sua ISO do 360 (de onde saem os arquivos ORIGINAIS)
      PASTA_DO_JOGO  a pasta extraída (com o default.xex). Se ainda não existir,
                     o kit oferece extrair a ISO inteira para ela.

Toda vez que você aplica, o kit parte dos arquivos ORIGINAIS da ISO (guardados em
cd_trabalho360/originais), então pode ligar e desligar opções à vontade.
A opção "Restaurar" devolve a pasta do jogo ao original.

Precisa, na mesma pasta: cd_xiso.py, cd_scripts.py, cd_ps3.py, cd_tool.py, cd_vozes.py
e, para a tradução, o traducao_x360_pt.txt (na pasta onde você roda o kit ou na do kit).
Só usa a biblioteca padrão do Python 3.8+.
"""
import fnmatch
import glob
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

TRABALHO = "cd_trabalho360"
ORIGINAIS = os.path.join(TRABALHO, "originais")
ESCOLHAS = os.path.join(TRABALHO, "escolhas.txt")
TRADUCAO = "traducao_x360_pt.txt"
FERRAMENTAS = ["cd_xiso.py", "cd_scripts.py", "cd_ps3.py", "cd_tool.py", "cd_vozes.py"]

# arquivos que o kit pode mudar (sempre refeitos a partir do original)
GERENCIADOS = [
    "global/scripts/globals.ds",      # mod Ultimate
    "global/scripts/xbx_us.txt",      # textos (tradução)
    "global/scripts/sounds.ddf",      # lista das vozes (gritos)
    "*/vo/vo_eng.xbx",                # bancos de voz das fases (gritos)
    "*/scripts/vo_*.ds",              # scripts de voz das fases (gritos)
]

OPCOES = [  # (chave, nome no menu, ligada por padrão, situação)
    ("traducao", "Jogo em português", True, "testado: funciona"),
    ("ultimate", "Ultimate a qualquer momento (R3)", True, "em teste: às vezes se desfaz"),
    ("habilidades", "Ultimates com as habilidades do alien normal (caixa, teia, planar)", False,
     "não testado no 360 (precisa da Ultimate ligada)"),
    ("vozes", "Ultimates gritando o nome em todas as fases", False,
     "EXPERIMENTAL: travou em Roma no último teste"),
]


def gerenciado(caminho):
    c = caminho.replace("\\", "/").lower()
    return any(fnmatch.fnmatch(c, p) for p in GERENCIADOS)


def rodar(*args):
    cmd = [sys.executable, os.path.join(AQUI, args[0])] + [str(a) for a in args[1:]]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("Erro ao rodar %s (veja a mensagem acima)." % args[0])


def conferir_ferramentas():
    falta = [f for f in FERRAMENTAS if not os.path.exists(os.path.join(AQUI, f))]
    if falta:
        raise SystemExit("Faltam na pasta do kit: %s" % ", ".join(falta))


def lista_originais():
    saida = []
    for raiz, _, arqs in os.walk(ORIGINAIS):
        for a in arqs:
            p = os.path.join(raiz, a)
            saida.append(os.path.relpath(p, ORIGINAIS).replace("\\", "/"))
    return sorted(saida)


def preparar(iso, pasta):
    """Extrai da ISO os originais (uma vez) e, se preciso, o jogo inteiro na pasta."""
    import cd_xiso
    precisa_orig = not os.path.exists(os.path.join(ORIGINAIS, "global", "scripts", "globals.ds"))
    precisa_jogo = not os.path.exists(os.path.join(pasta, "default.xex"))
    if not (precisa_orig or precisa_jogo):
        return
    if not iso or not os.path.exists(iso):
        raise SystemExit("Preciso da ISO do 360 para pegar os arquivos originais.")
    d = cd_xiso.Disco(iso)
    print("Lendo a ISO (partição em 0x%X)..." % d.base)
    arqs = d.arquivos()
    if precisa_orig:
        n = 0
        for c, s, t in arqs:
            if gerenciado(c):
                d.extrair(s, t, os.path.join(ORIGINAIS, *c.split("/")))
                n += 1
        print("  %d arquivos originais guardados em %s" % (n, ORIGINAIS))
    if precisa_jogo:
        total = sum(t for _, _, t in arqs) / 1e9
        r = input("A pasta %s não tem o default.xex. Extrair a ISO inteira para ela (%.1f GB)? [s/n] "
                  % (pasta, total)).strip().lower()
        if r != "s":
            raise SystemExit("Sem a pasta do jogo não dá para aplicar.")
        for i, (c, s, t) in enumerate(arqs):
            d.extrair(s, t, os.path.join(pasta, *c.split("/")))
            if i % 100 == 0:
                print("  %d/%d arquivos..." % (i, len(arqs)))
        print("  jogo extraído em %s" % pasta)


def restaurar(pasta):
    for r in lista_originais():
        shutil.copyfile(os.path.join(ORIGINAIS, *r.split("/")), os.path.join(pasta, *r.split("/")))
    print("  pasta do jogo com os %d arquivos originais" % len(lista_originais()))


def achar_traducao():
    for p in (os.path.join(os.getcwd(), TRADUCAO), os.path.join(AQUI, TRADUCAO)):
        if os.path.exists(p):
            return p
    return None


def aplicar(pasta, ligadas):
    print("\n1) Voltando os arquivos do kit ao original...")
    restaurar(pasta)
    orig = lambda *p: os.path.join(ORIGINAIS, *p)
    jogo = lambda *p: os.path.join(pasta, *p)
    if "traducao" in ligadas:
        print("\n2) Tradução...")
        t = achar_traducao()
        if not t:
            print("  (pulada: não achei o %s)" % TRADUCAO)
        else:
            rodar("cd_ps3.py", "texto-importar", orig("global", "scripts", "xbx_us.txt"), t,
                  jogo("global", "scripts", "xbx_us.txt"))
    if "ultimate" in ligadas:
        print("\n3) Ultimate a qualquer momento...")
        extra = [] if "habilidades" in ligadas else ["--sem-habilidades"]
        rodar("cd_scripts.py", "ultimate-livre", orig("global", "scripts", "globals.ds"),
              jogo("global", "scripts", "globals.ds"), *extra)
    elif "habilidades" in ligadas:
        print("  (habilidades puladas: elas fazem parte do mod da Ultimate)")
    if "vozes" in ligadas:
        print("\n4) Gritos das Ultimates (experimental)...")
        saida = os.path.join(TRABALHO, "vozes")
        shutil.rmtree(saida, ignore_errors=True)
        rodar("cd_vozes.py", ORIGINAIS, ORIGINAIS, saida)
        for raiz, _, arqs in os.walk(saida):
            for a in arqs:
                p = os.path.join(raiz, a)
                destino = os.path.join(pasta, os.path.relpath(p, saida))
                shutil.copyfile(p, destino)
    print("\nPronto. No Xenia, abra:\n  %s" % os.path.join(os.path.abspath(pasta), "default.xex"))


def ler_escolhas():
    try:
        with open(ESCOLHAS, encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip()}
    except OSError:
        return {k for k, _, padrao, _ in OPCOES if padrao}


def salvar_escolhas(ligadas):
    os.makedirs(TRABALHO, exist_ok=True)
    with open(ESCOLHAS, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(ligadas)) + "\n")


def menu(iso, pasta):
    ligadas = ler_escolhas()
    while True:
        print("\n=== Ben 10 Cosmic Destruction - kit do Xbox 360 ===")
        print("Jogo: %s" % pasta)
        for i, (k, nome, _, sit) in enumerate(OPCOES, 1):
            print("  %d [%s] %s\n        (%s)" % (i, "X" if k in ligadas else " ", nome, sit))
        print("  A  aplicar as opções marcadas")
        print("  R  restaurar o jogo original")
        print("  S  sair")
        r = input("Escolha: ").strip().lower()
        if r.isdigit() and 1 <= int(r) <= len(OPCOES):
            k = OPCOES[int(r) - 1][0]
            ligadas ^= {k}
            salvar_escolhas(ligadas)
        elif r == "a":
            aplicar(pasta, ligadas)
        elif r == "r":
            restaurar(pasta)
        elif r == "s":
            return


def main(args):
    conferir_ferramentas()
    if len(args) < 2:
        print(__doc__)
        return 1
    iso, pasta = args[0], args[1]
    os.makedirs(TRABALHO, exist_ok=True)
    preparar(iso, pasta)
    if "--aplicar" in args:                     # sem menu (usa as escolhas salvas)
        aplicar(pasta, ler_escolhas())
        return 0
    menu(iso, pasta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
