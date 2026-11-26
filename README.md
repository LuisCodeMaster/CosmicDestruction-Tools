# CosmicDestruction-Tools

Kit de modding para **Ben 10 Ultimate Alien: Cosmic Destruction**, feito em Python puro.
Funciona no **PC** (Windows, Linux, Mac) e no **celular Android** (Termux).

Com ele você pode, por exemplo:

- virar a **forma Ultimate a qualquer momento**, e não só nos eventos das fases;
- deixar o **jogo em português**;
- fazer as Ultimates **gritarem o próprio nome** em qualquer fase;
- e, no PSP, jogar com o **Gigante (Way Big)** e dar ao **Ben os golpes do Gigante**.

> **Projeto de fã, não oficial.** Este repositório **não contém nenhum arquivo do jogo nem as
> traduções prontas**. As ferramentas trabalham sobre a **sua própria cópia** do jogo, e a sua
> ISO original **nunca é alterada**: o kit sempre cria uma cópia nova.

---

## Índice

1. [Qual versão do jogo você tem?](#1-qual-versão-do-jogo-você-tem)
2. [Antes de começar (só uma vez)](#2-antes-de-começar-só-uma-vez)
3. [PSP no PC](#3-psp-no-pc)
4. [PSP no celular (Termux)](#4-psp-no-celular-termux)
5. [Xbox 360 (Xenia)](#5-xbox-360-xenia)
6. [Jogo em português](#6-jogo-em-português)
7. [Como usar o mod no jogo](#7-como-usar-o-mod-no-jogo)
8. [Problemas comuns](#8-problemas-comuns)
9. [Todas as ferramentas](#9-todas-as-ferramentas)
10. [Para quem quer mexer no código](#10-para-quem-quer-mexer-no-código)

---

## 1. Qual versão do jogo você tem?

| Versão | O que o kit faz | Programa principal | Emulador |
|---|---|---|---|
| **PSP** (americana, ULUS-10542) | mod completo: Ultimate, interações, Gigante, Ben com golpes, gritos, tradução | `cd_kit.py` | PPSSPP |
| **Xbox 360** | tradução, Ultimate no R3, gritos (experimental) | `cd_kit360.py` | Xenia Canary |
| **PS3** | só tradução e análise (os scripts do PS3 são criptografados) | `cd_ps3.py` | RPCS3 |
| **Ben 10 Alien Force: Vilgax Attacks** (PSP) | tradução | `cd_arcv.py` | PPSSPP |

O que cada parte faz, e o que já foi testado no jogo, está em [docs/estado.md](docs/estado.md).

---

## 2. Antes de começar (só uma vez)

### 2.1 Instalar o Python

- **Windows:** baixe em [python.org/downloads](https://www.python.org/downloads/) e, na
  instalação, **marque a caixa "Add Python to PATH"**. Para conferir, abra o PowerShell e digite
  `python --version`: deve aparecer `Python 3.x`.
- **Android:** veja o [passo 4](#4-psp-no-celular-termux).
- **Linux/Mac:** normalmente já vem instalado (use `python3` no lugar de `python`).

O kit precisa só do Python 3.8 ou mais novo. **Não precisa instalar mais nada.**

### 2.2 Baixar o kit

1. No topo desta página, clique no botão verde **Code** e depois em **Download ZIP**.
2. Extraia o ZIP numa pasta. Exemplo: `C:\Ben10Mod`.
3. Coloque a **ISO do seu jogo** dentro dessa mesma pasta.

A pasta deve ficar mais ou menos assim:

```
C:\Ben10Mod\
    cd_kit.py
    cd_kit360.py
    cd_scripts.py
    ... (os outros .py)
    Ben 10 - Ultimate Alien - Cosmic Destruction (USA).iso
```

### 2.3 Abrir o terminal na pasta

- **Windows:** abra a pasta no Explorador, clique na barra de endereço, digite `powershell` e
  aperte Enter. O PowerShell abre já dentro da pasta.
- **Linux/Mac:** abra o terminal e use `cd` até a pasta.

---

## 3. PSP no PC

### Passo a passo

1. Abra o terminal na pasta do kit (passo 2.3).
2. Rode:

   ```
   python cd_kit.py
   ```

   O kit acha a ISO na pasta sozinho. Se tiver mais de uma, ele pergunta qual usar.
   Também dá para passar o nome: `python cd_kit.py "Ben 10 - Ultimate Alien - Cosmic Destruction (USA).iso"`.

3. Aparece o menu:

   ```
   === O que vai no mod? ===
     1) [x] Ultimate a qualquer momento (SELECT)
     2) [x] Ultimates interagindo com o cenário (caixas, beiradas...)
     3) [x] Animação de transformação na 1ª Ultimate de cada fase
     4) [x] Ultimates gritando o nome em todas as fases
     5) [ ] Tartagira + SELECT vira o Gigante (experimental)
     6) [ ] Ben com os golpes do Gigante (...)
     7) [ ] Jogo em português (...)
     M) montar a ISO   L) limpar arquivos de trabalho   S) sair
   ```

   - Digite o **número** de uma opção e aperte Enter para ligar `[x]` ou desligar `[ ]`.
   - Digite **M** para montar.

4. O kit extrai da sua ISO só o que precisa (para a pasta `cd_trabalho/`), monta o mod e cria
   uma ISO nova: **`nome do jogo (Mod).iso`**.
5. Abra a ISO nova no **PPSSPP**.

### Só quero o mod da Ultimate, do jeito mais simples

```
python instalar_mod.py
```

Ele acha o jogo, confere se é a versão americana (ULUS-10542) e cria
`nome do jogo (Ultimate Mod).iso`.

---

## 4. PSP no celular (Termux)

1. Instale o **Termux** pelo [F-Droid](https://f-droid.org/packages/com.termux/). A versão da
   Play Store é antiga.
2. Abra o Termux e rode, uma linha de cada vez:

   ```
   pkg install python
   termux-setup-storage
   ```

   O segundo comando pede permissão para acessar os arquivos: aceite.
3. Coloque os arquivos do kit e a ISO numa pasta do celular. Exemplo: `Ben 10 Mod`.
4. No Termux, entre na pasta e rode o kit:

   ```
   cd "/sdcard/Ben 10 Mod"
   python cd_kit.py
   ```

5. Use o menu igual ao do [passo 3](#3-psp-no-pc). A ISO nova aparece na mesma pasta; abra no PPSSPP.

---

## 5. Xbox 360 (Xenia)

No Xbox 360 o emulador **Xenia** roda o jogo direto de uma **pasta extraída** (o arquivo
`default.xex` dentro dela). Por isso o kit do 360 **aplica o mod na pasta**, em vez de criar outra ISO.

### Passo a passo

1. Coloque a ISO do 360 na pasta do kit e abra o terminal nela (passo 2.3).
2. Rode, trocando `C:\Ben10_360` pelo lugar onde o jogo vai ficar:

   ```
   python cd_kit360.py "Ben 10 - Ultimate Alien - Cosmic Destruction (USA).iso" "C:\Ben10_360"
   ```

3. Na primeira vez:
   - o kit guarda os **arquivos originais** que ele mexe em `cd_trabalho360/originais`;
   - se a pasta do jogo ainda não existir, ele pergunta se pode **extrair a ISO inteira** para
     ela (uns 7 GB; demora alguns minutos).
4. Aparece o menu:

   ```
   1 [X] Jogo em português                      (testado: funciona)
   2 [X] Ultimate a qualquer momento (R3)       (em teste)
   3 [ ] Ultimates com as habilidades do alien normal
   4 [ ] Ultimates gritando o nome em todas as fases   (experimental)
   A  aplicar    R  restaurar o original    S  sair
   ```

   - Número = liga/desliga. **A** = aplicar. **R** = volta o jogo ao original. **S** = sair.
   - O kit lembra as suas escolhas para a próxima vez.
5. No **Xenia Canary**, abra o `default.xex` da pasta do jogo.

Toda vez que você aplica, o kit parte dos arquivos **originais**. Então dá para ligar e
desligar opções à vontade, sem acumular um mod em cima do outro.

### Diferenças do 360 em relação ao PSP

| | PSP | Xbox 360 |
|---|---|---|
| Botão da Ultimate | SELECT | **R3** (apertar o analógico direito) |
| Animação longa de transformação | sim | não (ela travava no 360) |
| Aliens do direcional na Ultimate | trocados e devolvidos | **não mudam** (trocar travava o 360) |
| Rede de segurança contra quedas | sim | não |

---

## 6. Jogo em português

A tradução **não vem no repositório**: o texto é do jogo, então cada um tem a sua.

| Versão | Arquivo de tradução | Onde colocar | Como aplicar |
|---|---|---|---|
| PSP | `traducao_pt.txt` | pasta do kit | opção **7** do `cd_kit.py` |
| Xbox 360 | `traducao_x360_pt.txt` | pasta do kit | opção **1** do `cd_kit360.py` |
| PS3 | `traducao_ps3_pt.txt` | pasta do kit | `cd_ps3.py texto-importar` |

### Fazer a sua própria tradução

O arquivo de tradução é um texto simples, uma frase por linha, no formato `CÓDIGO|texto`:

```
9337f49a|NOVO JOGO
1443aa7d|OPÇÕES
```

1. **Exporte** os textos em inglês da sua cópia:

   ```
   python cd_tool.py texto-exportar psp_us.txt textos.txt      (PSP)
   python cd_ps3.py texto-exportar xbx_us.txt textos.txt       (Xbox 360)
   python cd_ps3.py texto-exportar ps3_us.txt textos.txt       (PS3)
   ```

   O arquivo de textos fica em `global/scripts/` dentro do jogo extraído.
2. Abra o `textos.txt`, traduza **só o que vem depois do `|`** e salve com o nome da tabela acima.
3. Não apague os códigos entre chaves e colchetes (`{2.5}`, `[4]`): são os tempos das
   legendas. Os símbolos estranhos no meio das frases são os ícones dos botões: deixe-os no lugar.

### Trocar um nome em toda a tradução (PSP)

```
python trocar_nome.py
```

Ele pergunta o nome antigo e o novo (ex.: "Ernomossauro" → "Humungossauro"), troca em todas as
frases do `traducao_pt.txt` e gera a ISO traduzida.

---

## 7. Como usar o mod no jogo

### Ultimate a qualquer momento

Aliens com forma Ultimate: **Humungossauro, Aranha Macaca, Gelo (Big Chill), Eco Eco e Fogo-Fátuo**.

| Situação | SELECT (PSP) / R3 (360) faz |
|---|---|
| Como **Ben** | o mesmo do jogo original (tela de troca de aliens) |
| Como **alien que tem Ultimate** | vira a **Ultimate** |
| Na **Ultimate** | volta ao normal |

Na Ultimate, a roda do canto mostra os golpes especiais, como nos eventos do jogo.
Os eventos de Ultimate das fases continuam funcionando como no original.

### Dicas

- **PPSSPP: não use save state** (F2/F4) para testar o mod. O save state guarda o script antigo
  na memória. Abra o jogo e carregue o **save do próprio jogo**.
- A transformação só acontece quando o personagem não está atacando, agarrado ou com o
  movimento travado.
- Tartagira e aliens sem forma Ultimate: o botão não faz nada.

---

## 8. Problemas comuns

| Problema | Solução |
|---|---|
| `python` não é reconhecido | Reinstale o Python marcando **"Add Python to PATH"** (passo 2.1). No Linux/Mac, use `python3`. |
| "Nada mudou" depois de baixar uma versão nova de um `.py` | O navegador salvou como `nome (1).py` e o comando rodou o antigo. Apague o antigo e renomeie o novo. |
| "Não achei a ISO" | A ISO tem de estar na **mesma pasta** dos `.py`, ou passe o caminho completo entre aspas. |
| O mod não aparece no PPSSPP | Você carregou um save state. Feche o jogo, abra a ISO nova e carregue o save do jogo. |
| Comando com espaços no nome falha | Coloque o caminho **entre aspas**: `"Ben 10 - ... (USA).iso"`. |
| Quero desfazer tudo | PSP: use a ISO original (ela nunca é alterada). Xbox 360: opção **R** do `cd_kit360.py`. |
| O jogo travou | Anote **onde** e **o que estava fazendo** e abra uma *issue* aqui no GitHub. No Xenia, mande também o log (abra o jogo com `--log_file=log.txt`). |

---

## 9. Todas as ferramentas

Todas usam só a biblioteca padrão do Python 3.8+. Rode qualquer uma **sem argumentos** para ver a ajuda.

### Menus (comece por aqui)

| Ferramenta | Para quê |
|---|---|
| `cd_kit.py` | **PSP:** menu que extrai, monta cada parte do mod e gera a ISO nova |
| `cd_kit360.py` | **Xbox 360:** menu que aplica tradução, Ultimate no R3, habilidades e gritos na pasta do jogo |
| `instalar_mod.py` | **PSP:** só o mod Ultimate, do jeito mais simples |
| `trocar_nome.py` | **PSP:** troca um nome em toda a tradução e gera a ISO traduzida |

### Ferramentas avançadas

| Ferramenta | Para quê |
|---|---|
| `cd_analisador.py` | **PSP:** lista e identifica os arquivos da ISO/CSO e extrai os escolhidos (`--extrair`, `--so`) |
| `cd_iso.py` | **PSP:** coloca arquivos modificados numa cópia da ISO |
| `cd_xiso.py` | **Xbox 360:** lista e extrai a ISO (sistema de arquivos XDVDFS) |
| `cd_scripts.py` | Desmonta os scripts `.ds`, aplica o mod `ultimate-livre` (PSP e 360) e gera a lista de nomes |
| `cd_anims.py` | **PSP:** copia e redireciona animações entre personagens, monta o Gigante e o Ben com golpes |
| `cd_vozes.py` | Gritos das Ultimates nos bancos de voz e scripts de voz de todas as fases (PSP e 360) |
| `cd_tool.py` | Exporta/importa os textos (`psp_*.txt`) e os dados `.ddf` (golpes, missões, personagens) |
| `cd_texturas.py` | **PSP:** exporta as texturas dos personagens para PNG e importa de volta |
| `cd_ps3.py` | **PS3/360:** pacotes `vaps` (esqueleto e animações) e textos (`texto-exportar`, `texto-importar`) |
| `cd_arcv.py` | **Vilgax Attacks:** lista, procura (`--procurar`), extrai e recoloca (`--colocar`) os arquivos do `psp_ben10.bin` |

### Exemplo: aplicar o mod da Ultimate à mão (PSP)

```
# 1. extrair o script global do jogo
python cd_analisador.py jogo.iso --extrair extraido --so "*scripts/globals.ds"

# 2. aplicar o mod (sempre a partir do globals.ds ORIGINAL)
python cd_scripts.py ultimate-livre extraido/PSP_GAME/USRDIR/global/scripts/globals.ds globals_mod.ds

# 3. montar a pasta do mod e gerar a ISO nova
mkdir -p mod/global/scripts
cp globals_mod.ds mod/global/scripts/globals.ds
python cd_iso.py jogo.iso jogo_ultimate.iso mod
```

---

## 10. Para quem quer mexer no código

### Documentação

| Arquivo | Conteúdo |
|---|---|
| [docs/estado.md](docs/estado.md) | o que já foi testado no jogo, em cada versão |
| [docs/pendencias.md](docs/pendencias.md) | o que falta e o próximo passo de cada item |
| [docs/formatos.md](docs/formatos.md) | manual de todos os formatos do jogo |
| [docs/historico.md](docs/historico.md) | por que as coisas são como são (lições que custaram caro) |
| [docs/como_pedir.md](docs/como_pedir.md) | como pedir mudanças para uma IA sem perder o que já foi feito |
| [CLAUDE.md](CLAUDE.md) | regras do projeto para quem (pessoa ou IA) vai continuar |

### Como o mod da Ultimate funciona

O mod **não altera nenhuma função do jogo**. Ele acrescenta funções novas no fim do
`globals.ds` (nomes `luis_f_...`) e cópias ajustadas de 4 funções do jogo. O jogo registra as
funções em ordem, e a última com o mesmo nome vence:

- `switch_form_update`: o botão chama o mod e a roda do canto passa pelo mod;
- a função que guarda o direcional: se uma fase começar um evento de Ultimate durante a Ultimate
  do mod, ela recebe os aliens verdadeiros;
- as 2 funções das áreas de câmera fixa: o botão ainda sai da Ultimate do mod.

### Desmontar os scripts com nomes legíveis

Os nomes internos do jogo são hashes CRC32. Para ver os nomes, gere a lista a partir da sua cópia:

```
python cd_scripts.py gerar-nomes ULUS10542_EBOOT.BIN extraido cd_nomes.txt
python cd_scripts.py desmontar globals.ds globals.txt --nomes cd_nomes.txt
```

O EBOOT descriptografado sai do PPSSPP: *Ferramentas → Ferramentas de desenvolvedor →
Dump Decrypted EBOOT.BIN on game boot* (vai para `PSP/SYSTEM/DUMP/`).

### Formatos descobertos (resumo)

- **Dados e textos:** começam com `0x1BADBABE`. Os nomes são CRC32 do texto em minúsculas.
- **`.ddf`:** registros `[hash nome][hash tipo][hash desc][qtd][ptr][tamanho][dados]`.
- **`psp_*.txt`:** `[hash][tamanho][texto\0]` repetido.
- **`.psp` (spav):** contêiner com blocos tipados; bloco 0 = texturas de 8 bits com paleta e swizzle do PSP.
- **`.ds`:** bytecode de uma máquina virtual de registradores (detalhes em `cd_scripts.py`).
- **PS3 e Xbox 360:** os mesmos formatos com a ordem dos bytes invertida (big-endian). Os pacotes
  viram `vaps`. As animações do PS3 e do 360 são idênticas byte a byte; texturas e modelos mudam.
- **Vozes:** bancos FMOD FSB4 por fase. Quem diz a posição de cada fala no banco é o
  `global/scripts/sounds.ddf` (um XML de texto).

Tudo em detalhe: [docs/formatos.md](docs/formatos.md).

### Testes

```
python testes/testes.py      # o mod rodando num simulador da máquina dos scripts
python testes/mutantes.py    # versões quebradas de propósito: os testes têm de pegar todas
```

Os testes usam o `globals.ds` e o `gld_psp.ds` originais extraídos pelo `cd_kit.py` (ou a pasta
da variável `CD_SCRIPTS`).

### O que nunca colocar no repositório

ISO, EBOOT, `default.xex`, arquivos extraídos do jogo (`.ds`, `.ddf`, `.psp`, `.xbx`, `.ps3`,
`.txt`), scripts modificados, as traduções (`traducao_*.txt`) e a lista de nomes gerada.
O `.gitignore` já bloqueia esses arquivos.
