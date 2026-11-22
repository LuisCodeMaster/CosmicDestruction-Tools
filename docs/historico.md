# Histórico de decisões (o porquê das coisas)

Cada item conta um problema real, a causa encontrada e a decisão tomada. Antes de "simplificar"
alguma coisa, confira se ela não está aqui.

## Mod Ultimate (globals.ds)

- **Não chamar `loadpreultimateform`.** Em Roma de dia ela chama `0xAEB41139` (manda "start" para
  um objeto da fase) e a fase avança sozinha. O mod faz o mesmo trabalho com o próprio código (`fim_mod`).
- **Não alterar funções do jogo usadas em outros lugares.** A primeira versão sobrescrevia callbacks
  do `ai_globl.ddf`, do `g_ec.psp`, do `l_romn` e funções que o EBOOT chama (`0x74879A8A`, mostrar/esconder
  o HUD; `0x95B12E77`). Isso quebrava eventos e travava o jogo. Hoje só se acrescentam funções novas
  (`luis_f_*`) e cópias modificadas de poucas funções.
- **`FUNC_ULT` fica original.** As fases usam essa função nos eventos de Ultimate; mexer nela quebrava as fases.
- **Booleano não é número.** A instrução 02 cria booleano; somar ou comparar dá erro silencioso e o
  resultado não é gravado. Contadores usam números (03).
- **Interação presa:** sem as animações de interação, a Ultimate ficava parada para sempre. Primeiro foi
  criada uma saída automática (volta para o Ben); com as animações copiadas, o limite passou de 2,5 s
  para 10 s, para não cortar uma alavanca de verdade.

## Animações

- **Índices das trilhas são a posição na TABELA do bloco 9**, não a ordem dos dados. Ao acrescentar
  trilhas, a tabela é reordenada e todos os cabeçalhos são renumerados.
- **Copiar rotações cruas deixava o Ben deitado no chão.** Cada esqueleto tem eixos diferentes em cada
  osso, e as poses de montagem são diferentes (Ben em "T", Gigante com os braços para baixo). Solução:
  redirecionar em espaço de mundo, com correção de postura (`redirecionar.py`).
- **Os quatérnios estão guardados conjugados.** Descoberto desenhando o esqueleto: só com essa leitura
  a pose de montagem do Ben fica em "T" e as animações dele ficam naturais.
- **Tempos absolutos:** a cotovelada do Gigante começa no quadro 30; sem "puxar" para o zero, havia uma pausa antes do golpe.
- **Ossos sem par** precisam de trilhas de uma chave só; usar o `idle_01` animado esticava a duração do golpe para 2 s.
- **Velocidade:** os golpes do Gigante são lentos no Ben; cada um tem um fator (1,3 a 2,0).

## Gigante

- **Fora da fase final o Gigante travava** (PC 0x08940AB0, laço dos ossos). O esqueleto dele só existe
  em `l_tokd/l_tokd.psp`, o pacote da fase final. Solução: montar um `global/g_wayb.psp` com modelo,
  esqueleto e todas as animações (`cd_anims --gigante`).

## Ben com golpes do Gigante

- **O jogo escolhe o golpe do Ben por botão e situação**, não por um combo fixo. O chute voador estava num
  golpe pouco usado e "não aparecia"; foi para o quadrado parado.
- **Especiais travavam o jogo** quando copiados inteiros do Gigante (referências a efeitos que só existem
  com ele carregado). Partindo de um golpe do Ben, não travavam, mas não saíam.
- **Campos 36/37 do golpe = qual upgrade libera o golpe.** Cada especial aparece três vezes (um por
  nível de upgrade). Os do Gigante pediam upgrades que o Ben nunca tem. Solução: base do Ben, campos 36/37
  "sempre liberado" do Ben, e do Gigante só o dano, os tempos, a marca de especial e o botão (campo 40).
- **A roda só desenha os especiais quando o personagem não é o Ben.** O mod faz o jogo "achar" que é o
  Gigante só durante o desenho da roda e volta para o Ben em seguida.
- **R + SELECT:** a função do SELECT não recebe o controle (o jogo passa nil). O estado do R é guardado pela roda no quadro anterior.

## Vozes

- **Os nomes no banco FSB4 têm só 30 bytes** (cortados) e alguns se repetem; a ordem não é alfabética.
  Amostras novas vão sempre no fim, para não mudar a posição das antigas.
- **A fala vem do script da fase** (`vo_<fase>.ds`, função `0xE8C0396D`), que diz qual amostra tocar
  para cada tipo de fala. O mod acrescenta os cinco gritos nessa função.
- **O jogo não grita sozinho** quando a Ultimate aparece pelo mod (só nos eventos). O mod chama
  `player:playvo_ex` meio segundo depois da troca.

## Testes no jogo

- Arquivo baixado de novo vira `nome(1).py` e o comando roda o antigo: isso já causou "não mudou nada" duas vezes.
- A pasta de saída de um comando pode não existir (`mkdir -p` antes), e aí a ISO sai sem o script.
