(function () {
    "use strict";

    const buscaEl = document.getElementById("busca");
    const resultadosEl = document.getElementById("resultados");
    const painelEl = document.getElementById("painel-item");
    const itemDescricaoEl = document.getElementById("item-descricao");
    const itemInfoEl = document.getElementById("item-info");
    const quantidadeEl = document.getElementById("quantidade");
    const custoEl = document.getElementById("custo");
    const fornecedorEl = document.getElementById("fornecedor");
    const notaFiscalEl = document.getElementById("nota_fiscal");
    const dataCompraEl = document.getElementById("data_compra");
    const itemAvisoEl = document.getElementById("item-aviso");
    const btnConfirmar = document.getElementById("btn-confirmar");
    const btnCancelar = document.getElementById("btn-cancelar");
    const btnNovaLeva = document.getElementById("btn-nova-leva");
    const historicoCorpo = document.getElementById("historico-corpo");

    let produtoSelecionado = null;
    let debounceTimer = null;

    function formatarReal(valor) {
        return "R$ " + Number(valor).toFixed(2).replace(".", ",");
    }

    function escapeHtml(texto) {
        const div = document.createElement("div");
        div.textContent = texto;
        return div.innerHTML;
    }

    function limparResultados() {
        resultadosEl.innerHTML = "";
        resultadosEl.classList.add("hidden");
    }

    async function buscarProdutos(termo) {
        const resp = await fetch("/api/produtos/buscar?q=" + encodeURIComponent(termo));
        return resp.json();
    }

    function renderResultados(produtos, termoOriginal) {
        resultadosEl.innerHTML = "";
        if (produtos.length === 0) {
            const li = document.createElement("li");
            li.className = "vazio";
            const linkNovo = `/produtos/novo?sku_ean=${encodeURIComponent(termoOriginal)}`;
            li.innerHTML = `Nenhum produto encontrado com esse código/nome.
                <a href="${linkNovo}">Cadastrar produto novo</a>`;
            resultadosEl.appendChild(li);
            resultadosEl.classList.remove("hidden");
            return;
        }
        produtos.forEach((p) => {
            const li = document.createElement("li");
            const custoTxt = p.custo_unitario != null ? formatarReal(p.custo_unitario) : "sem custo anterior";
            const saldoTxt = p.saldo_atual != null ? p.saldo_atual : "sem contagem";
            li.innerHTML = `<strong>${escapeHtml(p.descricao)}</strong>
                <span class="detalhe">${p.sku_ean} · último custo: ${custoTxt} · saldo atual: ${saldoTxt}</span>`;
            li.addEventListener("click", () => selecionarProduto(p));
            resultadosEl.appendChild(li);
        });
        resultadosEl.classList.remove("hidden");
    }

    async function executarBusca(termo) {
        const produtos = await buscarProdutos(termo);
        renderResultados(produtos, termo);
        return produtos;
    }

    function selecionarProduto(produto) {
        produtoSelecionado = produto;
        limparResultados();
        buscaEl.value = "";

        itemDescricaoEl.textContent = produto.descricao;
        const saldoTxt = produto.saldo_atual != null ? produto.saldo_atual : "sem contagem (inventário pendente)";
        itemInfoEl.textContent = `${produto.sku_ean} · saldo atual: ${saldoTxt}`;

        quantidadeEl.value = "1";
        // Fornecedor, NF e data ficam fixos entre itens de proposito — numa
        // mesma leva/entrega, sao quase sempre os mesmos, entao so pedir de
        // novo em cada item seria repetir trabalho a toa. So o "Nova leva"
        // limpa esses campos.
        custoEl.value = produto.custo_unitario != null ? produto.custo_unitario.toFixed(2) : "";
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

    function mostrarAvisoItem(texto, erro) {
        itemAvisoEl.textContent = texto;
        itemAvisoEl.classList.remove("hidden");
        itemAvisoEl.classList.toggle("erro", !!erro);
    }

    async function confirmarItem() {
        if (!produtoSelecionado) return;
        const quantidade = parseFloat(quantidadeEl.value);
        const custo_unitario = parseFloat(custoEl.value);

        if (!(quantidade > 0)) {
            mostrarAvisoItem("Quantidade inválida.", true);
            return;
        }
        if (!(custo_unitario >= 0)) {
            mostrarAvisoItem("Custo inválido.", true);
            return;
        }

        btnConfirmar.disabled = true;
        try {
            const resp = await fetch("/api/compras", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    sku: produtoSelecionado.sku_ean,
                    quantidade,
                    custo_unitario,
                    fornecedor: fornecedorEl.value.trim(),
                    nota_fiscal: notaFiscalEl.value.trim(),
                    data_compra: dataCompraEl.value,
                }),
            });
            const dados = await resp.json();

            if (!resp.ok) {
                mostrarAvisoItem(dados.erro || "Erro ao registrar a compra.", true);
                return;
            }

            adicionarLinhaHistorico(dados, fornecedorEl.value.trim(), notaFiscalEl.value.trim(), dataCompraEl.value);
            fecharPainel();
        } catch (e) {
            mostrarAvisoItem("Falha de comunicação com o servidor.", true);
        } finally {
            btnConfirmar.disabled = false;
        }
    }

    function adicionarLinhaHistorico(item, fornecedor, notaFiscal, data) {
        const vazio = document.getElementById("historico-vazio");
        if (vazio) vazio.remove();

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${data}</td>
            <td>${escapeHtml(item.descricao)}</td>
            <td>${escapeHtml(fornecedor || "—")}</td>
            <td>${item.quantidade}</td>
            <td>${formatarReal(item.custo_unitario)}</td>
            <td>${escapeHtml(notaFiscal || "—")}</td>
        `;
        historicoCorpo.insertBefore(tr, historicoCorpo.firstChild);
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

    [quantidadeEl, custoEl].forEach((el) => {
        el.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") {
                ev.preventDefault();
                confirmarItem();
            }
        });
    });

    function novaLeva() {
        fornecedorEl.value = "";
        notaFiscalEl.value = "";
        const hoje = new Date();
        const iso = hoje.getFullYear() + "-" + String(hoje.getMonth() + 1).padStart(2, "0")
            + "-" + String(hoje.getDate()).padStart(2, "0");
        dataCompraEl.value = iso;
        buscaEl.focus();
    }

    btnConfirmar.addEventListener("click", confirmarItem);
    btnCancelar.addEventListener("click", fecharPainel);
    btnNovaLeva.addEventListener("click", novaLeva);

    document.addEventListener("click", (ev) => {
        if (!painelEl.classList.contains("hidden")) return;
        if (ev.target.closest("input, select, button, a, li, option, label")) return;
        buscaEl.focus();
    });

    window.addEventListener("focus", () => {
        if (painelEl.classList.contains("hidden")) buscaEl.focus();
    });
})();
