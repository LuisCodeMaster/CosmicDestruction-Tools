"""Controle negativo: versões propositalmente erradas precisam FALHAR nos testes."""
import io, contextlib, sys, struct, tempfile
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cd_scripts as C
import testes as T

def roda(nome, ds):
    with contextlib.redirect_stdout(io.StringIO()):
        falhas = T.testar(ds)
    print('%-58s %3d falhas  ex.: %s' % (nome, len(falhas), (falhas[:2])))

ORIG = T.ORIGINAL
roda('jogo original (sem mod)', ORIG)

def build(path, **troca):
    salvo = {}
    for k, v in troca.items():
        salvo[k] = getattr(C, k); setattr(C, k, v)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            C.cmd_ultimate_livre(ORIG, path)
    finally:
        for k, v in salvo.items(): setattr(C, k, v)
    return path

# 1) sem a entrega do direcional para a fase
orig_gd = C.ajustar_guardar_direcional
def gd_original(d, funcs):
    corpo, npar = C.corpo_de(d, funcs, C.GUARDAR_DIRECIONAL); return bytes(corpo), npar
roda('mutante: sem entrega do direcional p/ a fase', build(os.path.join(tempfile.gettempdir(), 'cd_mutante1.ds'), ajustar_guardar_direcional=gd_original))

# 2) fim do mod chamando loadpreultimateform (como antes)
orig_f = C.funcoes_do_mod
def com_lpuf(rede=True, gigante=True, hud_ben=False, intro=True):
    f = orig_f(rede, gigante, hud_ben, intro)
    f[C.F_DEVOLVIDO] = C.montar([C.instr(0x01, 6), C.instr(0x08, 6, 0, 0, C.PENDENTE),
        C.instr(0x08, 6, 0, 0, C.COPIA_DIRECIONAL), C.instr(0x08, 6, 0, 0, C.RESTAURANDO),
        C.instr(0x08, 6, 0, 0, C.SAINDO), C.instr(0x08, 6, 0, 0, C.ALIEN_MOD),
        C.instr(0x08, 6, 0, 0, C.FORMA_MOD), *C.chamar0(C.crc('loadpreultimateform')), C.RETORNA])
    return f
roda('mutante: fim chama loadpreultimateform', build(os.path.join(tempfile.gettempdir(), 'cd_mutante2.ds'), funcoes_do_mod=com_lpuf))

# 3) sem a vigia por quadro (F_QUADRO vazio)
def sem_quadro(rede=True, gigante=True, hud_ben=False, intro=True):
    f = orig_f(rede, gigante, hud_ben, intro); f[C.F_QUADRO] = [C.RETORNA]; return f
roda('mutante: sem vigia por quadro', build(os.path.join(tempfile.gettempdir(), 'cd_mutante3.ds'), funcoes_do_mod=sem_quadro))

# 4) entrada ignora evento de fase (não confere FORMA_ULT)
def sem_fase(rede=True, gigante=True, hud_ben=False, intro=True):
    f = orig_f(rede, gigante, hud_ben, intro)
    corpo = b''.join(f[C.F_ENTRAR])
    alvo = C.instr(0x07, 6, 0, 0, C.FORMA_ULT)
    i = corpo.index(alvo)
    corpo = corpo[:i] + C.instr(0x01, 6) + C.NOP + corpo[i + len(alvo):]
    f[C.F_ENTRAR] = [corpo]; return f
roda('mutante: entrada não respeita evento da fase', build(os.path.join(tempfile.gettempdir(), 'cd_mutante4.ds'), funcoes_do_mod=sem_fase))

# 5) rede ligada sempre (não só com o mod)
def rede_sempre(rede=True, gigante=True, hud_ben=False, intro=True):
    f = orig_f(rede, gigante, hud_ben, intro)
    corpo = b''.join(f[C.F_REDE])
    a = C.instr(0x07, 1, 0, 0, C.PENDENTE)
    corpo = corpo.replace(a, C.instr(0x02, 1, 1, 0) + C.NOP, 1)
    f[C.F_REDE] = [corpo]; return f
roda('mutante: rede ligada sempre', build(os.path.join(tempfile.gettempdir(), 'cd_mutante5.ds'), funcoes_do_mod=rede_sempre))
