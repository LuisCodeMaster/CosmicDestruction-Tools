# Pendências, em ordem

Cada item tem o que já se sabe e o **próximo passo concreto**. Ao terminar um, mova o resultado
para `docs/estado.md` (e para `docs/historico.md`, se houve uma lição).

## Confirmar no jogo (correções já feitas, só falta testar)

1. **Gritos das Ultimates.** O mod chama `player:playvo_ex(player, global 0xE8C0396D, crc("<alien>_name_callout"), global 0xDA9FD054, 0)`
   0,5 s depois da troca. Se não tocar: testar outra prioridade (as fases usam também `0x3240F64B`,
   `0xF62DCABA`, `0x2A9E34CC`) ou chamar do mesmo jeito que as fases, no callback da animação.
2. **Ben gigante (R + SELECT).** Agora o tamanho é reaplicado a cada quadro. Se falhar, descobrir com o
   Luis: não acontece nada, abre a tela de troca, ou cresce e volta?
3. **Pose curta da transformação** (trava de 1,5 s).
4. **Gigante em qualquer fase** com o `g_wayb.psp` completo.

## Humungossauro Supremo

5. **Quebrar parede.** A investida do Humungossauro normal (`shoulder_charge`, marcas `0x55EB4`) tem a
   mesma marca que o varal da Ultimate (`clothesline`). Próximo passo: pedir para o Luis usar o varal
   numa parede rachada (Roma de dia tem `#unique_evtbx_tut_humo_breakable_wall_01`). Se não quebrar,
   passar o `shoulder_charge` do `atk_hm.ddf` para a Ultimate (animações + golpe + registro).
6. **Alavanca.** A animação `pry_01` já foi copiada. Suspeita: o objeto checa o personagem ou uma
   habilidade. Próximo passo: perguntar a fase e procurar o objeto da alavanca no `l_<fase>.ds` e no `archetyp.at`.

## Ferramentas para quem não programa

7. **Tradução para português.** Fonte `Ben10.TTF` tem todos os acentos. O `cd_tool.py`
   (`texto-exportar`/`texto-importar`) já lida com o `psp_us.txt` (1.277 frases, cerca de 12.800 palavras).
   Próximo passo: teste com 10 frases acentuadas no jogo; depois tradução em lotes; ideia de colocar o
   português no lugar do espanhol (`psp_sp.txt`).
8. **Editor de golpes** (`atk_*.ddf` ↔ texto legível).
9. **Descompilador de scripts** (`.ds` → pseudo-Python e de volta).
10. **Configuração em texto** (`mod.ini`) lida pelo `cd_kit.py`.
11. **Exemplos sem arquivos do jogo** (pacote, golpe e banco de voz falsos) para testar as ferramentas sem a ISO.

## Para estudar

12. **`archetyp.at`** (246 KB): provavelmente as definições de inimigos e objetos (paredes, alavancas).
13. **`gtex_s.psp`:** texturas globais, provavelmente o HUD e os ícones.
14. **Malha dos modelos** (blocos 3/4): base para exportar para o Blender e trazer o Rath/Quatro Braços
    (os golpes deles, `atk_ra.ddf`/`atk_fa.ddf`, e as vozes já estão no disco).
15. **Eco Eco para o Ben:** os clones são criados por `spawn_echo_clone` pedindo a um objeto da fase
    (`world:obj(0x0F485776)`); seriam clones do Eco Eco, não do Ben. Conferir antes se o objeto existe.
16. **Vídeos** (25 PMF) e **músicas** (26 AT3).
