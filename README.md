# CosmicDestruction-Tools

Kit de modding para **Ben 10 Ultimate Alien: Cosmic Destruction** (PSP, ULUS-10542), feito em Python puro. Roda no PC e no celular (Termux).

> Projeto de fã, não oficial. Este repositório **não contém nenhum arquivo do jogo**: todas as ferramentas trabalham sobre a **sua própria cópia** (ISO/CSO).

## Mod principal: Ultimate a qualquer momento

No jogo original, a forma Ultimate só aparece nos Ultimate Events de algumas fases. Com o mod:

| Situação | SELECT faz |
|---|---|
| Como Ben | Abre a tela de troca de aliens (igual ao original) |
| Como alien que tem forma Ultimate | Vira Ultimate |
| Na forma Ultimate | Volta para o Ben e restaura os aliens do direcional |
| Como Ben depois que a Ultimate acabou sozinha | Restaura os aliens do direcional |

Aliens com forma Ultimate: Humungossauro, Aranha Macaca, Gelo Fumaça, Eco Eco e Fogo Fátuo.

### Como aplicar

```
# 1. extrair o script global do jogo
python cd_analisador.py jogo.iso --extrair extraido --so "*scripts/globals.ds"

# 2. aplicar o mod
python cd_scripts.py ultimate-livre extraido/PSP_GAME/USRDIR/global/scripts/globals.ds globals_mod.ds

# 3. montar a pasta do mod e gerar a ISO nova
mkdir -p mod/global/scripts
cp globals_mod.ds mod/global/scripts/globals.ds
python cd_iso.py jogo.iso jogo_ultimate.iso mod
```

Abra `jogo_ultimate.iso` no PPSSPP. A ISO original nunca é alterada.

### Dicas e limitações

- Transforme e volte para o Ben **parado, no chão, em lugares abertos**. Fora das arenas dos eventos, a troca do modelo grande da Ultimate pode fazer o personagem atravessar o cenário perto de paredes e beiradas.
- Use os **save states do PPSSPP** antes de transformar.
- A transformação só começa se o personagem não estiver atacando, interagindo, agarrado ou com o movimento bloqueado. Se o SELECT não responder, pare e tente de novo.
- Durante a Ultimate, a roda do canto mostra o alien normal, a Ultimate e dois espaços vazios (é o que o carregamento do jogo coloca no direcional). Ao sair com SELECT, tudo volta ao normal.

## Ferramentas

Todas usam só a biblioteca padrão do Python 3.8+. Rode qualquer uma sem argumentos para ver a ajuda.

| Ferramenta | Para quê |
|---|---|
| `cd_analisador.py` | Lista e identifica os arquivos da ISO/CSO e extrai arquivos escolhidos (`--extrair`, `--so`) |
| `cd_iso.py` | Coloca arquivos modificados numa cópia da ISO (no lugar ou no fim, atualizando o índice) |
| `cd_scripts.py` | Desmonta os scripts compilados `.ds`, aplica o mod `ultimate-livre`, gera a lista de nomes |
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
- **`.ds`**: bytecode de uma máquina virtual de registradores. Funções `21 00 00 00 | hash | nº parâmetros | tamanho`, instruções de 4 bytes (algumas com +4). Detalhes no cabeçalho de `cd_scripts.py`.

## O que não colocar aqui

ISO, EBOOT, arquivos extraídos (`.ds`, `.ddf`, `.psp`, `.txt` do jogo), scripts modificados e a lista de nomes gerada. O `.gitignore` já bloqueia esses arquivos.
