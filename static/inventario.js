(function () {
    "use strict";

    const buscaEl = document.getElementById("busca");
    const categoriaEl = document.getElementById("categoria");
    const resultadosEl = document.getElementById("resultados");
    const painelEl = document.getElementById("painel-item");
    const itemDescricaoEl = document.getElementById("item-descricao");
    const itemInfoEl = document.getElementById("item-info");
    const saldoContadoEl = document.getElementById("saldo_contado");
    const itemAvisoEl = document.getElementById("item-aviso");
    const btnConfirmar = document.getElementById("btn-confirmar");
    const btnCancelar = document.getElementById("btn-cancelar");
    const btnLimparSessao = document.getElementById("btn-limpar-sessao");
    const tabelaCorpo = document.querySelector("#tabela-sessao tbody");
    const semItensEl = document.getElementById("sem-itens");

    let produtoSelecionado = null;
    let debounceTimer = null;

    function escapeHtml(texto) {
        const div = document.createElement("div");
        div.textContent = texto;
        return div.innerHTML;
    }

    function formatarNumero(valor) {
        return Number(valor).toString();
    }

    function limparResultados() {
        resultadosEl.innerHTML = "";
        resultadosEl.classList.add("hidden");
    }

    async function buscarProdutos(termo) {
        const params = new URLSearchParams();
        if (termo) params.set("q", termo);
        if (categoriaEl.value) params.set("categoria", categoriaEl.value);
        const resp = await fetch("/api/produtos/buscar?" + params.toString());
        return resp.json();
    }

    function renderResultados(produtos) {
        resultadosEl.innerHTML = "";
        if (produtos.length === 0) {
            const li = document.createElement("li");
            li.className = "vazio";
            li.textContent = "Nenhum produto encontrado.";
            resultadosEl.appendChild(li);
            resultadosEl.classList.remove("hidden");
            return;
        }
        produtos.forEach((p) => {
            const li = document.createElement("li");
            const saldoTxt = p.saldo_atual != null ? formatarNumero(p.saldo_atual) : "sem contagem";
            li.innerHTML = `<strong>${escapeHtml(p.descricao)}</strong>
                <span class="detalhe">${p.sku_ean} · saldo cadastrado: ${saldoTxt}</span>`;
            li.addEventListener("click", () => selecionarProduto(p));
            resultadosEl.appendChild(li);
        });
        resultadosEl.classList.remove("hidden");
    }

    async function executarBusca(termo) {
        const produtos = await buscarProdutos(termo);
        renderResultados(produtos);
        return produtos;
    }

    function selecionarProduto(produto) {
        produtoSelecionado = produto;
        buscaEl.value = "";
        // No modo "navegar por categoria" a lista fica visivel atras do
        // painel, pra depois de salvar dar pra clicar direto no proximo item
        // sem escolher a categoria de novo.
        if (!categoriaEl.value) limparResultados();

        itemDescricaoEl.textContent = produto.descricao;
        const saldoTxt = produto.saldo_atual != null ? formatarNumero(produto.saldo_atual) : "sem contagem ainda";
        itemInfoEl.textContent = `${produto.sku_ean} · saldo cadastrado hoje: ${saldoTxt}`;

        saldoContadoEl.value = "";
        itemAvisoEl.classList.add("hidden");

        painelEl.classList.remove("hidden");
        saldoContadoEl.focus();
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
        const saldoContado = parseFloat(saldoContadoEl.value);

        if (!(saldoContado >= 0)) {
            mostrarAvisoItem("Digite a quantidade contada (0 ou mais).", true);
            return;
        }

        btnConfirmar.disabled = true;
        try {
            const resp = await fetch("/api/inventario/ajustar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ sku: produtoSelecionado.sku_ean, saldo_contado: saldoContado }),
            });
            const dados = await resp.json();

            if (!resp.ok) {
                mostrarAvisoItem(dados.erro || "Erro ao salvar a contagem.", true);
                return;
            }

            adicionarLinhaSessao(dados);
            fecharPainel();

            // Se estava navegando por categoria, recarrega a lista (com o
            // saldo ja atualizado) pra continuar clicando nos proximos itens.
            if (categoriaEl.value) {
                const produtos = await buscarProdutos("");
                renderResultados(produtos);
            }
        } catch (e) {
            mostrarAvisoItem("Falha de comunicação com o servidor.", true);
        } finally {
            btnConfirmar.disabled = false;
        }
    }

    function adicionarLinhaSessao(item) {
        semItensEl.classList.add("hidden");
        const anterior = item.saldo_anterior != null ? item.saldo_anterior : null;
        const diferenca = anterior != null ? (item.saldo_contado - anterior) : null;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(item.descricao)}</td>
            <td>${anterior != null ? formatarNumero(anterior) : "sem contagem"}</td>
            <td>${formatarNumero(item.saldo_contado)}</td>
            <td>${diferenca != null ? (diferenca > 0 ? "+" : "") + formatarNumero(diferenca) : "—"}</td>
        `;
        tabelaCorpo.insertBefore(tr, tabelaCorpo.firstChild);
    }

    function limparSessao() {
        tabelaCorpo.innerHTML = "";
        semItensEl.classList.remove("hidden");
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

    categoriaEl.addEventListener("change", async () => {
        buscaEl.value = "";
        if (!categoriaEl.value) {
            limparResultados();
            return;
        }
        const produtos = await buscarProdutos("");
        renderResultados(produtos);
    });

    saldoContadoEl.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
            ev.preventDefault();
            confirmarItem();
        }
    });

    btnConfirmar.addEventListener("click", confirmarItem);
    btnCancelar.addEventListener("click", fecharPainel);
    btnLimparSessao.addEventListener("click", limparSessao);

    document.addEventListener("click", (ev) => {
        if (!painelEl.classList.contains("hidden")) return;
        if (ev.target.closest("input, select, button, a, li, option, label")) return;
        buscaEl.focus();
    });

    window.addEventListener("focus", () => {
        if (painelEl.classList.contains("hidden")) buscaEl.focus();
    });
})();
