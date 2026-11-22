#!/usr/bin/env python3
"""
Simulador da máquina de scripts do Ben 10 Cosmic Destruction (PSP) para testar
o mod ultimate-livre. Executa o bytecode real dos .ds; o motor do jogo é simulado.
"""
import struct
import sys
import zlib

import os
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import cd_scripts as C  # noqa: E402

def h(n):
    return zlib.crc32(n.lower().encode())

NOMES = {}
# lista de nomes (opcional; gerada da SUA cópia com cd_scripts.py gerar-nomes)
_nomes = os.environ.get("CD_NOMES", os.path.join(RAIZ, "cd_nomes.txt"))
if os.path.exists(_nomes):
    for n in open(_nomes).read().split():
        NOMES[h(n)] = n

def nome(v):
    return NOMES.get(v, "0x%08x" % v)


class ErroScript(Exception):
    pass


class Auto(dict):
    """objeto/função desconhecida do motor (modo sonda): qualquer campo existe"""
    usados = set()

    def __init__(self, rot):
        super().__init__()
        self.rot = rot

    def get(self, k, d=None):
        Auto.usados.add("%s.%s" % (self.rot, nome(k)))
        return Nativa("%s.%s" % (self.rot, nome(k)), lambda *a: Auto("ret"))

    def __hash__(self):
        return id(self)

    def __eq__(self, o):
        return self is o

    def __repr__(self):
        return "<auto %s>" % self.rot


class Funcao:
    def __init__(self, hash_, npar, ops, base, arquivo):
        self.hash, self.npar, self.ops, self.base, self.arquivo = hash_, npar, ops, base, arquivo
        self.pos = {o[0]: i for i, o in enumerate(ops)}

    def __repr__(self):
        return "<função %s>" % nome(self.hash)


class Nativa:
    def __init__(self, nome_, fn):
        self.nome, self.fn = nome_, fn

    def __repr__(self):
        return "<nativa %s>" % self.nome


class Obj(dict):
    """objeto do motor: campos por hash; métodos são Nativa"""
    def __init__(self, rotulo, **campos):
        super().__init__()
        self.rotulo = rotulo
        for k, v in campos.items():
            self[h(k)] = v

    def __repr__(self):
        return "<%s>" % self.rotulo

    def __hash__(self):
        return id(self)

    def __eq__(self, o):
        return self is o


def verdadeiro(v):
    # igual ao jogo (EBOOT 0x89511..): nil = falso; booleano = o valor; qualquer
    # outra coisa (inclusive o número 0.0) = verdadeiro
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return True


def eh_numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def tipo(v):
    if v is None:
        return 0
    if isinstance(v, bool):
        return 1
    if eh_numero(v):
        return 2
    if isinstance(v, str):
        return 3
    if isinstance(v, dict):
        return 4
    return 5


class VM:
    def __init__(self, arquivos):
        self.funcs = {}
        self.globais = {}
        self.chamadas = []      # registro de chamadas a funções simuladas
        self.erros = []
        self.tempo = 0.0
        self.agenda = []        # (tempo, seq, função, args)
        self.seq = 0
        for arq in arquivos:
            d = open(arq, "rb").read()
            ops, funcs = C.ler(d)
            for p, hh, npar, fim in funcs:
                corpo = [o for o in ops if o[4] == hh and p < o[0] < fim]
                self.funcs[hh] = Funcao(hh, npar, corpo, p + 16, arq)

    # ---------------------------------------------------------------
    def agendar(self, atraso, f, *args):
        self.seq += 1
        self.agenda.append((self.tempo + atraso, self.seq, f, args))

    def avancar(self, segundos):
        fim = self.tempo + segundos
        while True:
            pend = sorted(x for x in self.agenda if x[0] <= fim)
            if not pend:
                break
            item = pend[0]
            self.agenda.remove(item)
            self.tempo = max(self.tempo, item[0])
            self.chamar_seguro(item[2], list(item[3]), origem="timer/callback")
        self.tempo = fim

    def chamar_seguro(self, f, args, origem=""):
        try:
            return self.chamar(f, args)
        except ErroScript as e:
            self.erros.append("%s (%s, t=%.1f)" % (e, origem, self.tempo))
            return None

    # ---------------------------------------------------------------
    def chamar(self, f, args, prof=0):
        if prof > 60:
            raise ErroScript("recursão demais")
        if isinstance(f, Nativa):
            return f.fn(*args)
        if isinstance(f, Auto):
            Auto.usados.add("chamada %s" % f.rot)
            return Auto("ret_" + f.rot)
        if isinstance(f, Funcao):
            if len(args) != f.npar:
                raise ErroScript("chamada recusada: %s espera %d argumentos, recebeu %d"
                                 % (nome(f.hash), f.npar, len(args)))
            return self.executar(f, args, prof)
        raise ErroScript("chamada de algo que não é função: %r" % (f,))

    sonda = False
    ultimo_global = {}

    def global_(self, k):
        if k in self.globais:
            return self.globais[k]
        if k in self.funcs:
            return self.funcs[k]
        return None

    def executar(self, f, args, prof):
        r = [None] * 64
        for i, a in enumerate(args):
            r[i] = a
        i = 0
        passos = 0
        while i < len(f.ops):
            passos += 1
            if passos > 20000:
                raise ErroScript("laço infinito em %s" % nome(f.hash))
            p, op, (a, b, c), imm, _ = f.ops[i]
            prox = i + 1

            def salto(alvo):
                pos = f.base + 4 * alvo
                if pos not in f.pos:
                    if pos >= f.base + 4 * 100000:
                        raise ErroScript("salto inválido")
                    # salto para o fim da função
                    if not any(o[0] >= pos for o in f.ops):
                        return len(f.ops)
                    raise ErroScript("salto para o meio de instrução em %s (alvo %d)" % (nome(f.hash), alvo))
                return f.pos[pos]

            if op == 0x01: r[a] = None
            elif op == 0x02:
                # no jogo isto cria um BOOLEANO (tipo 1) com o valor de 16 bits b|c<<8;
                # não serve para contas (só 0.0/1.0 de verdade, via 0x03)
                v = b | (c << 8)
                if v not in (0, 1):
                    self.erros.append("inteiro %d via 0x02 vira booleano em %s" % (v, nome(f.hash)))
                r[a] = (v != 0)
            elif op == 0x03: r[a] = struct.unpack("<f", struct.pack("<I", imm[0]))[0]
            elif op == 0x04: r[a] = imm.decode("latin-1")
            elif op == 0x05: r[a] = imm[0]
            elif op == 0x06: r[b] = r[a]
            elif op == 0x07:
                r[a] = self.global_(imm[0])
                self.ultimo_global[a] = nome(imm[0])
            elif op == 0x08: self.globais[imm[0]] = r[a]
            elif op == 0x0A:
                # o jogo só soma número + número; senão registra erro e NÃO grava o
                # resultado (o registro de destino fica com o valor antigo) e continua
                if eh_numero(r[a]) and eh_numero(r[b]):
                    r[c] = float(r[a]) + float(r[b])
                else:
                    self.erros.append("soma de %r + %r em %s" % (r[a], r[b], nome(f.hash)))
            elif op == 0x0B:
                # subtração (handler 0x8950600): só número - número, como a soma
                if eh_numero(r[a]) and eh_numero(r[b]):
                    r[c] = float(r[a]) - float(r[b])
                else:
                    self.erros.append("subtração de %r - %r em %s" % (r[a], r[b], nome(f.hash)))
            elif op == 0x0F: r[b] = not verdadeiro(r[a])
            elif op == 0x10: r[c] = (tipo(r[a]) == tipo(r[b]) and r[a] == r[b])
            elif op == 0x11: r[c] = not (tipo(r[a]) == tipo(r[b]) and r[a] == r[b])
            elif op == 0x12:                    # a < b (usada nos scripts de vozes)
                if eh_numero(r[a]) and eh_numero(r[b]):
                    r[c] = float(r[a]) < float(r[b])
                else:
                    self.erros.append("comparação < com tipos inválidos em %s" % nome(f.hash))
            elif op == 0x13:
                # tipos diferentes, nil ou booleano: erro e o destino NÃO muda
                if eh_numero(r[a]) and eh_numero(r[b]):
                    r[c] = float(r[a]) > float(r[b])
                elif isinstance(r[a], str) and isinstance(r[b], str):
                    r[c] = r[a] > r[b]
                else:
                    self.erros.append("comparação %r > %r em %s" % (r[a], r[b], nome(f.hash)))
            elif op == 0x14: r[c] = verdadeiro(r[a]) and verdadeiro(r[b])
            elif op == 0x15: r[c] = verdadeiro(r[a]) or verdadeiro(r[b])
            elif op == 0x16: r[a] = {}
            elif op == 0x17:
                obj = r[a]
                if obj is None:
                    raise ErroScript("acesso a campo %s de nil em %s" % (nome(imm[0]), nome(f.hash)))
                if isinstance(obj, Auto):
                    r[b] = obj.get(imm[0])
                elif isinstance(obj, dict):
                    r[b] = obj.get(imm[0])
                else:
                    raise ErroScript("acesso a campo de %r em %s" % (obj, nome(f.hash)))
            elif op == 0x18:
                t = r[a]
                if not isinstance(t, dict):
                    raise ErroScript("indexar %r em %s" % (t, nome(f.hash)))
                r[c] = t.get(r[b])
            elif op == 0x19:
                if not isinstance(r[a], dict):
                    raise ErroScript("gravar campo %s em %r (%s)" % (nome(imm[0]), r[a], nome(f.hash)))
                r[a][imm[0]] = r[b]
            elif op == 0x1A:
                if not isinstance(r[a], dict):
                    raise ErroScript("gravar índice em %r (%s)" % (r[a], nome(f.hash)))
                r[a][r[b]] = r[c]
            elif op == 0x1D: prox = salto(a | (b << 8))
            elif op == 0x1E:
                if verdadeiro(r[a]): prox = salto(b | (c << 8))
            elif op == 0x1F:
                if not verdadeiro(r[a]): prox = salto(b | (c << 8))
            elif op == 0x20:
                fn = r[a]
                if fn is None and self.sonda:
                    # função do motor que o simulador não conhece: vira "faz nada"
                    Auto.usados.add("função %s (em %s)" % (self.ultimo_global.get(a, "?"), nome(f.hash)))
                    fn = Auto("fn")
                if fn is None:
                    raise ErroScript("chamada de nil em %s (0x%x)" % (nome(f.hash), p))
                r[imm[0]] = self.chamar(fn, [r[b + k] for k in range(c)], prof + 1)
            elif op == 0x21: return None
            elif op == 0x22: return r[a]
            else:
                raise ErroScript("instrução 0x%02x não simulada em %s (0x%x)" % (op, nome(f.hash), p))
            i = prox
        return None
