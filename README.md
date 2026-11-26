# CosmicDestruction-Tools

Kit de modding para **Ben 10 Ultimate Alien: Cosmic Destruction**, feito em Python puro. Roda no PC e no celular (Termux).

| Versão | O que dá para fazer | Como |
|---|---|---|
| **PSP** (ULUS-10542) | mod completo: Ultimate a qualquer momento, interações, Gigante, Ben com golpes, tradução | `cd_kit.py` |
| **Xbox 360** | tradução PT-BR, Ultimate no R3, gritos (experimental) | `cd_kit360.py` ([ver abaixo](#xbox-360)) |
| **PS3** | tradução e análise dos pacotes (os scripts do PS3 são criptografados) | `cd_ps3.py` |
| **Ben 10 Alien Force: Vilgax Attacks** (PSP) | tradução PT-BR completa | `cd_arcv.py` |

> Projeto de fã, não oficial. Este repositório **não contém nenhum arquivo do jogo nem as traduções**: todas as ferramentas trabalham sobre a **sua própria cópia** (ISO/CSO).

## Jeito mais fácil: o menu do kit

```
python cd_kit.py "Ben 10 - Ultimate Alien - Cosmic Destruction (USA).iso"
```

Você liga ou desliga cada parte do mod pelo número e aperta **M**. O kit extrai da sua ISO só o que precisa
(fica em `cd_trabalho/`), monta tudo e gera `nome do jogo (Mod).iso`. A ISO original não é alterada.

| Parte do mod | O que faz | Estado |
|---|---|---|
| Ultimate a qualquer momento | SELECT vira a Ultimate do alien atual | testado no jogo |
| Ultimates interagindo | caixas, beiradas, cair e apanhar sem travar (animações copiadas do alien normal) | testado (caixa) |
| Animação de transformação | na 1ª Ultimate de cada alien em cada fase | testado, ajustado |
| Gritos das Ultimates | "Ultimate Humungousaur!" em qualquer fase | experimental |
| Gigante | Tartagira + SELECT vira o Gigante em qualquer fase | experimental |
| Ben com golpes do Gigante | combo, especiais no R + botão (roda de especiais), R + SELECT = Ben gigante | combo e especiais testados |
| Jogo em português | usa o `traducao_pt.txt` da pasta (fica só com você: não vem no repositório) | testado (acentos) |

O estado detalhado de cada recurso está em [docs/estado.md](docs/estado.md).

## Xbox 360

No 360 os scripts do jogo são abertos (iguais aos do PSP, só que big-endian), e o emulador
Xenia roda o jogo direto da pasta extraída. Por isso o kit do 360 aplica o mod **na pasta**:

```
python cd_kit360.py "Ben 10 - Ultimate Alien - Cosmic Destruction (USA).iso" PASTA_DO_JOGO
```

Na primeira vez ele guarda os arquivos originais da ISO em `cd_trabalho360/` (e, se a pasta
ainda não existir, oferece extrair a ISO inteira). Toda vez que você aplica, ele parte dos
originais, então dá para ligar e desligar opções à vontade; a opção **R** volta tudo ao original.
No Xenia, abra o `default.xex` da pasta.

| Parte do mod | O que faz | Estado |
|---|---|---|
| Jogo em português | 1292 frases, com as mensagens próprias do 360 (usa o `traducao_x360_pt.txt`, que fica só com você) | testado |
| Ultimate a qualquer momento | **R3** vira a Ultimate do alien atual (no 360 o jogo usa o R3 para trocar de alien) | em teste |
| Habilidades das Ultimates | caixa, teia, planar, como o alien normal | não testado no 360 |
| Gritos das Ultimates | "Ultimate Humungousaur!" em qualquer fase | experimental (travou num teste) |

Diferenças do 360 em relação ao PSP, descobertas nos testes no Xenia:

- A Ultimate vira **direto**, sem a animação longa de transformação (ela travava no 360).
- O mod **carrega só a Ultimate**: trocar os aliens do direcional no meio da fase, como no PSP,
  corrompia a memória do 360 e travava o jogo em lugares diferentes.
- Sem a rede de segurança contra quedas (ela usa uma função que os scripts do 360 não têm).

## Documentação

- [docs/formatos.md](docs/formatos.md): manual de todos os formatos do jogo (scripts, pacotes, animações, esqueletos, golpes, vozes).
- [docs/estado.md](docs/estado.md): o que já foi testado no jogo.
- [docs/historico.md](docs/historico.md): por que as coisas são como são.
- [docs/pendencias.md](docs/pendencias.md): o que falta e o próximo passo de cada item.
- [docs/como_pedir.md](docs/como_pedir.md): como pedir mudanças para uma IA sem perder o que já foi feito.
- [CLAUDE.md](CLAUDE.md): regras do projeto para quem (pessoa ou IA) vai continuar.

## Mod principal: Ultimate a qualquer momento

No jogo original, a forma Ultimate só aparece nos Ultimate Events de algumas fases. Com o mod:

| Situação | SELECT faz |
|---|---|
| Como Ben | Abre a tela de troca de aliens (igual ao original) |
| Como alien que tem forma Ultimate | Vira Ultimate |
| Na forma Ultimate | Volta para o Ben e restaura os aliens do direcional |
| Como Ben depois que a Ultimate acabou sozinha | Restaura os aliens do direcional |

Aliens com forma Ultimate: Ernomosauro , Macaco Aranha, Friagem, Eco Eco e Fogo Fátuo.
Na Ultimate, a roda do canto mostra os golpes especiais (como nos eventos do jogo).

### Como funciona

O mod **não altera nenhuma função do jogo**. Ele acrescenta funções novas no fim do `globals.ds` (nomes `luis_f_...`) e cópias ajustadas de 4 funções do jogo, que valem no lugar das originais (o carregador do EBOOT registra as funções em ordem e a última com o mesmo nome vence):

- `switch_form_update`: SELECT chama o mod e a roda do canto passa pelo mod. O direcional continua o do jogo.
- A função que guarda o direcional: se uma fase começar um Ultimate Event no meio da Ultimate do mod, ela recebe os seus aliens verdadeiros.
- As 2 funções das áreas de câmera fixa: SELECT ainda sai da Ultimate do mod.

Os Ultimate Events das fases funcionam como no jogo original. Vigias soltam travas presas e devolvem o direcional sozinhos, e uma rede de segurança puxa o jogador de volta se ele cair no vazio enquanto o mod está em ação (`--sem-rede` desliga).

### Como aplicar (jeito fácil)

Baixe o repositório, coloque a sua ISO (ou CSO) na mesma pasta e rode:

```
python instalar_mod.py
```

O instalador acha o jogo na pasta, confere se é a versão americana (ULUS-10542), cria `nome do jogo (Ultimate Mod).iso` com o mod aplicado e confere o resultado. A sua ISO original não é alterada. Também dá para passar os caminhos: `python instalar_mod.py "jogo.iso" "saida.iso"` (opção `--sem-rede` desliga a rede de segurança).

### Como aplicar (passo a passo, manual)

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

Abra `jogo_ultimate.iso` no PPSSPP. A ISO original nunca é alterada. O `globals.ds` modificado fica uns 7,6 KB maior; o `cd_iso.py` coloca ele no fim da ISO.

### Dicas e limitações

- **Não teste com save states do PPSSPP**: eles guardam na memória o script da versão anterior. Abra o jogo e carregue o save do próprio jogo.
- A transformação só começa se o personagem não estiver atacando, interagindo, agarrado ou com o movimento bloqueado. Se o jogo ficar "ocupado", segure SELECT para sair da Ultimate.
- Durante a Ultimate, o direcional fica com o alien normal e a Ultimate (é o que o carregamento do jogo coloca). Ao sair, tudo volta ao normal.
- Tartagira e aliens sem Ultimate: SELECT não faz nada.
- Opcional: `python cd_scripts.py verificar-funcoes jogo.iso relatorio.txt` confere se algum nome usado pelo mod aparece nos arquivos do jogo.

## Ferramentas

Todas usam só a biblioteca padrão do Python 3.8+. Rode qualquer uma sem argumentos para ver a ajuda.

| Ferramenta | Para quê |
|---|---|
| `cd_kit.py` | Menu que junta tudo: extrai, monta cada parte do mod e gera a ISO nova |
| `instalar_mod.py` | Instala só o mod Ultimate: ISO/CSO original → ISO nova com o mod |
| `cd_anims.py` | Pacotes `.psp`: copia e redireciona animações entre personagens, monta o Gigante e o Ben com golpes |
| `cd_vozes.py` | Coloca os gritos das Ultimates nos bancos de voz e scripts de voz de todas as fases (PSP e 360; com o `sounds.ddf`, em posição fixa) |
| `trocar_nome.py` | Troca um nome (alien, golpe, personagem) em toda a tradução e gera a ISO traduzida |
| `cd_arcv.py` | **Vilgax Attacks:** lista, procura (`--procurar`), extrai e recoloca (`--colocar`) os arquivos do pacote `psp_ben10.bin` |
| `cd_analisador.py` | Lista e identifica os arquivos da ISO/CSO e extrai arquivos escolhidos (`--extrair`, `--so`) |
| `cd_iso.py` | Coloca arquivos modificados numa cópia da ISO (no lugar ou no fim, atualizando o índice) |
| `cd_scripts.py` | Desmonta os scripts compilados `.ds`, aplica o mod `ultimate-livre`, gera a lista de nomes |
| `cd_kit360.py` | **Xbox 360:** menu que aplica tradução, Ultimate no R3, habilidades e gritos na pasta do jogo |
| `cd_xiso.py` | **Xbox 360:** lista e extrai a ISO (sistema de arquivos XDVDFS) |
| `cd_ps3.py` | **PS3/360:** lista e converte pacotes `vaps` (esqueleto e animações) e exporta/importa os textos big-endian |
| `cd_tool.py` | Exporta/importa os textos (`psp_*.txt`) e os dados binários `.ddf` (golpes, missões, personagens) |
| `cd_texturas.py` | Exporta as texturas dos personagens (`.psp`) para PNG e importa de volta |

### Desmontar scripts com nomes legíveis

Os nomes internos do jogo são hashes CRC32. Para ver os nomes, gere a lista a partir da sua cópia:

```
python cd_scripts.py gerar-nomes ULUS10542_EBOOT.BIN extraido cd_nomes.txt
python cd_scripts.py desmontar globals.ds globals.txt --nomes cd_nomes.txt
```

O EBOOT descriptografado sai do PPSSPP: *Ferramentas → Ferramentas de desenvolvedor → Dump Decrypted EBOOT.BIN on game boot* (vai para `PSP/SYSTEM/DUMP/`).

## No celular (Termux)

```
pkg install python
termux-setup-storage
cd ~/storage/shared/pasta_do_jogo
python cd_analisador.py jogo.iso
```

## Formatos descobertos

- **Arquivos de dados e textos**: começam com `0x1BADBABE`. Nomes são CRC32 do texto em minúsculas.
- **`.ddf`**: registros `[hash nome][hash tipo][hash desc][qtd][ptr][tamanho][dados]`, com floats e hashes nos dados.
- **`psp_*.txt`**: `[hash][tamanho][texto\0]` repetido.
- **`.psp` (spav)**: contêiner com blocos tipados; bloco 0 = texturas 8 bits com paleta de 256 cores e swizzle do PSP.
- **PS3 e Xbox 360**: os mesmos formatos com a ordem dos bytes invertida (big-endian). Os pacotes viram `vaps`; as animações do PS3 e do 360 são idênticas byte a byte, as texturas e os modelos mudam.
- **Vozes**: bancos FMOD FSB4 por fase; quem diz a posição de cada fala no banco é o `global/scripts/sounds.ddf` (XML de texto).
- **`.ds`**: bytecode de uma máquina virtual de registradores. Funções `21 00 00 00 | hash | nº parâmetros | tamanho`, instruções de 4 bytes (algumas com +4). Detalhes no cabeçalho de `cd_scripts.py`.

## Testes

```
python testes/testes.py      # o mod rodando num simulador da máquina dos scripts
python testes/mutantes.py    # versões quebradas de propósito: os testes têm de pegar todas
```

Os testes usam o `globals.ds` e o `gld_psp.ds` originais extraídos pelo `cd_kit.py` (ou a pasta da variável `CD_SCRIPTS`).

## O que não colocar aqui

ISO, EBOOT, `default.xex`, arquivos extraídos (`.ds`, `.ddf`, `.psp`, `.xbx`, `.ps3`, `.txt` do jogo), scripts modificados, as traduções (`traducao_*.txt`) e a lista de nomes gerada. O `.gitignore` já bloqueia esses arquivos.
