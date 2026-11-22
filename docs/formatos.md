# Formatos do Ben 10 Ultimate Alien: Cosmic Destruction (PSP, ULUS-10542)

Este documento reúne tudo o que foi descoberto sobre os arquivos do jogo durante o
desenvolvimento do mod. A ideia é que qualquer pessoa (inclusive você daqui a um ano)
consiga entender, corrigir e continuar o projeto sem precisar redescobrir nada.

Convenções usadas aqui:

- Todos os números do jogo são **little-endian** (o byte menos significativo vem primeiro).
- `u8`, `u16`, `u32` = inteiros sem sinal de 1, 2 e 4 bytes; `f32` = número de ponto flutuante de 4 bytes.
- "+0x48" = posição (deslocamento) em bytes a partir do começo do bloco.
- Hashes são sempre **CRC32 do nome em minúsculas** (`zlib.crc32(b"nome")` no Python),
  a menos que o texto diga outra coisa.

---

## Sumário

1. [Ferramentas do kit](#1-ferramentas-do-kit)
2. [A ISO](#2-a-iso)
3. [Hashes e nomes](#3-hashes-e-nomes)
4. [Scripts compilados (.ds)](#4-scripts-compilados-ds)
5. [Pacotes (.psp, formato "spav")](#5-pacotes-psp-formato-spav)
6. [Animações (blocos 13 e 9)](#6-animações-blocos-13-e-9)
7. [Esqueleto (bloco 12)](#7-esqueleto-bloco-12)
8. [Redirecionar animação entre esqueletos](#8-redirecionar-animação-entre-esqueletos)
9. [Golpes (atk_*.ddf)](#9-golpes-atk_ddf)
10. [Vozes (vo_eng.psp e vo_*.ds)](#10-vozes-vo_engpsp-e-vo_ds)
11. [Coisas do jogo usadas pelo mod](#11-coisas-do-jogo-usadas-pelo-mod)
12. [Como testar e não se perder](#12-como-testar-e-não-se-perder)
13. [Armadilhas conhecidas](#13-armadilhas-conhecidas)

---

## 1. Ferramentas do kit

| Arquivo | O que faz |
|---|---|
| `cd_kit.py` | Menu que junta tudo: extrai da ISO, monta cada parte do mod e gera a ISO nova |
| `instalar_mod.py` | Instalador simples só do mod Ultimate (ISO/CSO → ISO nova) |
| `cd_analisador.py` | Lista e extrai arquivos da ISO/CSO (`--extrair PASTA --so "padrão" ...`) |
| `cd_iso.py` | Coloca arquivos modificados numa cópia da ISO (no lugar ou no fim) |
| `cd_scripts.py` | Desmonta scripts `.ds` em texto e aplica o mod Ultimate no `globals.ds` |
| `cd_anims.py` | Lê/grava pacotes, copia animações entre personagens, monta o Gigante e o Ben |
| `cd_vozes.py` | Junta os gritos das Ultimates nos bancos de voz e scripts de voz das fases |

Nenhuma ferramenta precisa de bibliotecas de fora: só Python 3.8+.

---

## 2. A ISO

- Formato ISO 9660 comum, setores de **2048 bytes**.
- O CSO é a mesma ISO comprimida em blocos (zlib/deflate cru); o `cd_iso.py` descomprime.
- Estrutura que importa:

```
PSP_GAME/USRDIR/
  global/            coisas que todas as fases usam
    scripts/         globals.ds (cérebro do jogo), atk_*.ddf (golpes), char.ddf...
    g_*.psp          um pacote por alien (g_hm = Humungossauro, g_uhm = Ultimate...)
    a_plyr.psp       animações do Ben humano
    vo/vo_eng.psp    vozes dos menus
  l_<fase>/          uma pasta por fase (romd, romn, chin, mili, pari, rush, tokd, tokn)
    scripts/         l_<fase>.ds (eventos), vo_<fase>.ds (falas)
    vo/vo_eng.psp    banco de vozes da fase
    a_plyr.psp       cópia das animações do Ben (idêntica à global)
    l_<fase>.psp     pacote da fase (cenário, e na tokd os esqueletos do Gigante e do Ben)
```

**Trocar um arquivo na ISO** (`cd_iso.py`): no registro de diretório de cada arquivo há
o setor inicial (+2) e o tamanho (+10), cada um gravado duas vezes (little e big-endian).
Se o arquivo novo couber no espaço do antigo, vai no mesmo lugar; senão vai para o fim da
ISO, e o tamanho total do volume (setor 16, +80) é atualizado.

---

## 3. Hashes e nomes

Quase tudo é identificado por `crc32(nome)`:

| Onde | Como o hash é formado | Exemplo |
|---|---|---|
| Nomes nos scripts (globais, campos) | `crc32("gcurrentcharacter")` | |
| Animação num pacote | `crc32(prefixo + "_" + nome)` | `crc32("humongousaur_interact_01")` |
| Golpe → animação | o mesmo hash da animação | campo 8 do golpe |
| Fala | `crc32(nome da amostra sem .wav)` | `crc32("ult_humongousaur_name_callout_01")` |
| Tipo de fala | `crc32(alien + "_name_callout")` | |

**Prefixos de animação:** humongousaur, ulthumong, spidermonkey, ultspidermonkey, bigchill,
ultbigchill, echo, ultechoecho, swampfire, ultswampfire, waybig, ben.

**Tabela de personagens** (`0xE1003DC4()` devolve uma tabela cujos campos são os ids):
`ben`, `spidermonkey`, `echo`, `swampfire`, `terraspin`, `humongousaur` (0xE201C289),
`bigchill` (0x1679657D), `ult_humongousaur` (0x0AA213A1)...

> Cuidado: o nome do campo nem sempre é o que parece. Confira no `globals.ds` desmontado
> qual campo cada `gformdata[...]` usa antes de confiar.

O `cd_scripts.py gerar-nomes` cria `cd_nomes.txt` a partir do EBOOT e dos arquivos do jogo,
para a desmontagem mostrar nomes em vez de números.

---

## 4. Scripts compilados (.ds)

Uma máquina virtual de registradores (`r0`, `r1`...). Cada função tem seus próprios registradores.

### Estrutura do arquivo

```
+0x00  u32  magic 0x1BADBABE (bytes BE BA AD 1B)
+0x04  u32  número de funções (+1 para a inicialização)
+0x10  u32  tamanho, em palavras, do código de inicialização
+0x14       código de inicialização
...         funções, uma atrás da outra:
            u32 0x21 | u32 hash do nome | u32 nº de parâmetros | u32 nº de palavras | código
```

Ao carregar, o jogo registra cada função pelo hash. **Se duas funções tiverem o mesmo
hash, a última vence.** É assim que o mod funciona: ele não altera nada do original, só
acrescenta funções no fim (as novas, mais cópias modificadas de algumas do jogo) e soma
o contador em +0x04.

### Instruções

Cada instrução tem 4 bytes `[op][a][b][c]`, às vezes seguidos de palavras extras
(o `imm`, valores de 4 bytes embutidos).

| op | Efeito | Extras |
|---|---|---|
| 01 | `r[a] = nil` | |
| 02 | `r[a] = falso/verdadeiro (b)` (booleano: **não serve para contas**) | |
| 03 | `r[a] = número` (float; o único tipo usado em contas e comparações) | 1 (float) |
| 04 | `r[a] = "texto"` (texto embutido, completado até múltiplo de 4) | texto |
| 05 | `r[a] = constante` (hash) | 1 |
| 06 | `r[b] = r[a]` | |
| 07 | `r[a] = global[h]` | 1 (hash) |
| 08 | `global[h] = r[a]` | 1 (hash) |
| 0A / 0B | `r[c] = r[a] + r[b]` / `r[a] - r[b]` | |
| 0F | `r[b] = not r[a]` | |
| 10 / 11 | `r[c] = (r[a] == r[b])` / `!=` | |
| 12 / 13 | `r[c] = r[a] < r[b]` / `>` | |
| 14 / 15 | `and` / `or` | |
| 16 | `r[a] = {}` (tabela nova) | |
| 17 | `r[b] = r[a].campo` | 1 (hash) |
| 18 | `r[c] = r[a][r[b]]` | |
| 19 | `r[a].campo = r[b]` | 1 (hash) |
| 1A | `r[a][r[b]] = r[c]` | |
| 1D | pula para a palavra `a + b*256` | |
| 1E | se `r[a]` verdadeiro, pula para `b + c*256` | |
| 1F | se `r[a]` falso, pula para `b + c*256` | |
| 20 | `r[imm] = r[a](r[b], r[b+1], ... c argumentos)` | 1 (registrador de retorno) |
| 21 | fim da função (retorna nada) | |
| 22 | retorna `r[a]` | |

Os destinos dos saltos contam **palavras de 4 bytes desde o começo da função**. Ao
copiar código para dentro de outra função, some o deslocamento a todos os saltos
(`cd_scripts.realocar`).

**Métodos de objetos** são chamados como `obj.metodo(obj, ...)`: pega o campo (17) e
chama passando o próprio objeto como primeiro argumento. Exemplo, `player:person()`:

```
r28 = global player ; r25 = global player ; r3 = r25.person ; r20 = r3(r28)
```

### Desmontar para estudar

```
python cd_scripts.py desmontar globals.ds globals.txt --nomes cd_nomes.txt
```

---

## 5. Pacotes (.psp, formato "spav")

Contêineres com tabela de hash. Um bloco pode conter outros blocos (a mesma estrutura dentro).

### Cabeçalho (16 palavras u32)

| Palavra | Conteúdo |
|---|---|
| 0 | `"spav"` |
| 3 | `0x4000A`: o **A** é o alinhamento dos dados (2^A bytes) |
| 4 | tamanho dos dados |
| 7 | tamanho do cabeçalho + tabela |
| 8 | **cap** = número de "baldes" da tabela de hash |
| 11 | posição da tabela − 0x20 |

A tabela começa em +0x40. Cada entrada tem `[hash][tamanho | flags<<24][posição]`.
As entradas ficam **ordenadas por `hash % cap`** (os "baldes").

> Ao acrescentar entradas, a ordem da tabela muda. Se outra coisa aponta para
> entradas **pelo número da posição** (como as animações apontam para as trilhas),
> tudo precisa ser renumerado. O `spav.py`/`cd_anims.py` faz isso.

### Tipos de bloco (a "chave" de cada entrada no nível de cima)

| Tipo | Conteúdo |
|---|---|
| 0 | texturas |
| 3, 4 | malha (modelo 3D) |
| 9 | trilhas de animação (as curvas de cada osso) |
| 12 | esqueleto(s) |
| 13 | cabeçalhos de animação |
| 14, 22, 24 | outros (anexos, colisão, efeitos; pouco estudados) |

**Ler e regravar sem estragar:** o `spav.py` (embutido no `cd_anims.py`) lê e grava de
volta **byte a byte igual** em todos os 68 pacotes testados. Blocos não alterados são
copiados como estavam; só os alterados são remontados.

---

## 6. Animações (blocos 13 e 9)

### Cabeçalho da animação (entrada do bloco 13)

O hash da entrada é `crc32(prefixo + "_" + nome)`.

| Posição | Conteúdo |
|---|---|
| +0x00 | nome (texto, até 0x48 bytes) |
| +0x48, +0x4C | número de ossos (repetido) |
| +0x50 | índice da trilha de **eventos** no bloco 9 (−1 = nenhuma) |
| +0x54 | hash do esqueleto |
| +0x58 | 64 × u16: ids dos ossos, na ordem do esqueleto |
| +0xD8 | para cada osso: 3 × u32 = índices no bloco 9 de **translação, rotação, escala** (−1 = sem trilha) |

Tamanho total = 0x58 + 128 + 12 × nº de ossos. Os índices são **a posição na tabela do bloco 9**,
não a ordem dos dados.

### Trilhas (entradas do bloco 9)

Começam com `u16 tipo, u16 tipo/variante, u16 n, u16 n` e depois `n` chaves:

| Tipo | Uso | Chave |
|---|---|---|
| 0x0401 | translação | 16 bytes: `f32 tempo, f32 x, y, z` |
| 0x0210 | rotação | 8 bytes: `i16 x, y, z (/32767), i8 w (/127), u8 quadro` |
| 0x040C | escala | 16 bytes: `f32 tempo, f32 x, y, z` |
| 0x090A | eventos | 36 bytes: `f32 tempo` + 32 bytes de marcas (que parte do corpo acerta, passos, sons...) |
| 0x030B | rotação em outro formato (algumas Ultimates; não decodificado) | |

- **Tempo:** 1 quadro = **160 tiques**. As rotações guardam o número do quadro num byte.
- **Tempos absolutos:** os tempos são do clipe original. Por exemplo, a cotovelada do
  Gigante vai do quadro 30 ao 38 e a volta (`_out`) do 39 ao 60. Ao copiar, é bom
  "puxar" para começar no zero (`deslocar`).
- **Quaternião:** x, y, z guardam a precisão; o `w` do byte é só aproximado. Na leitura,
  `w = ±sqrt(1 − x² − y² − z²)` com o sinal do byte. **Os quatérnios estão guardados
  conjugados** (inversos): desconjugue para fazer contas e conjugue de volta para gravar.
- Trilhas iguais são reaproveitadas (por exemplo, "escala 1,1,1" é uma trilha só, usada por vários ossos).

### Duração e velocidade

Para acelerar uma animação, divida todos os tempos (rotação: o byte do quadro; translação,
escala e eventos: o float). Veja `acelerar_trilha` no `cd_anims.py`.

---

## 7. Esqueleto (bloco 12)

```
+0x00  u16 n ossos, u16 n, u8, u8, u16
+0x08  u32 hash do esqueleto (o mesmo de +0x54 das animações)
+0x0C  n registros de 44 bytes:
         f32 quaternião x, y, z, w   (pose de montagem, conjugado)
         f32 translação x, y, z
         f32 escala x, y, z
         u8 pai (0xFF = raiz), u8, u16 id do osso
```

- **Ids de osso são globais:** 0 é a raiz, 31 o quadril, 32/33 a coluna, e assim por diante.
  Personagens diferentes compartilham ids para as partes iguais. É isso que permite
  copiar animações entre eles (o Humungossauro e o Ben têm 47 ossos em comum).
- **Pose de montagem:** o Ben é montado em pose de "T" (braços abertos); o Gigante, com os braços para baixo.
- **Onde ficam os esqueletos:** cada alien tem o seu no próprio `g_*.psp`. Os do **Gigante**
  e do **Ben** ficam no pacote da **fase final** (`l_tokd/l_tokd.psp`). Por isso o Gigante
  travava fora dessa fase: o modelo carregava sem esqueleto.

---

## 8. Redirecionar animação entre esqueletos

Copiar as rotações cruas não funciona: cada osso tem os eixos virados para um lado em cada
personagem. Foi por isso que, no primeiro teste, o Ben ficou deitado no chão.

O método (`redirecionar.py`, embutido no `cd_anims.py`):

1. Para cada quadro, monta a orientação **no mundo** de cada osso da origem (multiplicando pelos pais).
2. Calcula o quanto cada osso girou em relação à pose de montagem da origem.
3. Aplica esse giro sobre a pose de montagem do destino, com uma correção (`arco`) que
   alinha a direção do osso entre as duas poses (T × braços para baixo).
4. Volta para rotação **local** (dividindo pelo pai) e grava.
5. **Translação:** ossos parados usam a medida do destino; ossos que se movem (quadril)
   têm o deslocamento convertido para o espaço do pai do destino e reescalado pela
   proporção de tamanho entre os personagens.
6. Ossos sem par no destino (por exemplo, dedos) ficam parados na primeira pose do `idle_01`.
7. Remove chaves que a interpolação já reproduz (erro < ~0,6°) para economizar memória.

**Teste de controle:** redirecionar uma animação de um personagem para ele mesmo tem que
devolver a mesma animação (erro máximo 0,3°). Se isso falhar, o problema está no método.

---

## 9. Golpes (atk_*.ddf)

```
+0x00  u32 magic 0x1BADBABE
+0x04  registros de 224 bytes, um atrás do outro (a quantidade vem do tamanho do arquivo)
```

Um arquivo por personagem: `atk_bn` (Ben), `atk_hm` (Humungossauro), `atk_uh` (Ultimate
Humungossauro), `atk_wb` (Gigante), `atk_fa` (**Quatro Braços**) e `atk_ra` (**Rath**).
Os dois últimos são restos de personagens cortados da versão de PSP.

### Campos conhecidos (cada um com 4 bytes; o número é o índice do campo)

| Campo | Conteúdo |
|---|---|
| 0 | id do golpe (hash) |
| 1 | tipo do registro (`attackdefinition`) |
| 2 | dono (o mesmo para todos os golpes de um arquivo) |
| 4 | parece um endereço de memória (não copiar entre arquivos) |
| 8 | animação do golpe (hash) |
| 9 | animação de volta (`_out`, ou 0) |
| 12–23 | floats: dano, alcance, tempos (o 13 parece ser o dano) |
| 25 | marcas. `0x40000` = especial; `0x10000`/`0x4000` aparecem nas investidas |
| 36, 37 | **qual melhoria (upgrade) libera o golpe**. Golpes normais usam `0x8D0FBAAB, 0xFFF06ADF` ("sempre liberado") |
| 38 | grupo/tipo |
| 40 | **botão do especial** (cada especial de um personagem tem um valor diferente) |
| 41 | parte do corpo que acerta (mão direita/esquerda, cabeça...) |
| 44+ | lista de efeitos (atordoar, derrubar, empurrar) |

- **Três níveis por especial:** cada especial aparece três vezes no arquivo, com campos
  36/37 diferentes, um por nível de melhoria. Copiar um especial com os 36/37 de outro
  personagem deixa o golpe bloqueado, porque a melhoria nunca é comprada.
- **Registro dos golpes:** o jogo registra os golpes com `player:addstartattack(player, id)`
  toda vez que troca de forma (o script do Ben e de cada alien faz isso). Golpes novos
  precisam ser registrados do mesmo jeito.

---

## 10. Vozes (vo_eng.psp e vo_*.ds)

### Banco de vozes: FMOD FSB4

```
+0x00  "FSB4", u32 nº de amostras, u32 tamanho dos cabeçalhos, u32 tamanho dos dados,
       u32 versão (0x40000), u32 modo, 8 bytes zero, 16 bytes de hash
+0x30  cabeçalhos das amostras (80 bytes cada): u16 tamanho, nome (30 bytes, CORTADO),
       u32 amostras, u32 tamanho comprimido (+36), laços, modo, frequência, canais...
       depois os dados de cada amostra, cada um alinhado em 32 bytes
```

- **Nomes não são únicos nem ordenados:** como o campo do nome tem 30 bytes, nomes longos
  são cortados e alguns se repetem. Por isso amostras novas vão **sempre no fim**, para
  não mudar a posição das que já existem.

### Script de vozes da fase (vo_<fase>.ds)

Cada "falante" é uma função que recebe o tipo de fala e devolve qual amostra tocar:

```
função 0xe8c0396d (Ultimates):
  se tipo == crc32("humongousaur_name_callout") devolve crc32("ult_humongousaur_name_callout_01")
  se tipo == ... (derrota) devolve uma de duas, ao acaso
```

Na transformação, o jogo liga a Ultimate a essa função (`person:setvolookup`). Uma fala é
tocada com `player:playvo_ex(player, falante, tipo, prioridade, 0)`.

**Gritos das Ultimates:** cada fase só tinha o da Ultimate do evento dela. O `cd_vozes.py`
põe as cinco amostras em todos os bancos e acrescenta os cinco casos na função 0xe8c0396d
(como uma função nova no fim do script: a última vence).

---

## 11. Coisas do jogo usadas pelo mod

| Nome / hash | O que é |
|---|---|
| `gcurrentcharacter` | id do personagem atual |
| `gformdata[id]` | dados de cada forma (pacote, golpes, especiais da roda, Ultimate) |
| `switch_form_update` | lê os botões e troca de forma a cada quadro (o mod troca o SELECT e a roda) |
| `0x8F436AD3` | desenha a roda do canto (aliens ou especiais) |
| `btn_r1_cur` (0x643CCFE7) | R segurado (mostra os especiais na roda) |
| `switch_to_ultimate` | troca para a Ultimate (o mod chama a mesma coisa que os eventos) |
| `0x65661824(player, máscara)` | habilidades: 1 pular, 32 empurrar caixa, 64 correr, 128 planar, 1024 atacar, 2048 defender, 4096 teia |
| `playermgr:lockmovement/unlockmovement` | trava e destrava o movimento (usado na pose) |
| `person:playanim(person, hash, voltas, ?, callback)` | toca uma animação, com aviso no fim |
| `person:setscale(person, valor)` | tamanho do personagem |
| `overlay:setgloweffect(3, 1, 0)` | brilho da tela na transformação |
| `missionmgr:getcurrentmission()` | fase atual (usado para "1ª vez nesta fase") |

---

## 12. Como testar e não se perder

1. **Uma mudança por vez.** Se mudar três coisas e travar, você não sabe qual foi.
2. **Testes de diagnóstico:** quando não souber a causa, monte uma versão em que cada
   parte testa uma hipótese (como o combo do Ben com um golpe diferente em cada parte).
3. **Compare com o original:** confira byte a byte que o que você não quis mexer
   continua igual. As ferramentas fazem isso sozinhas sempre que podem.
4. **Simulador:** o simulador da máquina dos scripts (`simulador.py` + `testes.py`) roda
   o `globals.ds` com o mod fora do jogo. Ele pega muito erro antes de você abrir o PPSSPP.
5. **Desenhe:** para animações, desenhar o esqueleto em "bonecos de palito" (matplotlib)
   mostra na hora se a pose está certa.
6. **Anote no GitHub:** cada descoberta nova vai para este arquivo, e cada versão do mod ganha uma linha no changelog.

---

## 13. Armadilhas conhecidas

- **Arquivo baixado de novo vira `nome(1).py`:** o comando continua usando o antigo. Apague
  o velho antes de baixar, ou renomeie.
- **Save state do PPSSPP** guarda a memória inteira, incluindo os scripts antigos. Teste
  sempre carregando o save do próprio jogo.
- **Nunca altere funções que o jogo usa em outros lugares** (callbacks de IA, de fase, as
  do EBOOT): faça uma cópia modificada com um nome novo, ou só acrescente.
- **Booleano não é número:** contas com o valor da instrução 02 dão erro silencioso. Use números (03).
- **Os nomes dos campos da tabela de personagens** podem enganar. Confira no script desmontado.
- **Não publique arquivos do jogo** no GitHub (ISO, EBOOT, `.ds`, `.psp`, `.ddf`, saves, `cd_nomes.txt`).
  As ferramentas sempre trabalham com a cópia de quem está usando.
