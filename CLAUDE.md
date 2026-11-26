# Leia primeiro (para IAs e pessoas que vão continuar o projeto)

Kit de modding e mod do **Ben 10 Ultimate Alien: Cosmic Destruction (PSP, ULUS-10542)**.
Autor: Luis (GitHub LuisCodeMaster). Respostas e documentação **em português do Brasil**.

## Comece por aqui

1. `docs/estado.md`: o que funciona **testado no jogo** e o que ainda não. Não "conserte" o que está ✅.
2. `docs/pendencias.md`: o que falta, em ordem, com o próximo passo de cada item.
3. `docs/historico.md`: por que as coisas são como são (lições que custaram caro).
4. `docs/formatos.md`: o manual técnico de todos os formatos do jogo.

## Regras que não podem ser quebradas

- **Nunca publicar arquivos do jogo** no repositório: ISO/CSO, EBOOT, `.ds`, `.ddf`, `.psp`,
  `.fsb`, `.txt` do jogo, `globals_mod.ds`, saves, save states, `cd_nomes.txt`. As ferramentas
  sempre leem a cópia de quem está usando.
- **Sempre partir dos arquivos ORIGINAIS** (por exemplo, o `globals.ds` original), nunca de uma saída anterior.
- **Scripts `.ds`: só acrescentar no fim.** O jogo registra as funções pelo hash e a última vence.
  Não alterar funções que o jogo usa em outros lugares (callbacks de IA, de fase, funções
  chamadas pelo EBOOT); quando for preciso mudar uma, acrescente uma cópia modificada.
- **Não mexer nos eventos das fases** (`FUNC_ULT`, `loadpreultimateform` etc.). Veja `docs/historico.md`.
- **Commit e push só quando o Luis pedir.** Nos commits, use o e-mail
  `LuisCodeMaster@users.noreply.github.com`.
- **Uma mudança por vez.** Rode os testes antes de mandar qualquer coisa para o Luis testar no jogo.
- **Só a biblioteca padrão do Python 3.8+.** As ferramentas rodam no Termux, no celular.

## Como o Luis trabalha

- Celular Poco X7 Pro com **Termux**, emulador **PPSSPP**, pasta `/sdcard/Ben 10 Mod`.
- A ISO dele: `Ben 10 - Ultimate Alien - Cosmic Destruction (USA).iso`.
- Ele testa no jogo e manda vídeo ou print. Explique sempre o que testar e o que deve aparecer
  (tamanhos de arquivo esperados ajudam a ver se ele rodou a versão certa).
- **Armadilha comum:** o arquivo baixado de novo vira `nome(1).py`, e o comando roda o antigo.
  Lembre disso quando "nada mudou".
- Testar sempre a partir do save do jogo, não de um save state do PPSSPP.

## Ferramentas

| Arquivo | Papel |
|---|---|
| `cd_kit.py` | Menu: extrai da ISO, monta cada parte do mod e gera a ISO nova (jeito principal) |
| `instalar_mod.py` | Instalador só do mod Ultimate (a versão mais simples) |
| `cd_analisador.py` | Lista e extrai arquivos da ISO/CSO |
| `cd_iso.py` | Coloca arquivos numa cópia da ISO |
| `cd_scripts.py` | Desmonta `.ds`; aplica o mod Ultimate (`ultimate-livre`) |
| `cd_anims.py` | Pacotes `.psp`: copia e redireciona animações, monta o Gigante e o Ben com golpes |
| `cd_vozes.py` | Gritos das Ultimates nos bancos de voz e scripts de voz das fases |
| `trocar_nome.py` | Troca nomes na tradução (`traducao_pt.txt`) e gera a ISO PT-BR |
| `cd_arcv.py` | Vilgax Attacks: pacote ARCV (listar, `--procurar`, `--extrair`) |
| `cd_xiso.py` | Xbox 360: lista e extrai a ISO (XDVDFS) |
| `cd_kit360.py` | Xbox 360: menu (tradução, Ultimate no R3, habilidades, gritos) aplicado na pasta do jogo |
| `cd_ps3.py` | PS3/360: pacotes "vaps" (animações) e textos big-endian (`texto-exportar`/`texto-importar`) |
| `testes/` | Simulador da máquina dos scripts + testes do mod + testes de controle |

## Como testar

```
python cd_kit.py "jogo.iso"            # extrai uma vez para cd_trabalho/extraido
python testes/testes.py                # ~280 verificações do mod no simulador
python testes/mutantes.py              # versões quebradas de propósito: todas têm de ser pegas
```

Os testes leem o `globals.ds` e o `gld_psp.ds` originais de `cd_trabalho/extraido/...` (ou da pasta
na variável `CD_SCRIPTS`). A lista de nomes (`cd_nomes.txt`) é opcional; sem ela as mensagens mostram hashes.

> Atenção: no simulador, `m.id["humungousaur"]` aponta para o campo `.bigchill` da tabela do
> jogo (os nomes estão trocados no teste). Nos testes novos, confira qual campo está em jogo.

## Estilo das respostas para o Luis

- Português, direto, com os comandos prontos para colar no Termux.
- Diga o que já foi verificado (simulador, teste byte a byte) e o que só o jogo pode confirmar.
- Quando algo falhar no jogo, prefira montar um **teste de diagnóstico** (cada parte testa uma
  hipótese) a chutar várias mudanças juntas.
