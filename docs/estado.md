# Estado do mod: o que foi testado no jogo

Atualize esta tabela **só com o que o Luis testou no PPSSPP**. O que só passou no simulador
fica como 🧪.

Legenda: ✅ funciona no jogo · ⚠️ funciona com ressalva · ❌ não funcionou · 🧪 só testado no simulador

| Recurso | Opção | Estado | Última notícia |
|---|---|---|---|
| Ultimate a qualquer momento (SELECT) | padrão | ✅ | 18/11: "Deu super certo" |
| HUD com os golpes da Ultimate | padrão | ✅ | 18/11 |
| Direcional devolvido ao sair | padrão | ✅ | 18/11 |
| Habilidades do alien normal na Ultimate (caixa, teia, planar) | padrão | ✅ | 22/11: empurrar caixa ok |
| Animações de interação nas Ultimates | `cd_anims --pasta` | ✅ | 22/11: caixa ok |
| Humungossauro Supremo quebrar parede | — | ❓ | não testado; ver pendências |
| Humungossauro Supremo alavanca | — | ❌ | 22/11: não gira |
| Animação de transformação (1ª vez na fase) | padrão (`--sem-intro` tira) | ⚠️ | 22/11: aparece; pose estava lenta, trava encurtada para 1,5 s (🧪) |
| Gritos das Ultimates em todas as fases | `cd_vozes` + script | 🧪 | 22/11: não tocou; agora o mod manda tocar (🧪) |
| Gigante (Tartagira + SELECT) só na fase final | `--gigante` (antigo) | ⚠️ | 19/11: funcionava só em l_tokd |
| Gigante em qualquer fase | `cd_anims --gigante` + `--gigante` | 🧪 | pacote com esqueleto montado; não confirmado |
| Ben com os golpes do Gigante (combo) | `cd_anims --ben-gigante` | ✅ | 22/11: "funcionou boa parte"; ataques um pouco lentos → acelerados |
| Roda de especiais do Ben (segurar R) | `--ben-gigante` | ✅ | 22/11 |
| Especiais do Gigante no Ben (R + botão) | `--ben-gigante` | ✅ | 22/11: "tá ok" |
| Ben gigante (R + SELECT) | `--ben-gigante` | ❌→🧪 | 22/11: não funcionou; correção (tamanho reaplicado a cada quadro) |
| `cd_kit.py` com a ISO real | — | ✅ | 22/11: "Deu certo" |
| Instalador `instalar_mod.py` | — | 🧪 | testado com ISO falsa |
