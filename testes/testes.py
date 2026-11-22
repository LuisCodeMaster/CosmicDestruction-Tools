#!/usr/bin/env python3
"""Testes do mod ultimate-livre no simulador (bytecode real, motor simulado).
Versão "funções acrescentadas": nenhuma função do jogo é alterada."""
import sys
import os
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))
from simulador import VM, Nativa, Obj, h, nome, ErroScript, verdadeiro  # noqa: E402
import cd_scripts as C  # noqa: E402

# pasta com globals.ds e gld_psp.ds ORIGINAIS (da sua cópia do jogo). Padrão: a extração do cd_kit.py
BASE = os.environ.get("CD_SCRIPTS", os.path.join(os.path.dirname(AQUI), "cd_trabalho", "extraido",
                                                  "PSP_GAME", "USRDIR", "global", "scripts")) + os.sep
ORIGINAL = BASE + "globals.ds"
TRANSF_GIGANTE = 0xB7269B14
PREP_TRANSF = 0x79CD24DA
RODA_VISIVEL = 0x6881B6A5
EVT_PENDENTE = 0x68DFA66E      # FUNC_ULT liga quando o ícone é tocado antes do evento ficar pronto
ROMA_CONTINUA = 0xAEB41139     # loadpreultimateform chama em Roma de dia
FIM_ULT_ROMA = 0x8D400098      # Roma de dia chama no fim da luta (desfaz a Ultimate)


class Mundo:
    def __init__(self, globals_ds, perigo=False, missao="paris"):
        self.vm = vm = VM([globals_ds, BASE + "gld_psp.ds"])
        self.escala = 1.0
        self.preset_aberto = 0
        self.roda_modos = []
        self.dpad = 0
        self.perigo = perigo
        self.log = []
        g = vm.globais

        def nat(nome_, fn):
            return Nativa(nome_, fn)

        def registra(nome_, ret=None):
            def f(*a):
                self.log.append(nome_)
                return ret
            return nat(nome_, f)

        # tabela de ids (código real do gld_psp.ds)
        self.T = vm.chamar(vm.funcs[0xE1003DC4], [])
        T = self.T
        self.id = {k: T[h(k)] for k in ("ben", "spidermonkey", "echo", "swampfire", "terraspin",
                                          "waterhazard", "waybig")}
        self.id["humungousaur"] = T[0x1679657D]
        self.id["bigchill"] = T[0xE201C289]
        ults = {"swampfire": 0xF54B5E78, "spidermonkey": 0xF02188EC, "bigchill": 0x0AA213A1,
                "echo": 0xD1349EEF, "humungousaur": 0xBCE02525}
        self.ult_id = {k: T[v] for k, v in ults.items()}

        # gformdata
        gform = {}
        for i in range(1, 18):
            e = Obj("form%d" % i)
            e[h("character")] = "char%d" % i
            e[h("specials")] = {1: "esp"}
            alvo = i

            def troca(*a, alvo=alvo):
                self.troca_modelo(alvo)
            e[0x89D9800B] = nat("trocar_para_%d" % i, troca)
            gform[i] = e
        for k, u in ults.items():
            gform[self.id[k]][C.CAMPO_ULT] = T[u]
        g[h("gformdata")] = gform
        g[h("gcurrentcharacter")] = self.id["ben"]
        g[h("gformhotkey")] = {i: {h("formid"): v} for i, v in
                               zip(range(1, 5), [self.id["humungousaur"], self.id["terraspin"],
                                                 self.id["spidermonkey"], self.id["waterhazard"]])}

        # objetos do motor
        pessoa = self.pessoa = Obj("person")
        for m in ("isdead", "isstruggling"):
            pessoa[h(m)] = nat(m, lambda *a: False)
        self.interagindo = False
        pessoa[h("isinteracting")] = nat("isinteracting", lambda *a: self.interagindo)
        self.pos = [0.0, 10.0, 0.0]

        def posicao(*a):
            o = Obj("pos"); o[h("x")], o[h("y")], o[h("z")] = self.pos; return o
        pessoa[h("isattacking")] = nat("isattacking", lambda *a: self.perigo)

        def setscale(p, v):
            self.escala = round(v, 3)
        pessoa[h("setscale")] = nat("setscale", setscale)
        self.anims = []

        def playanim(p, anim, *resto):
            self.anims.append(anim)
            if len(resto) >= 3 and resto[2] is not None:      # (voltas, ?, callback)
                vm.agendar(1.4, resto[2], p)
        pessoa[h("playanim")] = nat("playanim", playanim)
        for m in ("dontrender", "setbreath", "settype", "message", "attach"):
            pessoa[h(m)] = registra(m)
        jogador = Obj("player")
        jogador[h("person")] = nat("person", lambda *a: pessoa)
        self.ataques = []
        jogador[h("addstartattack")] = nat("addstartattack", lambda p, a: self.ataques.append(a))
        jogador[h("isabletotransform")] = nat("isabletotransform", lambda *a: self.gcur == self.id["ben"])
        jogador[h("isplayermovementdisabled")] = nat("isplayermovementdisabled", lambda *a: False)
        jogador[h("position")] = nat("position", posicao)
        jogador[h("enableability")] = nat("enableability", lambda *a: None)
        g[h("player")] = jogador
        self.em_cena = False
        g[h("cutscene")] = Obj("cutscene", isplaying=nat("isplaying", lambda *a: self.em_cena))
        # controle de troca atual (o motor chama a cada quadro)
        self.cb_atual = vm.funcs[h("switch_form_update")]

        def setinputcb(im, n, cb):
            self.log.append("setinputcb")
            self.cb_atual = cb
        g[h("inputmgr")] = Obj("inputmgr", setinputcb=nat("setinputcb", setinputcb))
        overlay = Obj("overlay")

        def runuser(o, fn):
            if fn is vm.global_(h("characterpresetscreen_enter")) or fn == h("characterpresetscreen_enter"):
                self.preset_aberto += 1
        overlay[h("runuser")] = nat("runuser", runuser)
        overlay[h("setgloweffect")] = nat("setgloweffect", lambda *a: self.log.append("brilho"))
        self.mov_travado = 0
        pmgr = Obj("playermgr")

        def _trava(*a):
            self.mov_travado += 1

        def _solta(*a):
            self.mov_travado -= 1
        pmgr[h("lockmovement")] = nat("lockmovement", _trava)
        pmgr[h("unlockmovement")] = nat("unlockmovement", _solta)
        g[h("playermgr")] = pmgr
        g[h("overlay")] = overlay
        missao_obj = Obj("missao", getname=nat("getname", lambda *a: h(missao)))
        self.carregados = set()
        self.carrega_ok = True

        def carrega(tipo):
            def f(m, pasta, arq, cb):
                self.log.append("%s %s/%s" % (tipo, pasta, arq))
                if self.carrega_ok:
                    self.carregados.add(arq)
                    vm.agendar(1.0, cb, None)
            return nat(tipo, f)

        def descarrega(tipo):
            def f(m, pasta, arq):
                self.log.append("%s %s/%s" % (tipo, pasta, arq))
                if self.gcur == self.id["waybig"]:
                    vm.erros.append("TRAVOU: descarregou o Gigante em uso")
                self.carregados.discard(arq)
            return nat(tipo, f)
        missao_obj[h("loaddata")] = carrega("loaddata")
        missao_obj[h("loaddesc")] = carrega("loaddesc")
        missao_obj[h("unloaddata")] = descarrega("unloaddata")
        missao_obj[h("unloaddesc")] = descarrega("unloaddesc")
        g[h("missionmgr")] = Obj("missionmgr", getcurrentmission=nat("gcm", lambda *a: missao_obj))
        self.removidos = []

        def removecharacter(cm, c):
            self.removidos.append(c)
            self.log.append("removecharacter")
        g[0x93ACA275] = Obj("charmgr", removecharacter=nat("removecharacter", removecharacter))
        g[h("soundmgr")] = Obj("soundmgr", play=registra("play"))
        g[h("print")] = nat("print", lambda *a: None)
        g[h("createtimer")] = nat("createtimer", lambda f, t, n: vm.agendar(t, f))
        g[0x2B2A4FAF] = 1   # (o jogo exige != nil)
        g[0xBBC71DAF] = 1   # init_global_variables
        g[ROMA_CONTINUA] = registra("ROMA_CONTINUA")

        # funções do jogo simuladas (comportamento observado no jogo)
        self.redemoinho = False

        def limpa_tartagira():
            self.redemoinho = False
        g[0xC7A0B380] = nat("LIMPA_TARTAGIRA", limpa_tartagira)

        def voltar_ben(cb):                    # 0x326f91f9 liga a trava de transformação
            if self.redemoinho and self.gcur == self.id["terraspin"]:
                vm.erros.append("TRAVOU: virou Ben com o redemoinho da Tartagira ligado")
            g[C.TRANSF_EM_CURSO] = True
            self.gcur = self.id["ben"]
            self.escala_por_forma(self.id["ben"])
            self.log.append("VOLTAR_BEN")
            if cb is not None:
                vm.agendar(0.5, cb)
        g[C.VOLTAR_BEN] = nat("VOLTAR_BEN", voltar_ben)

        def destransf(cb):
            g[C.TRANSF_EM_CURSO] = True
            self.gcur = self.id["ben"]
            self.escala_por_forma(self.id["ben"])
            self.log.append("FUNC_DESTRANSF")
            if cb is not None:
                vm.agendar(0.5, cb)
        g[C.FUNC_DESTRANSF] = nat("FUNC_DESTRANSF", destransf)
        vm.natives_destransf = destransf

        def virar(x):                          # troca normal: switch_character_cb no fim
            g[C.TRANSF_EM_CURSO] = True
            self.troca_modelo(x)
            vm.agendar(1.0, vm.funcs[h("switch_character_cb")])
        g[C.VIRAR_ALIEN] = nat("VIRAR_ALIEN", virar)

        def precarregar(a, b, c, d, cb):
            self.log.append("carrega %s" % [a, b, c, d])
            hk = g[h("gformhotkey")]
            for i, v in zip(range(1, 5), [a, b, c, d]):
                hk[i][h("formid")] = v
            if cb is not None:
                vm.agendar(1.0, cb)
        g[C.PRECARREGAR] = nat("PRECARREGAR", precarregar)
        _destransf_orig = destransf

        def destransf2(cb):                     # virar Ben cancela a interação
            self.interagindo = False
            _destransf_orig(cb)
        g[C.FUNC_DESTRANSF] = nat("FUNC_DESTRANSF", destransf2)
        vm.natives_destransf = destransf2

        def gigante(cb):                      # 0xb7269b14 (exige 1 argumento)
            if self.id["waybig"] not in self.hotkeys():
                vm.erros.append("TRAVOU: virou o Gigante sem o pacote dele carregado (direcional)")
            g[C.TRANSF_EM_CURSO] = True
            self.gcur = self.id["waybig"]
            self.escala = 3.0
            if cb is not None:
                vm.agendar(1.5, cb)
        g[TRANSF_GIGANTE] = nat("TRANSF_GIGANTE", gigante)
        g[PREP_TRANSF] = nat("PREP_TRANSF", lambda: None)
        g[0x8F436AD3] = nat("roda", lambda i, a, b: self.roda_modos.append(b))

        def dpad(i, a, b):
            self.dpad += 1
        g[0x66960347] = nat("dpad", dpad)
        g[0x801B4AF7] = registra("0x801b4af7")
        g[RODA_VISIVEL] = registra("roda_visivel")
        g[h("unload_all_hot_key_forms")] = registra("unload")
        # restauração do direcional (0x8ee0f42c) e o guardar: código real

    # -------------------------------------------------------------
    @property
    def gcur(self):
        return self.vm.globais[h("gcurrentcharacter")]

    @gcur.setter
    def gcur(self, v):
        self.vm.globais[h("gcurrentcharacter")] = v

    def escala_por_forma(self, x):
        self.escala = 3.0 if x == self.id["waybig"] else 1.0

    def troca_modelo(self, x):
        self.gcur = x
        self.escala_por_forma(x)
        if x in self.ult_id.values():
            self.vm.globais[C.TRANSF_EM_CURSO] = True
            # o motor chama switch_ultimate_cb ao fim da animação de transformação
            self.vm.agendar(2.0, self.vm.funcs[h("switch_ultimate_cb")])

    def hotkeys(self):
        hk = self.vm.globais[h("gformhotkey")]
        return [hk[i][h("formid")] for i in range(1, 5)]

    def g(self, n):
        return self.vm.globais.get(h(n) if isinstance(n, str) else n)

    def botao(self, select=False):
        """um quadro do jogo: o motor chama o controle de troca registrado"""
        if self.cb_atual is None:
            return
        entrada = Obj("input", btn_select=select)
        self.vm.chamar_seguro(self.cb_atual, [entrada, None, None], origem="controle")

    def quadros(self, segundos, passo=0.25):
        t = 0
        while t < segundos:
            self.botao(False)
            self.vm.avancar(passo)
            t += passo

    def quadros_reais(self, n, passo=1 / 30.0, select=False):
        for _ in range(n):
            self.botao(select)
            self.vm.avancar(passo)

    def nome_id(self, v):
        for k, x in list(self.id.items()) + [("ult_" + k, x) for k, x in self.ult_id.items()]:
            if x == v:
                return k
        return str(v)

    def travado(self):
        return verdadeiro(self.g(C.TRAVA_INPUT)) or verdadeiro(self.g(C.TRANSF_EM_CURSO))

    def mod_limpo(self):
        return all(self.g(v) is None for v in (C.PENDENTE, C.SAINDO, C.RESTAURANDO, C.ALIEN_MOD,
                                               C.FORMA_MOD, C.COPIA_DIRECIONAL))

    # ------------- um Ultimate Event de fase (como l_romd faz) -------------
    def evento_fase_comeca(self, alien="bigchill"):
        vm, g = self.vm, self.vm.globais
        g[PREP_TRANSF] = Nativa("PREP_TRANSF", lambda: None)
        g[C.FORMA_ULT] = self.id[alien]                 # 0x11152a3b
        estado = {"pronto": False}

        def depois_ben():                               # 0xd4786a27
            vm.chamar_seguro(vm.global_(C.GUARDAR_DIRECIONAL), [], origem="fase")
            hk = g[h("gformhotkey")]
            hk[3][h("formid")] = self.ult_id[alien]     # map_hot_key(ultimate, 3, ...)
            g[0x749E7798] = True
            vm.chamar_seguro(vm.global_(C.VIRAR_ALIEN), [self.id[alien]], origem="fase")
            vm.agendar(1.0, Nativa("evento_pronto", pronto))

        def pronto():                                   # 0x4d621ba3
            g[C.EVENTO_ULT] = True
            estado["pronto"] = True
            if verdadeiro(g.get(EVT_PENDENTE)):
                vm.chamar_seguro(vm.funcs[C.FUNC_ULT], [None], origem="fase")
        if self.gcur != self.id["ben"]:
            vm.chamar_seguro(vm.global_(C.VOLTAR_BEN), [Nativa("cb_fase", depois_ben)], origem="fase")
        else:
            depois_ben()
        return estado

    def evento_fase_icone(self):
        icone = Obj("icone", addfadeeffect=Nativa("fade", lambda *a: None))
        self.vm.chamar_seguro(self.vm.funcs[C.FUNC_ULT], [icone], origem="fase")

    def evento_fase_termina(self):                      # fim da luta de Roma
        self.vm.chamar_seguro(self.vm.funcs[FIM_ULT_ROMA], [], origem="fase")


# =================================================================
RESULTADOS = []


def checa(cond, texto):
    RESULTADOS.append((bool(cond), texto))
    print("   %s %s" % ("OK  " if cond else "FALHOU", texto))


def cenario(titulo):
    print("\n== " + titulo)


def novo_mundo(ds, alien="humungousaur", **kw):
    m = Mundo(ds, **kw)
    m.gcur = m.id[alien]
    m.redemoinho = alien == "terraspin"
    return m


def entrar_ultimate(m, alien):
    m.gcur = m.id[alien]
    m.botao(select=True)
    m.quadros(6)


def sem_erros(m, filtro=None):
    err = [e for e in m.vm.erros if not (filtro and filtro in e)]
    checa(not err, "nenhum erro de script %s" % err[:3])


def testar(ds):
    RESULTADOS.clear()

    for alien in ("humungousaur", "spidermonkey", "bigchill", "echo", "swampfire"):
        cenario("Entrar na Ultimate como %s (SELECT) e sair (SELECT)" % alien)
        m = novo_mundo(ds, alien)
        original_hk = m.hotkeys()
        m.botao(select=True)
        m.quadros(6)
        checa(m.gcur == m.ult_id[alien], "virou %s (está: %s)" % ("ult_" + alien, m.nome_id(m.gcur)))
        checa(not m.travado(), "controles liberados depois da transformação")
        checa(verdadeiro(m.g(C.ATIVA)), "monitor ligado")
        checa(m.g(C.FORMA_ULT) == m.id[alien], "a variável do jogo diz qual alien virou Ultimate")
        m.roda_modos.clear(); d0 = m.dpad
        m.quadros(1)
        checa(m.roda_modos and all(x == 1 for x in m.roda_modos), "HUD em modo golpes (modo 1) na Ultimate")
        checa(m.dpad == d0, "direcional não troca de alien na Ultimate (igual ao jogo)")
        m.botao(select=True)
        m.quadros(4)
        checa(m.gcur == m.id["ben"], "voltou para o Ben (está: %s)" % m.nome_id(m.gcur))
        checa(m.hotkeys() == original_hk, "aliens do direcional restaurados %s" % [m.nome_id(x) for x in m.hotkeys()])
        checa(m.g(C.FORMA_ULT) is None and m.mod_limpo(), "estado do mod limpo")
        checa(not m.travado(), "controles liberados")
        checa(not verdadeiro(m.g(C.ATIVA)), "monitor desligado")
        checa(m.removidos == [m.vm.globais[h("gformdata")][m.ult_id[alien]][h("character")]],
              "Ultimate tirada da memória (%s)" % m.removidos)
        m.roda_modos.clear(); d0 = m.dpad
        m.quadros(1)
        checa(m.dpad > d0 and all(x == 0 for x in m.roda_modos), "direcional e roda de aliens voltaram ao normal")
        checa("ROMA_CONTINUA" not in m.log, "não disparou nada da fase")
        sem_erros(m)

    for perigo in (False, True):
        cenario("Tartagira + SELECT vira o Gigante%s" % (" (atacando: recusado)" if perigo else ""))
        m = novo_mundo(ds, "terraspin", perigo=perigo)
        hk = m.hotkeys()
        m.botao(select=True); m.quadros(6)
        if perigo:
            checa(m.gcur == m.id["terraspin"] and not m.travado() and m.mod_limpo(), "recusou sem travar nada")
        else:
            checa(m.gcur == m.id["waybig"], "virou o Gigante (está: %s)" % m.nome_id(m.gcur))
            checa(m.escala == C.ESCALA_GIGANTE, "tamanho %s" % m.escala)
            checa(m.id["waybig"] in m.hotkeys(), "carregou as animações do Gigante no direcional")
            checa("loaddata l_tokd/g_wayb" not in m.log, "não depende do pacote da fase final (l_tokd)")
            checa(not m.redemoinho, "redemoinho da Tartagira desligado antes")
            checa(not m.travado() and verdadeiro(m.g(C.ATIVA)), "controles livres, monitor ligado")
            m.botao(select=True); m.quadros(5)
            checa(m.gcur == m.id["ben"] and m.escala == 1.0, "SELECT: voltou para o Ben, tamanho normal")
            gig = m.vm.globais[h("gformdata")][m.id["waybig"]][h("character")]
            checa(gig in m.removidos, "tirou o Gigante da memória (%s)" % m.removidos)
            checa(not m.carregados, "nada da fase final carregado")
            checa(m.hotkeys() == hk and m.mod_limpo() and not m.travado(), "direcional intacto, estado limpo")
            m.gcur = m.id["humungousaur"]; m.botao(select=True); m.quadros(6)
            checa(m.gcur == m.ult_id["humungousaur"], "depois a Ultimate normal funciona")
        sem_erros(m)

    cenario("Gigante: carregamento nunca termina - nada trava para sempre")
    m = novo_mundo(ds, "terraspin")
    hk = m.hotkeys()
    real = m.vm.globais[C.PRECARREGAR]
    m.vm.globais[C.PRECARREGAR] = Nativa("prec_mudo", lambda a, b, c, d, cb: None)
    m.botao(select=True)
    m.vm.avancar(16)
    m.vm.globais[C.PRECARREGAR] = real
    m.quadros(6)
    checa(m.gcur != m.id["waybig"] and not m.travado(), "não virou, controles soltos (%s)" % m.nome_id(m.gcur))
    checa(m.mod_limpo() and m.hotkeys() == hk, "estado limpo")
    d0 = m.dpad; m.quadros(1)
    checa(m.dpad > d0, "direcional funcionando")
    sem_erros(m)

    cenario("Gigante: fase começa evento antes de carregar (cancela e descarrega)")
    m = novo_mundo(ds, "terraspin")
    m.botao(select=True); m.vm.avancar(0.6)
    m.vm.globais[C.FORMA_ULT] = m.id["bigchill"]
    m.quadros(4)
    checa(m.gcur != m.id["waybig"], "não virou o Gigante por cima da fase")
    m.vm.globais[C.FORMA_ULT] = None
    m.quadros(4)
    checa(m.mod_limpo() and not m.travado(), "estado limpo depois do evento")
    checa(not m.carregados, "nada carregado sobrando (%s)" % m.carregados)
    checa(m.vm.globais.get(C.GIG_CARREGADO) is None, "marca do modelo limpa")
    sem_erros(m)

    cenario("Ultimate acaba sozinha (o jogo devolve o Ben) com trava presa")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.gcur = m.id["ben"]
    m.vm.globais[C.TRANSF_EM_CURSO] = 1          # o jogo pode deixar travas ligadas (presas)
    m.vm.avancar(12)                              # o mod espera ~9 s e depois age
    m.quadros(3)
    checa(m.hotkeys() == original_hk, "monitor restaurou os aliens")
    checa(not m.travado(), "travas liberadas")
    checa(m.g(C.FORMA_ULT) is None and m.mod_limpo(), "estado limpo")
    sem_erros(m)

    cenario("Ultimate acaba sozinha e o jogo devolve o alien normal")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.gcur = m.id["humungousaur"]
    m.quadros(8)
    checa(m.gcur == m.id["ben"], "voltou para o Ben")
    checa(m.hotkeys() == original_hk, "aliens restaurados")
    sem_erros(m)

    cenario("SELECT como Ben abre a tela de troca de aliens (igual ao jogo)")
    m = novo_mundo(ds, "ben")
    m.botao(select=True)
    m.quadros(1)
    checa(m.preset_aberto == 1, "tela de troca aberta")
    checa(m.gcur == m.id["ben"] and m.g(C.FORMA_ULT) is None, "nada mais aconteceu")
    sem_erros(m)

    cenario("SELECT como Ben com a transformação bloqueada pela fase: nada (igual ao jogo)")
    m = novo_mundo(ds, "ben")
    m.vm.globais[h("player")][h("isabletotransform")] = Nativa("iat", lambda *a: False)
    m.botao(select=True); m.quadros(1)
    checa(m.preset_aberto == 0, "tela de troca não abriu")
    sem_erros(m)

    cenario("SELECT como alien sem Ultimate (Water Hazard)")
    m = novo_mundo(ds, "waterhazard")
    hk = m.hotkeys()
    m.botao(select=True)
    m.quadros(3)
    checa(m.gcur == m.id["waterhazard"] and m.hotkeys() == hk, "nada acontece")
    checa(not m.travado(), "controles não travam")
    sem_erros(m)

    cenario("SELECT atacando (situação insegura)")
    m = novo_mundo(ds, "humungousaur", perigo=True)
    m.botao(select=True)
    m.quadros(3)
    checa(m.gcur == m.id["humungousaur"] and m.g(C.FORMA_ULT) is None, "transformação recusada")
    checa(not m.travado() and m.mod_limpo(), "controles não travam, nada pendente")

    cenario("Apertar SELECT várias vezes durante o carregamento")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    m.botao(select=True)
    for _ in range(12):
        m.vm.avancar(0.25)
        m.botao(select=True)
    m.quadros(6)
    checa(m.gcur == m.ult_id["humungousaur"], "terminou na Ultimate (está: %s)" % m.nome_id(m.gcur))
    carregs = [x for x in m.log if x.startswith("carrega")]
    checa(len(carregs) == 1, "carregou uma vez só (%d)" % len(carregs))
    m.botao(select=True)
    m.quadros(4)
    checa(m.hotkeys() == original_hk, "saiu e restaurou")
    sem_erros(m)

    cenario("Direcional durante o carregamento da entrada e da saída: o jogo ignora (trava)")
    m = novo_mundo(ds, "humungousaur")
    m.botao(select=True)
    d0 = m.dpad
    for _ in range(16):
        m.vm.avancar(0.25); m.botao(False)
        if m.gcur == m.ult_id["humungousaur"]:
            break
    checa(m.dpad == d0, "direcional não chamado no meio da entrada")
    m.quadros(3)
    m.botao(select=True); m.vm.avancar(0.6)
    d0 = m.dpad
    for _ in range(4):
        m.botao(False); m.vm.avancar(0.25)
    checa(m.dpad == d0, "direcional não chamado no meio da devolução")
    m.quadros(3)
    d0 = m.dpad; m.quadros(1)
    checa(m.dpad > d0, "direcional volta a funcionar depois")
    sem_erros(m)

    cenario("Repetir entrar/sair 5 vezes seguidas")
    m = novo_mundo(ds, "spidermonkey")
    original_hk = m.hotkeys()
    ok = True
    for _ in range(5):
        m.gcur = m.id["spidermonkey"]
        m.botao(select=True)
        m.quadros(6)
        ok &= m.gcur == m.ult_id["spidermonkey"]
        m.botao(select=True)
        m.quadros(4)
        ok &= m.gcur == m.id["ben"] and m.hotkeys() == original_hk and m.mod_limpo()
    checa(ok, "5 ciclos completos sem perder os aliens")
    sem_erros(m)

    cenario("Fim natural pelo próprio jogo (undo_ultimate_form) com o monitor rodando")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    n0 = len([x for x in m.log if x.startswith("carrega")])
    m.vm.globais[C.TRAVA_INPUT] = 1               # o jogo trava e volta para o Ben
    m.vm.natives_destransf(m.vm.funcs[h("undo_ultimate_form")])
    for _ in range(40):
        m.vm.avancar(0.25); m.botao(select=False)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "aliens do direcional devolvidos %s" % [m.nome_id(x) for x in m.hotkeys()])
    n = len([x for x in m.log if x.startswith("carrega")]) - n0
    checa(n == 1, "devolveu uma vez só, sem carregar em dobro (%d)" % n)
    checa(m.mod_limpo() and m.g(C.FORMA_ULT) is None, "estado limpo")
    checa(not m.travado(), "controles liberados")
    m.gcur = m.id["humungousaur"]; m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["humungousaur"], "entra na Ultimate de novo depois")
    sem_erros(m)

    cenario("Caso da foto: Ben com o direcional trocado (alien + Ultimate) e nada ativo")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.vm.agenda.clear(); m.vm.globais[C.ATIVA] = None   # monitor perdido
    m.vm.globais[C.FORMA_ULT] = None                     # e a marca do jogo apagada
    m.gcur = m.id["ben"]
    m.quadros(3)                                         # só o direcional/roda rodando
    checa(m.hotkeys() == original_hk, "devolveu sozinho %s" % [m.nome_id(x) for x in m.hotkeys()])
    checa(not m.travado() and m.mod_limpo(), "controles liberados, estado limpo")
    sem_erros(m)

    cenario("Monitor perdido com a marca ainda ligada (ex.: timer sumiu): devolve depois de ~15 s")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.vm.agenda.clear()                                  # ATIVA continua ligada, sem monitor
    m.gcur = m.id["ben"]
    d0 = m.dpad
    m.quadros_reais(100)
    checa(m.dpad > d0, "direcional do jogo funcionando enquanto isso")
    checa(m.hotkeys() != original_hk, "(ainda esperando o monitor)")
    m.quadros_reais(400)
    m.quadros(3)
    checa(m.hotkeys() == original_hk and m.mod_limpo(), "devolveu sozinho %s" % [m.nome_id(x) for x in m.hotkeys()])
    sem_erros(m)

    cenario("Devolução empaca (callback nunca chega): libera e tenta de novo")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    real = m.vm.globais[C.PRECARREGAR]
    m.vm.globais[C.PRECARREGAR] = Nativa("prec_mudo", lambda a, b, c, d, cb: None)
    m.botao(select=True); m.quadros(4)
    m.vm.globais[C.PRECARREGAR] = real
    m.vm.avancar(11); m.quadros(3)
    checa(m.hotkeys() == original_hk and m.g(C.PENDENTE) is None, "devolveu na segunda tentativa")
    checa(not m.travado(), "controles liberados")
    sem_erros(m)

    cenario("Devolução empaca sempre: depois de 3 vezes para de insistir (controles livres)")
    m = novo_mundo(ds, "humungousaur")
    entrar_ultimate(m, "humungousaur")
    m.vm.globais[C.PRECARREGAR] = Nativa("prec_mudo", lambda a, b, c, d, cb: None)
    m.botao(select=True)
    for _ in range(80):
        m.quadros(0.5)
    tentativas = m.log.count("VOLTAR_BEN") + m.log.count("FUNC_DESTRANSF")
    checa(not m.travado(), "controles livres no fim")
    d0 = m.dpad; m.quadros(1)
    checa(m.dpad > d0, "direcional do jogo funcionando")
    checa(verdadeiro(m.g(C.FALHAS)) and m.g(C.FALHAS) >= 3, "parou de tentar sozinho (%s falhas)" % m.g(C.FALHAS))
    sem_erros(m)

    cenario("Sair e entrar de novo rápido (SELECT, SELECT, SELECT...)")
    m = novo_mundo(ds, "spidermonkey")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "spidermonkey")
    for _ in range(10):
        m.botao(select=True); m.vm.avancar(0.25)
    m.quadros(8)
    if m.gcur == m.ult_id["spidermonkey"]:
        m.botao(select=True); m.quadros(6)
    checa(m.hotkeys() == original_hk, "direcional original no fim %s" % [m.nome_id(x) for x in m.hotkeys()])
    checa(m.mod_limpo(), "nada pendente")
    sem_erros(m)

    for alien_z in ("humungousaur", "ben"):
        cenario("Área de câmera fixa (o jogo desliga a troca) como %s" % ("Ultimate" if alien_z != "ben" else "Ben"))
        m = novo_mundo(ds, alien_z)
        original_hk = m.hotkeys()
        if alien_z != "ben":
            entrar_ultimate(m, alien_z)
        m.vm.globais[0xE67AB1F3] = Nativa("hud", lambda: None)
        m.vm.chamar_seguro(m.vm.funcs[0x9AD2BFC4], [], origem="zona")
        checa(m.cb_atual is not None and m.cb_atual is m.vm.funcs.get(C.F_ZONA), "controle trocado pelo filtro da zona")
        antes = m.gcur
        for _ in range(3):
            m.botao(select=True)
            m.vm.avancar(0.25)
        m.vm.avancar(4)
        if alien_z != "ben":
            checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "SELECT saiu da Ultimate dentro da zona")
        else:
            checa(m.gcur == antes and m.preset_aberto == 0, "como Ben, SELECT na zona não faz nada (igual ao jogo)")
        sem_erros(m)

    for tipo in ("trava", "controle"):
        cenario("Ultimate sem resposta depois do ataque especial (%s)" % ("trava presa" if tipo == "trava" else "controle desligado"))
        m = novo_mundo(ds, "swampfire")
        original_hk = m.hotkeys()
        entrar_ultimate(m, "swampfire")
        n_cb = m.log.count("setinputcb")
        if tipo == "trava":
            m.vm.globais[C.TRANSF_EM_CURSO] = 1
        # sem o controle rodando (nenhum botao()): só o tempo passa
        m.vm.avancar(8)
        checa(not m.travado(), "travas liberadas sozinhas")
        checa(m.log.count("setinputcb") == n_cb, "não mexeu no controle de troca do jogo (só nas travas)")
        m.botao(select=True); m.quadros(5)
        checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "SELECT saiu da Ultimate depois")
        sem_erros(m)

    cenario("Ultimate normal (controle rodando): o vigia não mexe em nada")
    m = novo_mundo(ds, "swampfire")
    entrar_ultimate(m, "swampfire")
    n_cb = m.log.count("setinputcb")
    for _ in range(40):
        m.botao(select=False); m.vm.avancar(0.25)
    checa(m.log.count("setinputcb") == n_cb and m.gcur == m.ult_id["swampfire"], "nenhuma intervenção, continua na Ultimate")
    sem_erros(m)

    cenario("Ultimate 'ocupada' para sempre (depois do especial): segurar SELECT sai")
    m = novo_mundo(ds, "swampfire")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "swampfire")
    m.perigo = True                                   # o jogo diz "atacando" o tempo todo
    m.botao(select=True); m.quadros(1)
    checa(m.gcur == m.ult_id["swampfire"], "um toque rápido não força a saída")
    for _ in range(50):
        m.botao(select=True)
    m.quadros(5)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "segurando SELECT saiu e devolveu o direcional")
    checa(m.mod_limpo(), "estado limpo")
    sem_erros(m)

    cenario("A volta para o Ben não acontece: libera e deixa tentar de novo")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    real = m.vm.globais[C.FUNC_DESTRANSF]
    m.vm.globais[C.FUNC_DESTRANSF] = Nativa("destransf_mudo", lambda cb: None)
    m.botao(select=True); m.quadros(2)
    checa(m.gcur == m.ult_id["humungousaur"], "(jogo recusou a volta)")
    m.vm.globais[C.FUNC_DESTRANSF] = real
    m.vm.avancar(11); m.quadros(1)
    checa(m.g(C.SAINDO) is None and verdadeiro(m.g(C.ATIVA)), "liberado e monitor religado")
    m.botao(select=True); m.quadros(5)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "SELECT de novo saiu")
    sem_erros(m)

    def mundo_rede(alien, ultimate=True):
        m = novo_mundo(ds, alien)
        est = {"y": 10.0, "beams": []}

        def pos(*a):
            o = Obj("pos"); o[h("y")] = est["y"]; return o
        m.vm.globais[h("player")][h("position")] = Nativa("position", pos)
        pm = m.vm.globais.get(h("playermgr")) or Obj("playermgr")

        def beam(pmgr, p):
            est["beams"].append(p[h("y")]); est["y"] = p[h("y")]
        pm[h("beam")] = Nativa("beam", beam)
        m.vm.globais[h("playermgr")] = pm
        if ultimate:
            entrar_ultimate(m, alien)
        return m, est

    def passo(m, est, dy, seg):
        for _ in range(int(seg * 4)):
            est["y"] += dy / 4.0
            m.botao(select=False); m.vm.avancar(0.25)

    cenario("Rede de segurança na Ultimate: caiu no vazio volta ao último lugar seguro")
    m, est = mundo_rede("humungousaur")
    passo(m, est, 0, 4)                 # parado no chão (y=10)
    passo(m, est, -15, 6)               # caindo sem parar
    checa(est["beams"] == [10.0], "voltou para a altura segura uma vez (%s)" % est["beams"])
    redes = sum(1 for x in m.vm.agenda if x[2] is m.vm.funcs.get(C.F_REDE))
    checa(redes == 1, "só uma rede rodando (%d)" % redes)
    sem_erros(m)

    cenario("Rede de segurança: pulo, escada e queda curta não acionam")
    m, est = mundo_rede("humungousaur")
    passo(m, est, 0, 3)
    passo(m, est, 6, 0.5); passo(m, est, -6, 0.5)    # pulo
    passo(m, est, -2.5, 8)                            # descendo escada/rampa
    passo(m, est, 0, 2)
    passo(m, est, -12, 1.5)                           # caiu de um degrau alto
    passo(m, est, 0, 3)
    checa(est["beams"] == [], "nenhum resgate (%s)" % est["beams"])
    sem_erros(m)

    cenario("Rede de segurança: desliga quando o mod termina (quedas da fase são do jogo)")
    m, est = mundo_rede("humungousaur")
    passo(m, est, 0, 3)
    m.botao(select=True); m.quadros(5)
    checa(m.gcur == m.id["ben"] and m.mod_limpo(), "(saiu da Ultimate)")
    passo(m, est, 0, 3)
    passo(m, est, -15, 6)                             # queda roteirizada da fase
    checa(est["beams"] == [], "não puxou de volta (%s)" % est["beams"])
    redes = sum(1 for x in m.vm.agenda if x[2] is m.vm.funcs.get(C.F_REDE))
    checa(redes == 0, "rede parada (%d)" % redes)
    sem_erros(m)

    cenario("Rede de segurança: entrar de novo não usa o lugar seguro antigo")
    m, est = mundo_rede("humungousaur")
    passo(m, est, 0, 4)                               # seguro em y=10
    m.botao(select=True); m.quadros(5)
    est["y"] = 50.0                                   # andou até outro lugar
    m.gcur = m.id["humungousaur"]; m.botao(select=True); m.quadros(6)
    passo(m, est, -15, 6)                             # caiu logo depois de entrar
    checa(10.0 not in est["beams"], "não voltou para o lugar antigo (%s)" % est["beams"])
    sem_erros(m)

    cenario("Trava de transformação do jogo presa (sem o mod): solta depois de ~15 s")
    m = novo_mundo(ds, "ben")
    m.vm.globais[C.TRANSF_EM_CURSO] = 1           # trocou de alien e a troca nunca terminou
    m.quadros_reais(200)
    checa(m.travado(), "(ainda esperando: pode ser uma troca demorada)")
    m.quadros_reais(300)
    checa(not m.travado(), "trava liberada")
    d0 = m.dpad; m.quadros(1)
    checa(m.dpad > d0, "direcional voltou")
    sem_erros(m)

    cenario("Trava do jogo durante uma cena: o mod não mexe")
    m = novo_mundo(ds, "ben")
    m.em_cena = True
    m.vm.globais[C.TRAVA_INPUT] = 1
    m.vm.globais[C.TRANSF_EM_CURSO] = 1
    m.quadros_reais(800)
    checa(verdadeiro(m.g(C.TRAVA_INPUT)) and verdadeiro(m.g(C.TRANSF_EM_CURSO)), "travas continuam (a cena manda)")
    sem_erros(m)

    cenario("Trava dos botões ligada pelo jogo (não pelo mod): o mod não mexe")
    m = novo_mundo(ds, "ben")
    m.vm.globais[C.TRAVA_INPUT] = 1
    m.quadros_reais(800)
    checa(verdadeiro(m.g(C.TRAVA_INPUT)), "trava do jogo intacta")
    sem_erros(m)

    cenario("Troca de alien normal (trava por 2 s): nada mexe")
    m = novo_mundo(ds, "ben")
    n_cb = m.log.count("setinputcb")
    m.vm.globais[C.TRANSF_EM_CURSO] = 1
    m.quadros_reais(60)
    checa(m.travado(), "(trava do jogo respeitada)")
    m.vm.globais[C.TRANSF_EM_CURSO] = None
    m.quadros_reais(600)
    checa(m.log.count("setinputcb") == n_cb and m.g(C.QUADROS_TRAVA) == 0, "nenhuma intervenção")
    sem_erros(m)

    cenario("Pior caso: travas presas + monitor perdido durante a Ultimate do mod")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.vm.agenda.clear(); m.vm.globais[C.ATIVA] = None
    m.vm.globais[C.TRAVA_INPUT] = 1; m.vm.globais[C.TRANSF_EM_CURSO] = 1
    m.vm.globais[C.TRAVA_MOD] = 1
    m.gcur = m.id["ben"]
    m.quadros_reais(500)
    m.quadros(4)
    checa(not m.travado(), "controles soltos")
    checa(m.hotkeys() == original_hk and m.mod_limpo(), "direcional devolvido %s" % [m.nome_id(x) for x in m.hotkeys()])
    sem_erros(m)

    cenario("Ben por 10 s apertando SELECT de vez em quando: direcional sempre do jogo")
    m = novo_mundo(ds, "ben")
    for i in range(40):
        m.botao(select=(i % 8 == 0)); m.vm.avancar(0.25)
    redes = sum(1 for x in m.vm.agenda if x[2] is m.vm.funcs.get(C.F_REDE))
    checa(redes == 0, "rede desligada fora do mod (%d)" % redes)
    d0 = m.dpad
    m.quadros(1)
    checa(m.dpad > d0, "direcional repassado ao jogo")
    sem_erros(m)

    cenario("Direcional nunca é bloqueado pelo mod (estado pendente velho)")
    m = novo_mundo(ds, "ben")
    m.vm.globais[C.PENDENTE] = True; m.vm.globais[C.ATIVA] = True; m.vm.globais[C.RESTAURANDO] = True
    d0 = m.dpad
    m.quadros(2)
    checa(m.dpad > d0, "direcional chamado mesmo com o estado velho")
    sem_erros(m)

    # ---------------- Ultimate Events das fases ----------------
    cenario("Ultimate Event da fase (Roma de dia) com o mod instalado: tudo como no jogo")
    m = novo_mundo(ds, "humungousaur", missao="rome_day")
    original_hk = m.hotkeys()
    est = m.evento_fase_comeca("bigchill")
    m.quadros(3)
    checa(est["pronto"] and m.gcur == m.id["bigchill"], "a fase virou o Big Chill e preparou o evento")
    checa(m.g(C.PENDENTE) is None, "o mod não guardou nada")
    m.botao(select=True); m.quadros(2)
    checa(m.gcur == m.id["bigchill"] and m.g(C.PENDENTE) is None, "SELECT durante o evento: o mod não entra")
    m.evento_fase_icone()
    m.quadros(3)
    checa(m.gcur == m.ult_id["bigchill"], "ícone da fase: virou a Ultimate do evento (função original)")
    for _ in range(6):
        m.botao(select=True)
    m.quadros(2)
    checa(m.gcur == m.ult_id["bigchill"], "SELECT não tira a Ultimate da fase")
    m.evento_fase_termina()
    m.quadros(4)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "fim do evento: a fase devolveu o direcional %s" % [m.nome_id(x) for x in m.hotkeys()])
    checa(m.log.count("ROMA_CONTINUA") == 1, "a fase seguiu adiante uma vez (%d)" % m.log.count("ROMA_CONTINUA"))
    checa(m.g(C.FORMA_ULT) is None and m.mod_limpo(), "nada do mod pendente")
    m.gcur = m.id["humungousaur"]; m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["humungousaur"], "depois do evento (EVENTO_ULT continua ligado) o SELECT funciona")
    m.botao(select=True); m.quadros(4)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "e sai normalmente")
    checa(m.log.count("ROMA_CONTINUA") == 1, "sair da Ultimate do mod não dispara a fase de Roma")
    sem_erros(m, filtro="fase")

    cenario("Ícone tocado antes do evento ficar pronto (pendência da fase): funciona como no jogo")
    m = novo_mundo(ds, "humungousaur", missao="rome_day")
    est = m.evento_fase_comeca("bigchill")
    m.evento_fase_icone()                        # cedo demais
    checa(verdadeiro(m.g(EVT_PENDENTE)), "a função original marcou a pendência")
    m.quadros(4)
    checa(m.gcur == m.ult_id["bigchill"], "quando ficou pronto, virou a Ultimate do evento")
    sem_erros(m, filtro="fase")

    cenario("Fase começa um Ultimate Event no meio da Ultimate do mod (mesmo alien ou outro)")
    for alien_mod in ("humungousaur", "bigchill"):
        m = novo_mundo(ds, alien_mod, missao="rome_day")
        original_hk = m.hotkeys()
        entrar_ultimate(m, alien_mod)
        removidos0 = list(m.removidos)
        destransf0 = m.log.count("FUNC_DESTRANSF")
        est = m.evento_fase_comeca("bigchill")
        m.quadros(4)
        checa(m.g(C.BACKUP_JOGO) is not None and [m.g(C.BACKUP_JOGO).get(float(i)) for i in range(1, 5)] == original_hk,
              "[%s] a fase recebeu o direcional verdadeiro" % alien_mod)
        checa(m.mod_limpo() and not verdadeiro(m.g(C.ATIVA)), "[%s] o mod saiu de cena" % alien_mod)
        checa(m.removidos[len(removidos0):] == [m.vm.globais[h("gformdata")][m.ult_id[alien_mod]][h("character")]],
              "[%s] Ultimate do mod tirada da memória" % alien_mod)
        m.evento_fase_icone(); m.quadros(3)
        checa(m.gcur == m.ult_id["bigchill"], "[%s] evento da fase seguiu" % alien_mod)
        m.quadros(10)
        checa(m.log.count("FUNC_DESTRANSF") == destransf0, "[%s] o mod não mexeu no personagem depois" % alien_mod)
        m.evento_fase_termina(); m.quadros(4)
        checa(m.hotkeys() == original_hk, "[%s] fim do evento: direcional original %s" % (alien_mod, [m.nome_id(x) for x in m.hotkeys()]))
        sem_erros(m, filtro="fase")

    cenario("Fase começa o evento no meio da ENTRADA do mod")
    m = novo_mundo(ds, "humungousaur", missao="rome_day")
    original_hk = m.hotkeys()
    m.botao(select=True)
    m.vm.avancar(0.25)
    est = m.evento_fase_comeca("bigchill")
    m.quadros(6)
    checa(m.gcur == m.id["bigchill"] and est["pronto"], "a fase ficou no comando (está: %s)" % m.nome_id(m.gcur))
    checa(not verdadeiro(m.g(C.ATIVA)), "o mod não virou Ultimate por cima da fase")
    m.evento_fase_icone(); m.quadros(3)
    m.evento_fase_termina(); m.quadros(6)
    checa(m.hotkeys() == original_hk, "fim do evento: direcional original %s" % [m.nome_id(x) for x in m.hotkeys()])
    checa(not m.travado(), "controles livres")
    sem_erros(m, filtro="fase")

    cenario("A fase chama a função da Ultimate durante a Ultimate do mod (como l_romd)")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.vm.chamar_seguro(m.vm.funcs[C.FUNC_ULT], [None], origem="fase")
    checa(m.g(C.FORMA_ULT) == m.id["humungousaur"], "função original: só marca a pendência da fase")
    m.botao(select=True); m.quadros(5)
    certo = m.vm.globais[h("gformdata")][m.ult_id["humungousaur"]][h("character")]
    checa(m.removidos == [certo], "tirou da memória a Ultimate certa (%s)" % m.removidos)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "saiu e devolveu o direcional")
    sem_erros(m, filtro="fase")

    cenario("Ultimate de um evento da própria fase (não do mod): SELECT não tira")
    m = novo_mundo(ds, "humungousaur")
    m.gcur = m.ult_id["humungousaur"]            # a fase transformou (sem o mod)
    for _ in range(10):
        m.botao(select=True)
    m.quadros(4)
    checa(m.gcur == m.ult_id["humungousaur"], "continua na Ultimate do evento")
    sem_erros(m)

    cenario("Restauração pendente: SELECT como Ben restaura")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.vm.globais[C.ATIVA] = None          # simula monitor perdido
    m.vm.agenda.clear()
    m.gcur = m.id["ben"]
    m.botao(select=True); m.quadros(4)
    checa(m.hotkeys() == original_hk and m.g(C.FORMA_ULT) is None, "SELECT como Ben restaurou")
    sem_erros(m)

    cenario("Morreu na Ultimate do mod (o jogo volta o Ben no checkpoint)")
    m = novo_mundo(ds, "echo")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "echo")
    m.vm.globais[C.MORTO] = True
    m.quadros(3)
    checa(m.gcur == m.ult_id["echo"], "(enquanto morto, nada muda)")
    m.vm.globais[C.MORTO] = None
    m.vm.globais[C.OUTRA_TRAVA] = 1             # 0x4f573077: recarrega o checkpoint
    m.vm.chamar_seguro(m.vm.funcs[C.RESTAURAR_DIRECIONAL], [m.vm.funcs[0xEC66E47C]], origem="jogo")
    m.gcur = m.id["ben"]
    m.quadros(10)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "direcional devolvido depois do checkpoint")
    checa(not m.travado() and m.mod_limpo(), "estado limpo")
    sem_erros(m)

    cenario("Ultimate do mod presa numa interação (sem animação): volta para o Ben sozinha")
    m = novo_mundo(ds, "humungousaur")
    original_hk = m.hotkeys()
    entrar_ultimate(m, "humungousaur")
    m.interagindo = True
    m.quadros_reais(180)
    checa(m.gcur == m.ult_id["humungousaur"], "uma interação de ~6 s (alavanca) não é interrompida")
    m.quadros_reais(140)
    m.quadros(4)
    checa(m.gcur == m.id["ben"] and m.hotkeys() == original_hk, "travou interagindo: voltou para o Ben e devolveu o direcional")
    checa(not m.travado() and m.mod_limpo(), "controles livres, estado limpo")
    sem_erros(m)

    cenario("Ultimate do mod interagindo e andando (empurrando caixa): não interrompe")
    m = novo_mundo(ds, "humungousaur")
    entrar_ultimate(m, "humungousaur")
    m.interagindo = True
    for i in range(300):
        m.pos[0] += 0.05
        m.botao(False); m.vm.avancar(1 / 30.0)
    checa(m.gcur == m.ult_id["humungousaur"], "continua na Ultimate empurrando")
    m.interagindo = False
    m.botao(select=True); m.quadros(5)
    checa(m.gcur == m.id["ben"], "SELECT sai normalmente depois")
    sem_erros(m)

    cenario("Ultimates com as habilidades do alien normal (código real da transformação)")
    for arq, esperado in ((ORIGINAL, False), (ds, True)):
        vm = VM([arq, BASE + "gld_psp.ds"])
        vm.sonda = True
        from simulador import Auto
        vm.globais[h("player")] = Auto("player")
        vm.globais[h("print")] = Nativa("p", lambda *a: None)
        vm.chamar(vm.funcs[h("init_global_variables")], [])
        got = []
        vm.globais[C.APLICA_HABILIDADES] = Nativa("hab", lambda pl, mk: got.append(mk))
        vm.globais[0x326F91F9] = Nativa("efeito", lambda *a: None)
        for fh, mu, mb in C.HABILIDADES_ULTIMATE:
            got.clear()
            try:
                vm.chamar(vm.funcs[fh], [])
            except ErroScript:
                pass
            base = vm.globais.get(mb)
            if esperado:
                checa(got and got[0] == base, "Ultimate %08x recebe as do alien normal (%s)" % (fh, got))
            else:
                checa(got and got[0] == 3137.0, "(jogo original: Ultimate %08x só com o básico)" % fh)
    checa(int(3169) & 32, "Humungossauro Supremo: empurrar caixa (bit 32) incluído")

    falhas = [t for okk, t in RESULTADOS if not okk]
    print("\nRESULTADO: %d verificações, %d falhas" % (len(RESULTADOS), len(falhas)))
    return falhas


def testar_hud_ben(ds_hud, ds_sem):
    """--ben-gigante: segurando o botão de especiais como Ben, a roda desenha os golpes do Gigante."""
    cenario("HUD do Ben com golpes do Gigante (--ben-gigante)")
    for ds, ligado in ((ds_hud, True), (ds_sem, False)):
        m = novo_mundo(ds, "humungousaur")
        m.gcur = m.id["ben"]
        vistos = []
        m.vm.globais[0x8F436AD3] = Nativa("roda", lambda i, a, b: vistos.append((m.gcur, b)))
        for segura in (True, False, True):
            vistos.clear()
            entrada = Obj("input", btn_select=False)
            entrada[C.BOTAO_ESPECIAIS] = segura
            m.vm.chamar_seguro(m.cb_atual, [entrada, None, None], origem="controle")
            esperado = m.id["waybig"] if (ligado and segura) else m.id["ben"]
            checa(vistos and all(x[0] == esperado for x in vistos),
                  "%s, %s: roda vê %s" % ("ligado" if ligado else "desligado",
                                          "segurando" if segura else "solto", m.nome_id(esperado)))
            checa(m.gcur == m.id["ben"], "depois da roda o personagem continua Ben")
    # especiais do Gigante registrados uma vez por "entrada" no Ben
    m = novo_mundo(ds_hud, "humungousaur")
    m.gcur = m.id["ben"]
    m.ataques.clear()
    for _ in range(5):
        m.botao()
    checa(sorted(m.ataques) == sorted(C.ESPECIAIS_BEN), "como Ben: 3 especiais registrados uma vez (%d)" % len(m.ataques))
    m.gcur = m.id["swampfire"]; m.botao(); m.botao()
    checa(len(m.ataques) == 3, "como alien: nada registrado")
    m.gcur = m.id["ben"]; m.botao(); m.botao()
    checa(len(m.ataques) == 6, "voltou a ser Ben: registrados de novo (%d)" % len(m.ataques))
    m2 = novo_mundo(ds_sem, "humungousaur"); m2.gcur = m2.id["ben"]; m2.ataques.clear(); m2.botao()
    checa(not m2.ataques, "sem --ben-gigante: nada registrado")
    # R + SELECT como Ben: Ben gigante (liga/desliga), mantido ao voltar de um alien
    m = novo_mundo(ds_hud, "humungousaur"); m.gcur = m.id["ben"]; m.botao(); m.botao()

    def r_select():
        for sel in (False, True, False):          # segura o R, aperta SELECT, solta
            e = Obj("input", btn_select=sel); e[C.BOTAO_ESPECIAIS] = True
            m.vm.chamar_seguro(m.cb_atual, [e, None, None], origem="controle")
        m.quadros(0.5)
    r_select()
    checa(m.escala == C.ESCALA_BEN, "R + SELECT: Ben gigante (escala %s)" % m.escala)
    checa(m.gcur == m.id["ben"], "continua Ben (não abriu troca nem transformou)")
    m.gcur = m.id["swampfire"]; m.escala = 1.0; m.botao(); m.botao()
    m.gcur = m.id["ben"]; m.escala = 1.0; m.botao(); m.botao()
    checa(m.escala == C.ESCALA_BEN, "voltou a ser Ben: continua gigante (escala %s)" % m.escala)
    r_select()
    checa(m.escala == 1, "R + SELECT de novo: tamanho normal (escala %s)" % m.escala)
    m2 = novo_mundo(ds_sem, "humungousaur"); m2.gcur = m2.id["ben"]
    e = Obj("input", btn_select=True); e[C.BOTAO_ESPECIAIS] = True
    m2.vm.chamar_seguro(m2.cb_atual, [e, None, None], origem="controle"); m2.quadros(0.5)
    checa(m2.escala == 1.0, "sem --ben-gigante: R + SELECT não muda o tamanho")
    # alien normal segurando o botão: nada muda
    m = novo_mundo(ds_hud, "humungousaur")
    vistos = []
    m.vm.globais[0x8F436AD3] = Nativa("roda", lambda i, a, b: vistos.append(m.gcur))
    entrada = Obj("input", btn_select=False); entrada[C.BOTAO_ESPECIAIS] = True
    m.vm.chamar_seguro(m.cb_atual, [entrada, None, None], origem="controle")
    checa(vistos and all(x == m.id["humungousaur"] for x in vistos), "alien normal: roda com os especiais dele")
    return [r for r in RESULTADOS if not r[1]]


def testar_intro(ds):
    """1ª Ultimate de cada alien na fase: animação de transformação; depois, direto."""
    cenario("Animação de transformação na 1ª Ultimate da fase")
    import zlib
    crc = lambda s: zlib.crc32(s.encode())
    m = novo_mundo(ds, "humungousaur")
    m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["humungousaur"], "virou a Ultimate (está: %s)" % m.nome_id(m.gcur))
    # (no simulador, m.id["humongousaur"] é o campo .bigchill da tabela do jogo:
    #  a animação certa é a do Arctiguana)
    checa(crc("bigchill_ult_formchange_in_01") in m.anims, "tocou a transformação do alien")
    checa(crc("ultbigchill_transform_01") in m.anims, "tocou a pose da Ultimate")
    m.quadros(2)
    checa(m.mov_travado == 0, "trava curta da pose acabou: movimento devolvido")
    checa("brilho" in m.log, "brilho na tela")
    checa(not m.travado(), "controles liberados")
    m.botao(select=True); m.quadros(4)
    checa(m.gcur == m.id["ben"], "saiu com SELECT")
    checa(m.mov_travado == 0, "movimento livre depois de sair")
    m.gcur = m.id["humungousaur"]; m.anims.clear()
    m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["humungousaur"] and not m.anims, "2ª vez na mesma fase: sem animação")
    m = novo_mundo(ds, "swampfire"); m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["swampfire"] and not m.anims and m.mov_travado == 0, "Fogo-Fátuo (sem animação): direto")
    # grito do nome: player:playvo_ex(player, falante das Ultimates, "<alien>_name_callout", prioridade, 0)
    falas = []
    for alien, nome_ in (("swampfire", "swampfire"), ("echo", "echoecho"), ("spidermonkey", "spidermonkey")):
        m = novo_mundo(ds, alien)
        falante = Nativa("fala_ult", lambda *a: None)
        m.vm.globais[C.FALA_ULTIMATES] = falante
        m.vm.globais[h("player")][h("playvo_ex")] = Nativa("playvo_ex", lambda *a: falas.append(a))
        falas.clear()
        m.botao(select=True); m.quadros(8)
        checa(len(falas) == 1 and falas[0][1] is falante and falas[0][2] == crc(nome_ + "_name_callout"),
              "%s grita o nome (%d fala)" % (alien, len(falas)))
    m = novo_mundo(ds, "swampfire")
    m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["swampfire"] and not m.vm.erros, "fase sem script de vozes: transforma sem grito e sem erro")
    # sair no meio da pose devolve o movimento na hora
    m = novo_mundo(ds, "spidermonkey"); m.botao(select=True)
    travou = False
    for _ in range(40):
        m.quadros(0.25); travou = travou or m.mov_travado == 1
    checa(travou, "Macaco-Aranha: movimento travado no começo da pose")
    m.botao(select=True); m.quadros(4)
    checa(m.mov_travado == 0 and m.gcur == m.id["ben"], "depois: SELECT volta e o movimento está livre")
    m = novo_mundo(ds, "echo")
    m.botao(select=True); m.quadros(6)
    checa(m.gcur == m.ult_id["echo"] and crc("echo_ult_formchange_in_01") in m.anims
          and crc("ultechoecho_transform_01") in m.anims, "Eco Eco: transformação e pose dele")
    # sem o aviso do fim da animação (callback): o timer de segurança segue
    m = novo_mundo(ds, "spidermonkey")
    m.pessoa[h("playanim")] = Nativa("playanim", lambda *a: None)
    m.botao(select=True); m.quadros(8)
    checa(m.gcur == m.ult_id["spidermonkey"] and not m.travado(), "sem callback: o timer termina a transformação")
    return [r for r in RESULTADOS if not r[1]]


if __name__ == "__main__":
    import io, contextlib
    import tempfile
    saida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "cd_teste_mod.ds")
    rede = "--sem-rede" not in sys.argv
    with contextlib.redirect_stdout(io.StringIO()):
        C.cmd_ultimate_livre(ORIGINAL, saida, rede=rede, habilidades="--sem-habilidades" not in sys.argv, gigante="--sem-gigante" not in sys.argv)
    falhas = testar(saida)
    with contextlib.redirect_stdout(io.StringIO()):
        C.cmd_ultimate_livre(ORIGINAL, saida + ".hud", rede=rede, gigante=True, hud_ben=True)
    falhas_hud = testar_hud_ben(saida + ".hud", saida)
    print("HUD do Ben: %s" % ("ok" if not falhas_hud else "%d falha(s)" % len(falhas_hud)))
    falhas_intro = testar_intro(saida)
    print("Intro: %s" % ("ok" if not falhas_intro else "%d falha(s)" % len(falhas_intro)))
    falhas_hud = falhas_hud + falhas_intro
    sys.exit(1 if (falhas or falhas_hud) else 0)
