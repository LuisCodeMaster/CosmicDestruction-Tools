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
| `instalar_mod.py` | Instala o mod Ultimate sozinho: ISO/CSO original → ISO nova com o mod |
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
