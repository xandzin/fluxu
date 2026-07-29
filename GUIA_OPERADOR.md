# Guia rápido — Sistema de Conveniência (pra imprimir e deixar no caixa)

## Abrir o sistema

Abra o navegador (Chrome/Edge) e acesse o endereço combinado com o gerente,
por exemplo `http://192.168.X.X:5000`. Favorite essa página pra não ter que
digitar toda vez.

Se a página não abrir: confira se o PC principal (o que fica com a janela
preta do sistema) está ligado e conectado na rede.

**A primeira tela vai pedir uma senha** — é a senha do sistema, a mesma pra
toda a equipe. Peça pro gerente se não souber.

## Abrir o caixa (todo dia, antes da primeira venda)

O sistema não deixa registrar venda sem o caixa aberto — é assim de
propósito, pra controlar o dinheiro.

1. Vá em **Caixa**.
2. Informe o **troco inicial** (dinheiro que já está na gaveta).
3. Clique em **"Abrir caixa"**.

Só precisa fazer isso uma vez por dia (ou por turno, se cada turno fechar o
caixa separado).

## Registrar uma venda

1. Na tela **Venda**, clique no campo de busca (ele já fica pronto pro
   leitor de código de barras).
2. **Passe o leitor** no produto, ou digite o nome dele e aperte Enter.
   - Se aparecer uma lista, clique no produto certo.
   - Se não achar nada, confira se digitou certo. Se o produto for
     realmente novo (nunca vendido antes), avise o gerente — ele cadastra
     em Estoque → "+ Novo produto".
3. Confirme a **quantidade** (já vem com 1) e o **preço** (já vem
   preenchido se o produto tiver preço cadastrado — se não tiver, digite o
   preço da etiqueta).
4. Aperte Enter ou clique em **"Registrar item"**.
5. Repita pra cada produto da compra do cliente.
6. No final, escolha a **forma de pagamento** (PIX, Débito, Crédito ou
   Dinheiro) na parte de baixo da tela e clique em **"Finalizar venda"**.
7. Aparece um aviso verde confirmando que a venda foi registrada — só
   depois disso a tela limpa pro próximo cliente.

**Atenção:** cada item já é registrado assim que você confirma ele (não
precisa "salvar" no final) — o botão "Finalizar venda" só marca a forma de
pagamento e limpa a tela pro próximo cliente. Se esquecer de finalizar, a
venda continua salva, só fica sem a forma de pagamento marcada (o gerente
corrige depois se precisar).

## Fechar o caixa (no fim do dia/turno)

1. Vá em **Caixa** — a tela mostra quanto já vendeu, separado por forma de
   pagamento, e quanto dinheiro deveria estar na gaveta agora (troco inicial
   + vendas em Dinheiro; PIX/Débito/Crédito não entram nessa conta porque
   não viram dinheiro físico na gaveta).
2. **Conte o dinheiro da gaveta de verdade.**
3. Digite o valor contado em **"Fechar caixa"**.
4. O sistema mostra se bateu ou se sobrou/faltou dinheiro.

## Lançar uma compra (chegada de mercadoria)

Isso é feito na tela **Compras** — geralmente por quem recebe a mercadoria,
não no caixa. Preencha fornecedor e data **uma vez só** no topo da tela (fica
valendo pra todos os produtos daquela entrega), depois é só ir buscando cada
produto e informando quantidade e custo.

## Contar o estoque (inventário)

Na tela **Inventário**: busque o produto (ou escolha uma categoria pra ir
passando pelos itens de uma prateleira inteira) e digite a quantidade que
você **contou fisicamente agora**. Isso substitui o número que estava
cadastrado — não é somar nem subtrair, é o valor final mesmo.

## Se errar alguma coisa

**Não tente corrigir mexendo em várias vendas seguidas por conta própria.**
Avise o gerente — ele corrige ou exclui o lançamento errado na tela
**Histórico**, que já ajusta o estoque sozinho.

## O que NÃO fazer

- Não feche a janela preta do sistema no PC principal (isso desliga o
  sistema pra todo mundo).
- Não altere preço ou cadastro de produto sem confirmar com o gerente.
- Não exclua vendas/compras sem certeza — a exclusão mexe no estoque na
  hora, não tem "desfazer".
- Não mexa na aba **Dashboard** — é área do gerente/desenvolvedor, tem
  botão que apaga o histórico de vendas.
