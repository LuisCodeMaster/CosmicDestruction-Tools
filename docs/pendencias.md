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

7. **Tradução para português (feita em 22/11/2026).** As 1.277 frases do `psp_us.txt` foram traduzidas
   (`traducao_pt.txt`, fica só com o Luis: deriva do texto do jogo, não vai para o GitHub). Teste de acentos
   confirmado no jogo. Falta: conferir no jogo textos cortados nos menus e o tempo das legendas.
   Nomes usados: Humungossauro, Friagem, Fogo Fátuo, Eco Eco, Macaco-Aranha, Tartagira, Quatro Braços,
   Gigante, Supremo; Water Hazard, Armodrillo, AmpFibian, NRG e Rath sem mudança. `trocar_nome.py` troca um nome.
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

## Vilgax Attacks (ULUS-10488)

16. **Mesmo motor do Cosmic.** Pacote ARCV decifrado (`cd_arcv.py`), scripts no mesmo formato, CARC entendido
    (pedaços LZSS que sobrescrevem partes de outros arquivos). Detalhes em `docs/formatos.md`.
17. **Alien X:** não existe jogável no jogo (só nas legendas da cena final, que é vídeo). Caminho possível:
    montar um a partir de outro alien (falta trocar textura nos `.psp`).
18. **Tradução do Vilgax (feita e testada no jogo em 24/11/2026).** `cd_arcv.py --colocar` grava arquivos numa
    cópia da ISO, no espaço que cada um já ocupa no pacote. As 599 frases foram traduzidas
    (`traducao_vilgax_pt.txt`, fica só com o Luis) e vão no arquivo do espanhol (`_sem_nome/7ceedc78.bin`).
    O jogo escolhe o idioma pelo sistema: no PPSSPP, Configurações > Sistema > Idioma do jogo = Español.
    Falta: conferir acentos (ã õ ç â ê ô) e textos cortados; opção de tradução num kit do Vilgax; talvez
    colocar também no lugar do inglês (cuidado com a cópia comprimida do inglês no CARC 66a3111e).
19. Notas antigas sobre o reempacotador: reempacotador do ARCV + teste simples (trocar uma legenda). As legendas são 4 arquivos sem
    nome, um por idioma (inglês `817ba211`, francês `d89cdc3b`, italiano `c14a1a6d`, espanhol `7ceedc78`), e há uma
    cópia comprimida do inglês dentro de um CARC (`66a3111e`) que pode sobrepor a tradução.
