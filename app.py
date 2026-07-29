"""
Fase 3 — Interface web local (Flask) pra venda e consulta de estoque.

Roda na rede local, sem dependencia de internet (sem CDN, CSS/JS proprios).
Cada item de venda e gravado e baixado do estoque na hora (mesma logica
transacional do registrar_venda.py), sem carrinho persistido no servidor —
o "carrinho" na tela e so uma lista visual do que ja foi confirmado.

So um PC roda esse app.py (o que guarda o estoque.db); os outros PCs acessam
pelo navegador via IP desse PC na rede local, tipo http://192.168.0.X:5000.
"""

import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, get_flashed_messages, jsonify,
                    redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "estoque.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
SECRET_KEY_PATH = os.path.join(BASE_DIR, "secret_key.txt")

# Unica fonte da verdade das opcoes do seletor na tela de venda. Pra adicionar
# uma forma de pagamento nova (ex: "Vale-refeicao"), so acrescentar aqui.
FORMAS_PAGAMENTO = ["PIX", "Débito", "Crédito", "Dinheiro"]

# Rotas que funcionam sem estar logado. Tudo mais exige senha (PRD-0 do dia
# da implantacao: sistema inteiro protegido, senha unica compartilhada).
ROTAS_PUBLICAS = {"login", "static"}


def garantir_schema(caminho_db):
    """Cria o banco do zero (via schema.sql) se ele ainda nao existir. Se ja
    existir, aplica migracoes idempotentes — nunca apaga dados. Colunas/
    tabelas novas sao adicionadas ANTES de rodar o schema.sql completo,
    porque ele cria indices em cima delas e "CREATE TABLE IF NOT EXISTS" nao
    adiciona coluna em tabela que ja existe."""
    novo = not os.path.exists(caminho_db)
    conn = sqlite3.connect(caminho_db)
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            texto_schema = f.read()

        if novo:
            conn.executescript(texto_schema)
            conn.commit()
            return

        existe_vendas = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vendas'"
        ).fetchone()
        if not existe_vendas:
            conn.executescript(texto_schema)
            conn.commit()
            return

        conn.execute(
            "CREATE TABLE IF NOT EXISTS caixa ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, "
            "hora_abertura TEXT NOT NULL, valor_abertura REAL NOT NULL, "
            "hora_fechamento TEXT, valor_fechamento REAL, observacoes TEXT)"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)")

        colunas_vendas = [linha[1] for linha in conn.execute("PRAGMA table_info(vendas)")]
        if "forma_pagamento" not in colunas_vendas:
            conn.execute("ALTER TABLE vendas ADD COLUMN forma_pagamento TEXT")
        if "caixa_id" not in colunas_vendas:
            conn.execute("ALTER TABLE vendas ADD COLUMN caixa_id INTEGER REFERENCES caixa(id)")
        conn.commit()

        conn.executescript(texto_schema)
        conn.commit()
    finally:
        conn.close()


def carregar_secret_key():
    """Chave persistente (arquivo local) pra sessao de login sobreviver a
    reinicio do servidor — senao todo mundo cairia da sessao a cada restart."""
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    chave = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(chave)
    return chave


garantir_schema(DB_PATH)

app = Flask(__name__)
app.secret_key = carregar_secret_key()
app.permanent_session_lifetime = timedelta(days=14)


@app.before_request
def exigir_login():
    if request.endpoint in ROTAS_PUBLICAS or request.endpoint is None:
        return
    if not session.get("autenticado"):
        return redirect(url_for("login", proximo=request.path))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL permite um PC gravando (venda/compra) enquanto outros leem, sem travar —
    # importante agora que varios PCs na rede acessam o mesmo banco ao mesmo tempo.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def obter_config(conn, chave):
    linha = conn.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return linha["valor"] if linha else None


def definir_config(conn, chave, valor):
    conn.execute(
        "INSERT INTO config (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_conn()
    try:
        senha_hash = obter_config(conn, "senha_hash")
        primeiro_acesso = senha_hash is None

        if request.method == "GET":
            return render_template("login.html", erro=None, primeiro_acesso=primeiro_acesso)

        senha = request.form.get("senha", "")

        if primeiro_acesso:
            confirmar = request.form.get("confirmar", "")
            if len(senha) < 4:
                return render_template("login.html", erro="A senha precisa ter pelo menos 4 caracteres.",
                                        primeiro_acesso=True)
            if senha != confirmar:
                return render_template("login.html", erro="As senhas não coincidem.", primeiro_acesso=True)
            definir_config(conn, "senha_hash", generate_password_hash(senha))
            conn.commit()
            session.clear()
            session.permanent = True
            session["autenticado"] = True
            return redirect(url_for("venda"))

        if senha_hash and check_password_hash(senha_hash, senha):
            session.clear()
            session.permanent = True
            session["autenticado"] = True
            proximo = request.args.get("proximo") or url_for("venda")
            return redirect(proximo)

        return render_template("login.html", erro="Senha incorreta.", primeiro_acesso=False)
    finally:
        conn.close()


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def buscar_por_sku(conn, sku):
    return conn.execute(
        "SELECT sku_ean, descricao, preco_venda, custo_unitario, saldo_atual FROM estoque WHERE sku_ean = ?",
        (sku,),
    ).fetchone()


def buscar_por_texto(conn, termo, limite=20, categoria=None):
    palavras = termo.upper().split()
    if not palavras:
        return []
    condicoes = [" AND ".join(["UPPER(descricao) LIKE ?" for _ in palavras])]
    params = [f"%{p}%" for p in palavras]
    if categoria:
        condicoes.append("categoria = ?")
        params.append(categoria)
    return conn.execute(
        f"SELECT sku_ean, descricao, preco_venda, custo_unitario, saldo_atual FROM estoque "
        f"WHERE {' AND '.join(condicoes)} ORDER BY descricao LIMIT ?",
        params + [limite],
    ).fetchall()


def row_to_produto(row):
    return {
        "sku_ean": row["sku_ean"],
        "descricao": row["descricao"],
        "preco_venda": row["preco_venda"],
        "custo_unitario": row["custo_unitario"],
        "saldo_atual": row["saldo_atual"],
    }


def listar_categorias(conn):
    return [r["categoria"] for r in conn.execute(
        "SELECT DISTINCT categoria FROM estoque WHERE categoria IS NOT NULL ORDER BY categoria"
    )]


CAMPOS_PRODUTO = ["sku_ean", "descricao", "categoria", "unidade", "custo_unitario", "preco_venda", "saldo_atual", "validade"]


def ler_form_produto(form):
    return {campo: form.get(campo, "").strip() for campo in CAMPOS_PRODUTO}


def validar_produto(valores):
    """Retorna (dados_normalizados, erro). dados_normalizados e None se erro."""
    if not valores["sku_ean"]:
        return None, "SKU/EAN é obrigatório."
    if not valores["descricao"]:
        return None, "Descrição é obrigatória."

    def numero_opcional(v, nome):
        if v == "":
            return None, None
        try:
            return float(v.replace(",", ".")), None
        except ValueError:
            return None, f"{nome} precisa ser um número."

    custo, erro = numero_opcional(valores["custo_unitario"], "Custo")
    if erro:
        return None, erro
    preco, erro = numero_opcional(valores["preco_venda"], "Preço")
    if erro:
        return None, erro
    saldo, erro = numero_opcional(valores["saldo_atual"], "Saldo")
    if erro:
        return None, erro

    return {
        "sku_ean": valores["sku_ean"],
        "descricao": valores["descricao"],
        "categoria": valores["categoria"] or None,
        "unidade": valores["unidade"] or "UN",
        "custo_unitario": custo,
        "preco_venda": preco,
        "saldo_atual": saldo,
        "validade": valores["validade"] or None,
    }, None


@app.route("/")
def index():
    return venda()


def obter_caixa_aberto(conn):
    return conn.execute(
        "SELECT * FROM caixa WHERE hora_fechamento IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()


@app.route("/venda")
def venda():
    conn = get_conn()
    try:
        if obter_caixa_aberto(conn) is None:
            flash("Abra o caixa antes de registrar vendas.", "erro")
            return redirect(url_for("caixa"))
        nome_loja = obter_config(conn, "nome_loja") or ""
        return render_template("venda.html", formas_pagamento=FORMAS_PAGAMENTO, nome_loja=nome_loja)
    finally:
        conn.close()


@app.route("/api/produtos/buscar")
def api_buscar_produtos():
    termo = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", "").strip()

    if not termo and not categoria:
        return jsonify([])

    conn = get_conn()
    try:
        if termo and not categoria and termo.isdigit():
            produto = buscar_por_sku(conn, termo)
            if produto:
                return jsonify([row_to_produto(produto)])

        if not termo and categoria:
            # Navegar uma categoria inteira (uso do inventario: percorrer a
            # prateleira sem precisar digitar nome/codigo de cada item).
            resultados = conn.execute(
                "SELECT sku_ean, descricao, preco_venda, custo_unitario, saldo_atual FROM estoque "
                "WHERE categoria = ? ORDER BY descricao LIMIT 300",
                (categoria,),
            ).fetchall()
            return jsonify([row_to_produto(r) for r in resultados])

        resultados = buscar_por_texto(conn, termo, categoria=categoria or None)
        return jsonify([row_to_produto(r) for r in resultados])
    finally:
        conn.close()


@app.route("/api/vendas/item", methods=["POST"])
def api_registrar_item():
    dados = request.get_json(force=True, silent=True) or {}
    sku = str(dados.get("sku", "")).strip()
    try:
        quantidade = float(dados.get("quantidade"))
        preco = float(dados.get("preco"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Quantidade e preco precisam ser numeros."}), 400

    if not sku:
        return jsonify({"erro": "SKU obrigatorio."}), 400
    if quantidade <= 0:
        return jsonify({"erro": "Quantidade deve ser maior que zero."}), 400
    if preco < 0:
        return jsonify({"erro": "Preco nao pode ser negativo."}), 400

    conn = get_conn()
    try:
        caixa_aberto = obter_caixa_aberto(conn)
        if caixa_aberto is None:
            return jsonify({"erro": "Nenhum caixa aberto. Abra o caixa antes de vender."}), 403

        produto = buscar_por_sku(conn, sku)
        if not produto:
            return jsonify({"erro": "Produto nao encontrado no estoque."}), 404

        descricao = produto["descricao"]
        saldo_atual = produto["saldo_atual"]
        valor_total = round(quantidade * preco, 2)

        aviso = None
        if saldo_atual is None:
            aviso = "Item sem contagem de estoque (inventario pendente) — saldo nao foi decrementado."
        elif quantidade > saldo_atual:
            aviso = f"Saldo ficou negativo ({saldo_atual - quantidade:g}). Confira o estoque desse item."

        conn.execute("BEGIN")
        cursor = conn.execute(
            "INSERT INTO vendas (data_venda, produto_nome_raw, sku_ean, quantidade, valor_total, caixa_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (date.today().isoformat(), descricao, sku, quantidade, valor_total, caixa_aberto["id"]),
        )
        venda_id = cursor.lastrowid
        novo_saldo = None
        if saldo_atual is not None:
            novo_saldo = saldo_atual - quantidade
            conn.execute(
                "UPDATE estoque SET saldo_atual = ? WHERE sku_ean = ?",
                (novo_saldo, sku),
            )
        conn.commit()

        return jsonify({
            "ok": True,
            "id": venda_id,
            "sku_ean": sku,
            "descricao": descricao,
            "quantidade": quantidade,
            "preco": preco,
            "valor_total": valor_total,
            "saldo_atual": novo_saldo,
            "aviso": aviso,
        })
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.route("/api/vendas/finalizar", methods=["POST"])
def api_finalizar_venda():
    dados = request.get_json(force=True, silent=True) or {}
    ids = dados.get("ids") or []
    forma_pagamento = str(dados.get("forma_pagamento", "")).strip()

    if not ids:
        return jsonify({"erro": "Nenhum item pra finalizar."}), 400
    if forma_pagamento not in FORMAS_PAGAMENTO:
        return jsonify({"erro": "Forma de pagamento inválida."}), 400
    if not all(isinstance(i, int) for i in ids):
        return jsonify({"erro": "IDs inválidos."}), 400

    conn = get_conn()
    try:
        marcadores = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE vendas SET forma_pagamento = ? WHERE id IN ({marcadores})",
            [forma_pagamento] + ids,
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/caixa")
def caixa():
    conn = get_conn()
    try:
        aberto = obter_caixa_aberto(conn)
        resumo_pagamento = []
        dinheiro_esperado = None
        if aberto is not None:
            resumo_pagamento = conn.execute(
                "SELECT COALESCE(forma_pagamento, 'Não informada') AS forma, "
                "COUNT(*) AS lancamentos, COALESCE(SUM(valor_total),0) AS total "
                "FROM vendas WHERE caixa_id = ? GROUP BY forma ORDER BY total DESC",
                (aberto["id"],),
            ).fetchall()
            total_dinheiro = conn.execute(
                "SELECT COALESCE(SUM(valor_total),0) AS total FROM vendas "
                "WHERE caixa_id = ? AND forma_pagamento = 'Dinheiro'",
                (aberto["id"],),
            ).fetchone()["total"]
            dinheiro_esperado = aberto["valor_abertura"] + total_dinheiro

        historico = conn.execute(
            "SELECT c.*, "
            "(SELECT COALESCE(SUM(v.valor_total),0) FROM vendas v "
            " WHERE v.caixa_id = c.id AND v.forma_pagamento = 'Dinheiro') AS total_dinheiro "
            "FROM caixa c WHERE c.hora_fechamento IS NOT NULL ORDER BY c.id DESC LIMIT 15"
        ).fetchall()

        return render_template(
            "caixa.html", aberto=aberto, resumo_pagamento=resumo_pagamento,
            dinheiro_esperado=dinheiro_esperado, historico=historico,
            hoje=date.today().isoformat(),
        )
    finally:
        conn.close()


@app.route("/caixa/abrir", methods=["POST"])
def caixa_abrir():
    conn = get_conn()
    try:
        if obter_caixa_aberto(conn) is not None:
            flash("Já tem um caixa aberto.", "erro")
            return redirect(url_for("caixa"))

        try:
            valor_abertura = float(request.form.get("valor_abertura", "").replace(",", "."))
        except ValueError:
            flash("Valor de abertura inválido.", "erro")
            return redirect(url_for("caixa"))
        if valor_abertura < 0:
            flash("Valor de abertura não pode ser negativo.", "erro")
            return redirect(url_for("caixa"))

        agora = datetime.now()
        conn.execute(
            "INSERT INTO caixa (data, hora_abertura, valor_abertura) VALUES (?, ?, ?)",
            (agora.date().isoformat(), agora.isoformat(timespec="seconds"), valor_abertura),
        )
        conn.commit()
        flash("Caixa aberto.", "ok")
        return redirect(url_for("venda"))
    finally:
        conn.close()


@app.route("/caixa/fechar", methods=["POST"])
def caixa_fechar():
    conn = get_conn()
    try:
        aberto = obter_caixa_aberto(conn)
        if aberto is None:
            flash("Não tem caixa aberto pra fechar.", "erro")
            return redirect(url_for("caixa"))

        try:
            valor_fechamento = float(request.form.get("valor_fechamento", "").replace(",", "."))
        except ValueError:
            flash("Valor de fechamento inválido.", "erro")
            return redirect(url_for("caixa"))
        if valor_fechamento < 0:
            flash("Valor de fechamento não pode ser negativo.", "erro")
            return redirect(url_for("caixa"))

        observacoes = request.form.get("observacoes", "").strip() or None
        agora = datetime.now()
        conn.execute(
            "UPDATE caixa SET hora_fechamento = ?, valor_fechamento = ?, observacoes = ? WHERE id = ?",
            (agora.isoformat(timespec="seconds"), valor_fechamento, observacoes, aberto["id"]),
        )
        conn.commit()
        flash("Caixa fechado.", "ok")
        return redirect(url_for("caixa"))
    finally:
        conn.close()


@app.route("/estoque")
def estoque():
    conn = get_conn()
    try:
        categorias = listar_categorias(conn)

        categoria_sel = request.args.get("categoria", "")
        busca = request.args.get("busca", "").strip()
        sem_preco = request.args.get("sem_preco") == "1"

        where = []
        params = []
        if categoria_sel:
            where.append("categoria = ?")
            params.append(categoria_sel)
        if busca:
            for palavra in busca.upper().split():
                where.append("UPPER(descricao) LIKE ?")
                params.append(f"%{palavra}%")
        if sem_preco:
            where.append("preco_venda IS NULL")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        total = conn.execute(f"SELECT COUNT(*) FROM estoque {where_sql}", params).fetchone()[0]

        LIMITE = 200
        itens = conn.execute(
            f"SELECT * FROM estoque {where_sql} ORDER BY categoria, descricao LIMIT ?",
            params + [LIMITE],
        ).fetchall()

        # Totais por categoria (sobre TODOS os itens que batem no filtro, nao
        # so os 200 exibidos). saldo*custo/preco so soma quando os dois sao
        # conhecidos — item sem saldo contado ou sem preco nao entra na conta,
        # entao os totais sao parciais ate o inventario estar completo.
        totais_categoria = conn.execute(
            f"SELECT categoria, COUNT(*) AS itens, "
            f"COALESCE(SUM(saldo_atual),0) AS qtd_total, "
            f"COALESCE(SUM(saldo_atual * custo_unitario),0) AS valor_custo, "
            f"COALESCE(SUM(saldo_atual * preco_venda),0) AS valor_venda "
            f"FROM estoque {where_sql} GROUP BY categoria ORDER BY categoria",
            params,
        ).fetchall()
        total_geral = {
            "valor_custo": sum(c["valor_custo"] for c in totais_categoria),
            "valor_venda": sum(c["valor_venda"] for c in totais_categoria),
        }

        return render_template(
            "estoque.html",
            itens=itens,
            categorias=categorias,
            categoria_sel=categoria_sel,
            busca=busca,
            sem_preco=sem_preco,
            total=total,
            limite=LIMITE,
            totais_categoria=totais_categoria,
            total_geral=total_geral,
        )
    finally:
        conn.close()


@app.route("/inventario")
def inventario():
    conn = get_conn()
    try:
        categorias = listar_categorias(conn)
        return render_template("inventario.html", categorias=categorias)
    finally:
        conn.close()


@app.route("/api/inventario/ajustar", methods=["POST"])
def api_inventario_ajustar():
    dados = request.get_json(force=True, silent=True) or {}
    sku = str(dados.get("sku", "")).strip()
    try:
        saldo_contado = float(dados.get("saldo_contado"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Quantidade contada precisa ser um número."}), 400

    if not sku:
        return jsonify({"erro": "SKU obrigatório."}), 400
    if saldo_contado < 0:
        return jsonify({"erro": "Quantidade contada não pode ser negativa."}), 400

    conn = get_conn()
    try:
        produto = buscar_por_sku(conn, sku)
        if not produto:
            return jsonify({"erro": "Produto não encontrado no estoque."}), 404

        saldo_anterior = produto["saldo_atual"]
        conn.execute("UPDATE estoque SET saldo_atual = ? WHERE sku_ean = ?", (saldo_contado, sku))
        conn.commit()

        return jsonify({
            "ok": True,
            "sku_ean": sku,
            "descricao": produto["descricao"],
            "saldo_anterior": saldo_anterior,
            "saldo_contado": saldo_contado,
        })
    finally:
        conn.close()


@app.route("/produtos/novo", methods=["GET", "POST"])
def produto_novo():
    conn = get_conn()
    try:
        categorias = listar_categorias(conn)

        if request.method == "GET":
            valores = {campo: "" for campo in CAMPOS_PRODUTO}
            valores["sku_ean"] = request.args.get("sku_ean", "")
            valores["unidade"] = "UN"
            valores["saldo_atual"] = "0"
            return render_template("produto_form.html", modo="novo", valores=valores, erro=None, categorias=categorias)

        valores = ler_form_produto(request.form)
        dados, erro = validar_produto(valores)
        if not erro and buscar_por_sku(conn, dados["sku_ean"]):
            erro = f"Já existe um produto cadastrado com o SKU/EAN {dados['sku_ean']}."
        if erro:
            return render_template("produto_form.html", modo="novo", valores=valores, erro=erro, categorias=categorias)

        conn.execute(
            "INSERT INTO estoque (sku_ean, descricao, categoria, unidade, custo_unitario, preco_venda, saldo_atual, validade) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (dados["sku_ean"], dados["descricao"], dados["categoria"], dados["unidade"],
             dados["custo_unitario"], dados["preco_venda"], dados["saldo_atual"], dados["validade"]),
        )
        conn.commit()
        return redirect(url_for("estoque", busca=dados["descricao"]))
    finally:
        conn.close()


@app.route("/produtos/<path:sku>/editar", methods=["GET", "POST"])
def produto_editar(sku):
    conn = get_conn()
    try:
        categorias = listar_categorias(conn)
        produto = conn.execute("SELECT * FROM estoque WHERE sku_ean = ?", (sku,)).fetchone()
        if not produto:
            abort(404)

        if request.method == "GET":
            valores = {campo: ("" if produto[campo] is None else str(produto[campo])) for campo in CAMPOS_PRODUTO}
            return render_template("produto_form.html", modo="editar", valores=valores, erro=None, categorias=categorias)

        valores = ler_form_produto(request.form)
        valores["sku_ean"] = sku  # SKU nao muda depois de criado (e referenciado por compras/vendas)
        dados, erro = validar_produto(valores)
        if erro:
            return render_template("produto_form.html", modo="editar", valores=valores, erro=erro, categorias=categorias)

        conn.execute(
            "UPDATE estoque SET descricao=?, categoria=?, unidade=?, custo_unitario=?, preco_venda=?, saldo_atual=?, validade=? "
            "WHERE sku_ean=?",
            (dados["descricao"], dados["categoria"], dados["unidade"], dados["custo_unitario"],
             dados["preco_venda"], dados["saldo_atual"], dados["validade"], sku),
        )
        conn.commit()
        return redirect(url_for("estoque", busca=dados["descricao"]))
    finally:
        conn.close()


@app.route("/compras")
def compras():
    conn = get_conn()
    try:
        historico = conn.execute(
            "SELECT c.id, c.data_compra, c.fornecedor, c.sku_ean, e.descricao, "
            "c.quantidade, c.custo_unitario, c.nota_fiscal "
            "FROM compras c JOIN estoque e ON e.sku_ean = c.sku_ean "
            "ORDER BY c.id DESC LIMIT 50"
        ).fetchall()
        return render_template("compras.html", historico=historico, hoje=date.today().isoformat())
    finally:
        conn.close()


@app.route("/api/compras", methods=["POST"])
def api_registrar_compra():
    dados = request.get_json(force=True, silent=True) or {}
    sku = str(dados.get("sku", "")).strip()
    fornecedor = str(dados.get("fornecedor") or "").strip() or None
    nota_fiscal = str(dados.get("nota_fiscal") or "").strip() or None
    data_compra = str(dados.get("data_compra") or "").strip() or date.today().isoformat()
    try:
        quantidade = float(dados.get("quantidade"))
        custo_unitario = float(dados.get("custo_unitario"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Quantidade e custo precisam ser números."}), 400

    if not sku:
        return jsonify({"erro": "SKU obrigatório."}), 400
    if quantidade <= 0:
        return jsonify({"erro": "Quantidade deve ser maior que zero."}), 400
    if custo_unitario < 0:
        return jsonify({"erro": "Custo não pode ser negativo."}), 400

    conn = get_conn()
    try:
        produto = conn.execute(
            "SELECT sku_ean, descricao, saldo_atual FROM estoque WHERE sku_ean = ?", (sku,)
        ).fetchone()
        if not produto:
            return jsonify({
                "erro": "Produto não cadastrado no estoque. Cadastre-o antes de lançar a compra.",
                "sku_nao_encontrado": True,
            }), 404

        descricao = produto["descricao"]
        novo_saldo = (produto["saldo_atual"] or 0) + quantidade

        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO compras (data_compra, fornecedor, sku_ean, quantidade, custo_unitario, nota_fiscal) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (data_compra, fornecedor, sku, quantidade, custo_unitario, nota_fiscal),
        )
        conn.execute(
            "UPDATE estoque SET saldo_atual = ?, custo_unitario = ? WHERE sku_ean = ?",
            (novo_saldo, custo_unitario, sku),
        )
        conn.commit()

        return jsonify({
            "ok": True,
            "sku_ean": sku,
            "descricao": descricao,
            "quantidade": quantidade,
            "custo_unitario": custo_unitario,
            "saldo_atual": novo_saldo,
        })
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.route("/historico")
def historico():
    conn = get_conn()
    try:
        vendas = conn.execute(
            "SELECT id, data_venda, produto_nome_raw, sku_ean, quantidade, valor_total, forma_pagamento "
            "FROM vendas ORDER BY id DESC LIMIT 50"
        ).fetchall()
        compras_lista = conn.execute(
            "SELECT c.id, c.data_compra, c.fornecedor, c.sku_ean, e.descricao, "
            "c.quantidade, c.custo_unitario, c.nota_fiscal "
            "FROM compras c LEFT JOIN estoque e ON e.sku_ean = c.sku_ean "
            "ORDER BY c.id DESC LIMIT 50"
        ).fetchall()
        return render_template("historico.html", vendas=vendas, compras=compras_lista)
    finally:
        conn.close()


@app.route("/vendas/<int:venda_id>/editar", methods=["GET", "POST"])
def venda_editar(venda_id):
    conn = get_conn()
    try:
        venda_row = conn.execute("SELECT * FROM vendas WHERE id = ?", (venda_id,)).fetchone()
        if not venda_row:
            abort(404)

        if request.method == "GET":
            preco_atual = round(venda_row["valor_total"] / venda_row["quantidade"], 2) if venda_row["quantidade"] else 0
            valores = {
                "quantidade": venda_row["quantidade"],
                "preco": preco_atual,
                "forma_pagamento": venda_row["forma_pagamento"] or "",
                "data_venda": venda_row["data_venda"],
            }
            return render_template("venda_editar.html", venda=venda_row, valores=valores, erro=None,
                                    formas_pagamento=FORMAS_PAGAMENTO)

        valores = {
            "quantidade": request.form.get("quantidade", ""),
            "preco": request.form.get("preco", ""),
            "forma_pagamento": request.form.get("forma_pagamento", ""),
            "data_venda": request.form.get("data_venda", ""),
        }
        try:
            nova_quantidade = float(valores["quantidade"])
            novo_preco = float(valores["preco"])
        except (TypeError, ValueError):
            return render_template("venda_editar.html", venda=venda_row, valores=valores,
                                    erro="Quantidade e preço precisam ser números.",
                                    formas_pagamento=FORMAS_PAGAMENTO)
        if nova_quantidade <= 0 or novo_preco < 0:
            return render_template("venda_editar.html", venda=venda_row, valores=valores,
                                    erro="Quantidade deve ser maior que zero e preço não pode ser negativo.",
                                    formas_pagamento=FORMAS_PAGAMENTO)

        forma_pagamento = valores["forma_pagamento"] or None
        if forma_pagamento is not None and forma_pagamento not in FORMAS_PAGAMENTO:
            return render_template("venda_editar.html", venda=venda_row, valores=valores,
                                    erro="Forma de pagamento inválida.", formas_pagamento=FORMAS_PAGAMENTO)

        data_venda = valores["data_venda"].strip() or venda_row["data_venda"]

        novo_valor_total = round(nova_quantidade * novo_preco, 2)

        conn.execute("BEGIN")
        if venda_row["sku_ean"]:
            produto = buscar_por_sku(conn, venda_row["sku_ean"])
            if produto is not None and produto["saldo_atual"] is not None:
                # devolve a quantidade antiga e tira a nova, num so passo
                saldo_ajustado = produto["saldo_atual"] + venda_row["quantidade"] - nova_quantidade
                conn.execute("UPDATE estoque SET saldo_atual = ? WHERE sku_ean = ?",
                             (saldo_ajustado, venda_row["sku_ean"]))
        conn.execute(
            "UPDATE vendas SET quantidade = ?, valor_total = ?, forma_pagamento = ?, data_venda = ? WHERE id = ?",
            (nova_quantidade, novo_valor_total, forma_pagamento, data_venda, venda_id),
        )
        conn.commit()
        return redirect(url_for("historico"))
    finally:
        conn.close()


@app.route("/vendas/<int:venda_id>/excluir", methods=["POST"])
def venda_excluir(venda_id):
    conn = get_conn()
    try:
        venda_row = conn.execute("SELECT * FROM vendas WHERE id = ?", (venda_id,)).fetchone()
        if not venda_row:
            abort(404)

        conn.execute("BEGIN")
        if venda_row["sku_ean"]:
            produto = buscar_por_sku(conn, venda_row["sku_ean"])
            if produto is not None and produto["saldo_atual"] is not None:
                conn.execute(
                    "UPDATE estoque SET saldo_atual = saldo_atual + ? WHERE sku_ean = ?",
                    (venda_row["quantidade"], venda_row["sku_ean"]),
                )
        conn.execute("DELETE FROM vendas WHERE id = ?", (venda_id,))
        conn.commit()
        return redirect(url_for("historico"))
    finally:
        conn.close()


@app.route("/compras/<int:compra_id>/editar", methods=["GET", "POST"])
def compra_editar(compra_id):
    conn = get_conn()
    try:
        compra_row = conn.execute("SELECT * FROM compras WHERE id = ?", (compra_id,)).fetchone()
        if not compra_row:
            abort(404)
        produto_ref = conn.execute(
            "SELECT descricao FROM estoque WHERE sku_ean = ?", (compra_row["sku_ean"],)
        ).fetchone()
        descricao = produto_ref["descricao"] if produto_ref else compra_row["sku_ean"]

        if request.method == "GET":
            valores = {
                "quantidade": compra_row["quantidade"],
                "custo_unitario": compra_row["custo_unitario"],
                "fornecedor": compra_row["fornecedor"] or "",
                "nota_fiscal": compra_row["nota_fiscal"] or "",
                "data_compra": compra_row["data_compra"],
            }
            return render_template("compra_editar.html", descricao=descricao, valores=valores, erro=None)

        valores = {
            "quantidade": request.form.get("quantidade", ""),
            "custo_unitario": request.form.get("custo_unitario", ""),
            "fornecedor": request.form.get("fornecedor", ""),
            "nota_fiscal": request.form.get("nota_fiscal", ""),
            "data_compra": request.form.get("data_compra", ""),
        }
        try:
            nova_quantidade = float(valores["quantidade"])
            novo_custo = float(valores["custo_unitario"])
        except (TypeError, ValueError):
            return render_template("compra_editar.html", descricao=descricao, valores=valores,
                                    erro="Quantidade e custo precisam ser números.")
        if nova_quantidade <= 0 or novo_custo < 0:
            return render_template("compra_editar.html", descricao=descricao, valores=valores,
                                    erro="Quantidade deve ser maior que zero e custo não pode ser negativo.")

        fornecedor = valores["fornecedor"].strip() or None
        nota_fiscal = valores["nota_fiscal"].strip() or None
        data_compra = valores["data_compra"].strip() or compra_row["data_compra"]

        conn.execute("BEGIN")
        produto = conn.execute(
            "SELECT saldo_atual FROM estoque WHERE sku_ean = ?", (compra_row["sku_ean"],)
        ).fetchone()
        if produto is not None and produto["saldo_atual"] is not None:
            # tira a quantidade antiga e poe a nova, num so passo
            saldo_ajustado = produto["saldo_atual"] - compra_row["quantidade"] + nova_quantidade
            conn.execute("UPDATE estoque SET saldo_atual = ? WHERE sku_ean = ?",
                         (saldo_ajustado, compra_row["sku_ean"]))
        conn.execute(
            "UPDATE compras SET quantidade=?, custo_unitario=?, fornecedor=?, nota_fiscal=?, data_compra=? WHERE id=?",
            (nova_quantidade, novo_custo, fornecedor, nota_fiscal, data_compra, compra_id),
        )
        conn.commit()
        return redirect(url_for("historico"))
    finally:
        conn.close()


@app.route("/compras/<int:compra_id>/excluir", methods=["POST"])
def compra_excluir(compra_id):
    conn = get_conn()
    try:
        compra_row = conn.execute("SELECT * FROM compras WHERE id = ?", (compra_id,)).fetchone()
        if not compra_row:
            abort(404)

        conn.execute("BEGIN")
        produto = conn.execute(
            "SELECT saldo_atual FROM estoque WHERE sku_ean = ?", (compra_row["sku_ean"],)
        ).fetchone()
        if produto is not None and produto["saldo_atual"] is not None:
            conn.execute(
                "UPDATE estoque SET saldo_atual = saldo_atual - ? WHERE sku_ean = ?",
                (compra_row["quantidade"], compra_row["sku_ean"]),
            )
        conn.execute("DELETE FROM compras WHERE id = ?", (compra_id,))
        conn.commit()
        return redirect(url_for("historico"))
    finally:
        conn.close()


@app.route("/relatorios")
def relatorios():
    conn = get_conn()
    try:
        hoje = date.today().isoformat()
        data_ini = request.args.get("data_ini", hoje) or hoje
        data_fim = request.args.get("data_fim", hoje) or hoje

        resumo = conn.execute(
            "SELECT COUNT(*) AS lancamentos, COALESCE(SUM(quantidade),0) AS itens, "
            "COALESCE(SUM(valor_total),0) AS total "
            "FROM vendas WHERE data_venda BETWEEN ? AND ?",
            (data_ini, data_fim),
        ).fetchone()

        por_pagamento = conn.execute(
            "SELECT COALESCE(forma_pagamento, 'Não informada') AS forma, COUNT(*) AS lancamentos, "
            "COALESCE(SUM(quantidade),0) AS itens, COALESCE(SUM(valor_total),0) AS total "
            "FROM vendas WHERE data_venda BETWEEN ? AND ? "
            "GROUP BY forma ORDER BY total DESC",
            (data_ini, data_fim),
        ).fetchall()

        mais_vendidos = conn.execute(
            "SELECT produto_nome_raw AS produto, SUM(quantidade) AS qtd, SUM(valor_total) AS total "
            "FROM vendas WHERE data_venda BETWEEN ? AND ? "
            "GROUP BY COALESCE(sku_ean, produto_nome_raw) "
            "ORDER BY total DESC LIMIT 20",
            (data_ini, data_fim),
        ).fetchall()

        compras_periodo = conn.execute(
            "SELECT COUNT(*) AS lancamentos, COALESCE(SUM(quantidade * custo_unitario),0) AS total "
            "FROM compras WHERE data_compra BETWEEN ? AND ?",
            (data_ini, data_fim),
        ).fetchone()

        return render_template(
            "relatorios.html",
            data_ini=data_ini, data_fim=data_fim, hoje=hoje,
            resumo=resumo, por_pagamento=por_pagamento,
            mais_vendidos=mais_vendidos, compras_periodo=compras_periodo,
        )
    finally:
        conn.close()


FRASE_CONFIRMACAO_ZERAR = "LIMPAR TUDO"


@app.route("/dashboard")
def dashboard():
    conn = get_conn()
    try:
        stats = {
            "produtos": conn.execute("SELECT COUNT(*) FROM estoque").fetchone()[0],
            "vendas": conn.execute("SELECT COUNT(*) FROM vendas").fetchone()[0],
            "compras": conn.execute("SELECT COUNT(*) FROM compras").fetchone()[0],
            "faturamento_total": conn.execute(
                "SELECT COALESCE(SUM(valor_total),0) FROM vendas").fetchone()[0],
        }

        backups_dir = os.path.join(BASE_DIR, "backups")
        ultimo_backup = None
        if os.path.isdir(backups_dir):
            arquivos = [f for f in os.listdir(backups_dir) if f.endswith(".db")]
            if arquivos:
                ultimo_backup = sorted(arquivos)[-1]

        tamanho_banco_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2) if os.path.exists(DB_PATH) else 0
        nome_loja = obter_config(conn, "nome_loja") or ""

        return render_template(
            "dashboard.html", stats=stats, ultimo_backup=ultimo_backup,
            tamanho_banco_mb=tamanho_banco_mb, frase_confirmacao=FRASE_CONFIRMACAO_ZERAR,
            nome_loja=nome_loja,
        )
    finally:
        conn.close()


@app.route("/dashboard/loja", methods=["POST"])
def dashboard_loja():
    conn = get_conn()
    try:
        nome_loja = request.form.get("nome_loja", "").strip()
        definir_config(conn, "nome_loja", nome_loja)
        conn.commit()
        flash("Nome da loja atualizado.", "ok")
        return redirect(url_for("dashboard"))
    finally:
        conn.close()


@app.route("/dashboard/zerar", methods=["POST"])
def dashboard_zerar():
    confirmacao = request.form.get("confirmacao", "").strip()
    if confirmacao != FRASE_CONFIRMACAO_ZERAR:
        flash(f'Confirmação incorreta. Digite exatamente "{FRASE_CONFIRMACAO_ZERAR}" pra confirmar.', "erro")
        return redirect(url_for("dashboard"))

    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM vendas")
        conn.execute("DELETE FROM compras")
        conn.execute("DELETE FROM caixa")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('vendas', 'compras', 'caixa')")
        conn.commit()
        flash("Vendas, compras e caixa foram zerados. O catálogo de produtos foi mantido.", "ok")
        return redirect(url_for("dashboard"))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.route("/dashboard/senha", methods=["POST"])
def dashboard_senha():
    conn = get_conn()
    try:
        senha_atual = request.form.get("senha_atual", "")
        nova = request.form.get("nova_senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        senha_hash = obter_config(conn, "senha_hash")
        if not senha_hash or not check_password_hash(senha_hash, senha_atual):
            flash("Senha atual incorreta.", "erro")
            return redirect(url_for("dashboard"))
        if len(nova) < 4:
            flash("A nova senha precisa ter pelo menos 4 caracteres.", "erro")
            return redirect(url_for("dashboard"))
        if nova != confirmar:
            flash("A confirmação não bate com a nova senha.", "erro")
            return redirect(url_for("dashboard"))

        definir_config(conn, "senha_hash", generate_password_hash(nova))
        conn.commit()
        flash("Senha alterada.", "ok")
        return redirect(url_for("dashboard"))
    finally:
        conn.close()


if __name__ == "__main__":
    # host="0.0.0.0" escuta em todas as interfaces de rede, nao so localhost —
    # e o que permite outro PC na mesma rede acessar via IP. debug=False de
    # proposito: o modo debug do Flask expõe um console que executa codigo
    # Python arbitrario em qualquer erro, o que vira um risco real assim que
    # o servidor sai de 127.0.0.1 e passa a ser alcancavel por outras maquinas.
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
