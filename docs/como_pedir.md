# Como pedir coisas para uma IA (e ter bons resultados)

Frases prontas para começar uma conversa nova com qualquer IA de programação, sem perder o que já foi feito.

## Começando uma conversa nova

> Leia o `CLAUDE.md`, o `docs/estado.md` e o `docs/pendencias.md` do repositório
> LuisCodeMaster/CosmicDestruction-Tools. Depois me diga em poucas linhas onde o projeto está
> e qual é o próximo passo que você sugere.

## Pedindo uma mudança

> Quero [o que você quer, do jeito que você vê no jogo: "o Ben gigante ao apertar R + SELECT"].
> Siga as regras do `CLAUDE.md`. Teste no simulador (`testes/testes.py`) antes de me mandar, e me
> diga o que testar no jogo e qual tamanho de arquivo deve aparecer.

## Quando algo não funcionou no jogo

> Testei e [o que aconteceu, com o máximo de detalhe: travou / não fez nada / fez outra coisa].
> [Anexe vídeo ou print. Se travou, o endereço que aparece na tela de erro.]
> Não chute várias mudanças: monte um teste de diagnóstico, em que cada parte testa uma hipótese.

## Pedindo para entender (aprender)

> Me explique, em português simples, como funciona [o formato dos golpes / o redirecionamento de
> animação / ...]. Use exemplos do próprio jogo e aponte a parte do `docs/formatos.md` que fala disso.

## Depois que der certo

> Funcionou no jogo. Atualize o `docs/estado.md` (e o `docs/historico.md` se houve uma lição) e
> prepare o commit. Só envie para o GitHub depois que eu confirmar.

## Dicas

- **Um pedido por vez.** Pedidos grandes misturados geram mudanças difíceis de testar.
- **Diga o que você vê, não o que acha que é a causa:** "o Ben deita no chão no 3º golpe" é melhor que "a animação está errada".
- **Confira o nome do arquivo baixado** (sem "(1)") antes de dizer que "não mudou nada".
