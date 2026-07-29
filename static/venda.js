(function () {
    "use strict";

    const buscaEl = document.getElementById("busca");
    const resultadosEl = document.getElementById("resultados");
    const painelEl = document.getElementById("painel-item");
    const itemDescricaoEl = document.getElementById("item-descricao");
    const itemInfoEl = document.getElementById("item-info");
    const quantidadeEl = document.getElementById("quantidade");
    const precoEl = document.getElementById("preco");
    const itemAvisoEl = document.getElementById("item-aviso");
    const btnConfirmar = document.getElementById("btn-confirmar");
    const btnCancelar = document.getElementById("btn-cancelar");
    const btnFinalizar = document.getElementById("btn-finalizar");
    const tabelaCorpo = document.querySelector("#tabela-carrinho tbody");
    const semItensEl = document.getElementById("sem-itens");
    const totalVendaEl = document.getElementById("total-venda");
    const formaPagamentoEl = document.getElementById("forma-pagamento");
    const finalizarAvisoEl = document.getElementById("finalizar-aviso");
    const modalSucessoEl = document.getElementById("modal-sucesso");
    const modalTotalEl = document.getElementById("modal-total");
    const modalFormaEl = document.getElementById("modal-forma");
    const btnModalOk = document.getElementById("btn-modal-ok");
    const btnImprimirComprovante = document.getElementById("btn-imprimir-comprovante");

    let produtoSelecionado = null;
    let ultimosResultados = [];
    let totalAtual = 0;
    let debounceTimer = null;
    let idsCarrinho = [];
    let itensCarrinho = [];
    let ultimaFormaPagamento = "";

    function formatarReal(valor) {
        return "R$ " + valor.toFixed(2).replace(".", ",");
    }

    function limparResultados() {
        resultadosEl.innerHTML = "";
        resultadosEl.classList.add("hidden");
        ultimosResultados = [];
    }

    async function buscarProdutos(termo) {
        const resp = await fetch("/api/produtos/buscar?q=" + encodeURIComponent(termo));
        return resp.json();
    }

    function renderResultados(produtos) {
        ultimosResultados = produtos;
        resultadosEl.innerHTML = "";
        if (produtos.length === 0) {
            const li = document.createElement("li");
            li.className = "vazio";
            li.textContent = "Nenhum produto encontrado com esse código/nome.";
            resultadosEl.appendChild(li);
            resultadosEl.classList.remove("hidden");
            return;
        }
        produtos.forEach((p) => {
            const li = document.createElement("li");
            const precoTxt = p.preco_venda != null ? formatarReal(p.preco_venda) : "sem preço";
            const saldoTxt = p.saldo_atual != null ? p.saldo_atual : "sem contagem";
            li.innerHTML = `<strong>${escapeHtml(p.descricao)}</strong>
                <span class="detalhe">${p.sku_ean} · ${precoTxt} · saldo: ${saldoTxt}</span>`;
            li.addEventListener("click", () => selecionarProduto(p));
            resultadosEl.appendChild(li);
        });
        resultadosEl.classList.remove("hidden");
    }

    function escapeHtml(texto) {
        const div = document.createElement("div");
        div.textContent = texto;
        return div.innerHTML;
    }

    function selecionarProduto(produto) {
        produtoSelecionado = produto;
        limparResultados();
        buscaEl.value = "";

        itemDescricaoEl.textContent = produto.descricao;
        const saldoTxt = produto.saldo_atual != null ? produto.saldo_atual : "sem contagem (inventário pendente)";
        itemInfoEl.textContent = `${produto.sku_ean} · saldo atual: ${saldoTxt}`;

        quantidadeEl.value = "1";
        precoEl.value = produto.preco_venda != null ? produto.preco_venda.toFixed(2) : "";
        itemAvisoEl.classList.add("hidden");

        painelEl.classList.remove("hidden");
        quantidadeEl.focus();
        quantidadeEl.select();
    }

    function fecharPainel() {
        produtoSelecionado = null;
        painelEl.classList.add("hidden");
        buscaEl.value = "";
        buscaEl.focus();
    }

    async function confirmarItem() {
        if (!produtoSelecionado) return;
        const quantidade = parseFloat(quantidadeEl.value);
        const preco = parseFloat(precoEl.value);

        if (!(quantidade > 0)) {
            mostrarAvisoItem("Quantidade inválida.", true);
            return;
        }
        if (!(preco >= 0)) {
            mostrarAvisoItem("Preço inválido.", true);
            return;
        }

        btnConfirmar.disabled = true;
        try {
            const resp = await fetch("/api/vendas/item", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ sku: produtoSelecionado.sku_ean, quantidade, preco }),
            });
            const dados = await resp.json();

            if (!resp.ok) {
                mostrarAvisoItem(dados.erro || "Erro ao registrar item.", true);
                return;
            }

            adicionarLinhaCarrinho(dados);
            fecharPainel();
        } catch (e) {
            mostrarAvisoItem("Falha de comunicação com o servidor.", true);
        } finally {
            btnConfirmar.disabled = false;
        }
    }

    function mostrarAvisoItem(texto, erro) {
        itemAvisoEl.textContent = texto;
        itemAvisoEl.classList.remove("hidden");
        itemAvisoEl.classList.toggle("erro", !!erro);
    }

    function adicionarLinhaCarrinho(item) {
        semItensEl.classList.add("hidden");
        idsCarrinho.push(item.id);
        itensCarrinho.push({
            descricao: item.descricao,
            quantidade: item.quantidade,
            preco: item.preco,
            valor_total: item.valor_total,
        });
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(item.descricao)}</td>
            <td class="mono">${item.quantidade}</td>
            <td class="mono">${formatarReal(item.preco)}</td>
            <td class="mono">${formatarReal(item.valor_total)}</td>
        `;
        tabelaCorpo.appendChild(tr);
        totalAtual += item.valor_total;
        totalVendaEl.textContent = formatarReal(totalAtual);

        if (item.aviso) {
            const trAviso = document.createElement("tr");
            trAviso.innerHTML = `<td colspan="4" class="aviso-linha">${escapeHtml(item.aviso)}</td>`;
            tabelaCorpo.appendChild(trAviso);
        }
    }

    function limparTela() {
        tabelaCorpo.innerHTML = "";
        semItensEl.classList.remove("hidden");
        totalAtual = 0;
        totalVendaEl.textContent = formatarReal(0);
        idsCarrinho = [];
        itensCarrinho = [];
        formaPagamentoEl.value = "";
        finalizarAvisoEl.classList.add("hidden");
        buscaEl.focus();
    }

    async function finalizarVenda() {
        if (idsCarrinho.length === 0) {
            mostrarAvisoFinalizar("Nenhum item registrado ainda.");
            return;
        }
        const formaPagamento = formaPagamentoEl.value;
        if (!formaPagamento) {
            mostrarAvisoFinalizar("Selecione a forma de pagamento.");
            return;
        }

        btnFinalizar.disabled = true;
        try {
            const resp = await fetch("/api/vendas/finalizar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: idsCarrinho, forma_pagamento: formaPagamento }),
            });
            const dados = await resp.json();
            if (!resp.ok) {
                mostrarAvisoFinalizar(dados.erro || "Erro ao finalizar a venda.");
                return;
            }
            ultimaFormaPagamento = formaPagamento;
            mostrarModalSucesso(totalAtual, formaPagamento);
        } catch (e) {
            mostrarAvisoFinalizar("Falha de comunicação com o servidor.");
        } finally {
            btnFinalizar.disabled = false;
        }
    }

    let timerModal = null;

    function mostrarModalSucesso(total, formaPagamento) {
        modalTotalEl.textContent = formatarReal(total);
        modalFormaEl.textContent = "Pago via " + formaPagamento;
        modalSucessoEl.classList.remove("hidden");
        btnModalOk.focus();
        clearTimeout(timerModal);
        timerModal = setTimeout(fecharModalSucesso, 4000);
    }

    function fecharModalSucesso() {
        clearTimeout(timerModal);
        modalSucessoEl.classList.add("hidden");
        limparTela();
    }

    function imprimirComprovante() {
        // Cancela o fechamento automatico do modal enquanto o operador
        // decide se vai imprimir ou nao — evita a tela limpar no meio do
        // dialogo de impressao.
        clearTimeout(timerModal);

        const agora = new Date();
        const dataHora = agora.toLocaleDateString("pt-BR") + " " + agora.toLocaleTimeString("pt-BR");
        const nomeLoja = window.NOME_LOJA || "";

        const linhasItens = itensCarrinho.map((item) => {
            const desc = escapeHtml(item.descricao);
            const qtdPreco = `${item.quantidade} x ${formatarReal(item.preco)}`;
            const subtotal = formatarReal(item.valor_total);
            return `<div class="linha-item">
                <div>${desc}</div>
                <div class="linha-item-valores"><span>${qtdPreco}</span><span>${subtotal}</span></div>
            </div>`;
        }).join("");

        const html = `<!doctype html>
<html><head><meta charset="utf-8"><title>Comprovante</title>
<style>
    @page { size: 80mm auto; margin: 2mm; }
    body { font-family: 'Courier New', monospace; font-size: 12px; width: 76mm; margin: 0; }
    h1 { font-size: 13px; text-align: center; margin: 0 0 4px; }
    .centro { text-align: center; }
    hr { border: none; border-top: 1px dashed #000; margin: 6px 0; }
    .linha-item { margin-bottom: 3px; }
    .linha-item-valores { display: flex; justify-content: space-between; }
    .total { display: flex; justify-content: space-between; font-weight: bold; font-size: 13px; }
</style></head>
<body>
    ${nomeLoja ? `<h1>${escapeHtml(nomeLoja)}</h1>` : ""}
    <p class="centro">Comprovante de venda<br>(não é documento fiscal)</p>
    <p class="centro">${dataHora}</p>
    <hr>
    ${linhasItens}
    <hr>
    <div class="total"><span>TOTAL</span><span>${formatarReal(totalAtual)}</span></div>
    <p class="centro">Forma de pagamento: ${escapeHtml(ultimaFormaPagamento)}</p>
</body></html>`;

        const janela = window.open("", "comprovante", "width=340,height=600");
        if (!janela) {
            mostrarAvisoFinalizar("Não foi possível abrir a janela de impressão (pop-up bloqueado pelo navegador).");
            return;
        }
        janela.document.open();
        janela.document.write(html);
        janela.document.close();
        janela.focus();
        janela.print();
    }

    function mostrarAvisoFinalizar(texto) {
        finalizarAvisoEl.textContent = texto;
        finalizarAvisoEl.classList.remove("hidden");
    }

    async function executarBusca(termo) {
        const produtos = await buscarProdutos(termo);
        renderResultados(produtos);
        return produtos;
    }

    buscaEl.addEventListener("input", () => {
        const termo = buscaEl.value.trim();
        clearTimeout(debounceTimer);
        if (!termo) {
            limparResultados();
            return;
        }
        debounceTimer = setTimeout(() => executarBusca(termo), 200);
    });

    // Leitor de codigo de barras USB digita o codigo inteiro e manda Enter em
    // milissegundos — rapido demais pro debounce de digitacao acima ja ter
    // voltado. Por isso o Enter refaz a busca na hora, sem depender do
    // ultimo resultado (que pode estar desatualizado ou vazio).
    buscaEl.addEventListener("keydown", async (ev) => {
        if (ev.key !== "Enter") return;
        ev.preventDefault();
        const termo = buscaEl.value.trim();
        if (!termo) return;
        clearTimeout(debounceTimer);
        const produtos = await executarBusca(termo);
        if (produtos.length === 1) {
            selecionarProduto(produtos[0]);
        }
    });

    [quantidadeEl, precoEl].forEach((el) => {
        el.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") {
                ev.preventDefault();
                confirmarItem();
            }
        });
    });

    btnConfirmar.addEventListener("click", confirmarItem);
    btnCancelar.addEventListener("click", fecharPainel);
    btnFinalizar.addEventListener("click", finalizarVenda);
    btnModalOk.addEventListener("click", fecharModalSucesso);
    btnImprimirComprovante.addEventListener("click", imprimirComprovante);
    modalSucessoEl.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === "Escape") fecharModalSucesso();
    });

    // Leitor USB funciona como teclado: so digita se o campo de busca tiver
    // foco. Clicar em qualquer area "morta" da pagina (fora de um campo,
    // botao ou item de lista) devolve o foco pra ele, sem atrapalhar quem
    // esta no meio de confirmar um item no painel ou vendo o pop-up de sucesso.
    document.addEventListener("click", (ev) => {
        if (!painelEl.classList.contains("hidden")) return;
        if (!modalSucessoEl.classList.contains("hidden")) return;
        if (ev.target.closest("input, select, button, a, li, option, label")) return;
        buscaEl.focus();
    });

    window.addEventListener("focus", () => {
        if (painelEl.classList.contains("hidden") && modalSucessoEl.classList.contains("hidden")) buscaEl.focus();
    });
})();
