"""
ATENCAO — script de migracao unica da Fase 1, ja usado e aposentado.

NAO RODE ISSO EM PRODUCAO. Ele APAGA o estoque.db inteiro (vendas, compras,
cadastro) e recria do zero a partir de planilhas Excel que nem existem mais
neste PC. Ficou aqui so por historico/referencia de como o catalogo inicial
foi montado. Se voce rodar por engano num PC sem essas planilhas em Downloads,
ele vai falhar com erro de arquivo nao encontrado — o que e o comportamento
seguro nesse caso.

Fontes originais (Fase 1, PC de desenvolvimento):
  - estoque_mestre_petro_importado.xlsx  -> tabela estoque (catalogo Petro, ~700 itens)
  - estoque_mestre.xlsx (aba Entrada Compras) -> tabela compras
  - controle_vendas.xlsx (aba Vendas)    -> tabela vendas

Pra acrescentar produtos novos ao catalogo, use importar_complemento.py —
esse sim e seguro de rodar em produção (so acrescenta, nunca apaga).
"""

import os
import re
import sqlite3
import sys
from datetime import datetime

import openpyxl

# Console do Windows usa cp1252 por padrao; forcar UTF-8 no stdout evita
# mojibake ao imprimir descricoes acentuadas no relatorio.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

DB_PATH = os.path.join(BASE_DIR, "estoque.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

PETRO_PATH = os.path.join(DOWNLOADS, "estoque_mestre_petro_importado.xlsx")
ESTOQUE_MESTRE_PATH = os.path.join(DOWNLOADS, "estoque_mestre.xlsx")
VENDAS_PATH = os.path.join(DOWNLOADS, "controle_vendas.xlsx")

PETRO_SHEET = "Estoque Mestre"
COMPRAS_SHEET = "Entrada Compras"
VENDAS_SHEET = "Vendas"


def parse_date(value):
    """Aceita 'dd/mm/aaaa' (texto) ou datetime/date do Excel. Retorna ISO 'aaaa-mm-dd' ou None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def to_float(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def to_sku(value):
    """Normaliza SKU/EAN pra texto, sem perder zeros a esquerda e sem sufixo '.0'."""
    if value is None or value == "":
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def load_workbook_rows(path, sheet_name):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet_name]
    rows = ws.iter_rows(min_row=2, values_only=True)
    return list(rows)


def normalize_words(text):
    text = re.sub(r"[^A-Za-z0-9 ]", " ", text.upper())
    return set(w for w in text.split() if w)


def import_estoque(conn):
    rows = load_workbook_rows(PETRO_PATH, PETRO_SHEET)
    n = 0
    for row in rows:
        sku = to_sku(row[0])
        descricao = row[1]
        if not sku or not descricao:
            continue
        categoria, unidade, custo, preco, saldo, validade = row[2], row[3], row[4], row[5], row[6], row[7]
        conn.execute(
            """INSERT OR REPLACE INTO estoque
               (sku_ean, descricao, categoria, unidade, custo_unitario, preco_venda, saldo_atual, validade)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sku, str(descricao).strip(), categoria, unidade, to_float(custo), to_float(preco),
             to_float(saldo), parse_date(validade)),
        )
        n += 1
    return n


def ensure_estoque_row(conn, sku, descricao, custo_unitario=None):
    """Cria um item minimo em estoque se a compra referenciar um SKU ainda nao catalogado."""
    cur = conn.execute("SELECT 1 FROM estoque WHERE sku_ean = ?", (sku,))
    if cur.fetchone():
        return False
    conn.execute(
        """INSERT INTO estoque (sku_ean, descricao, categoria, unidade, custo_unitario, preco_venda, saldo_atual, validade)
           VALUES (?, ?, NULL, 'UN', ?, NULL, NULL, NULL)""",
        (sku, str(descricao).strip() if descricao else sku, custo_unitario),
    )
    return True


def import_compras(conn):
    rows = load_workbook_rows(ESTOQUE_MESTRE_PATH, COMPRAS_SHEET)
    n = 0
    criados = 0
    for row in rows:
        data_compra, fornecedor, sku_raw, produto, quantidade, custo, nf = row
        sku = to_sku(sku_raw)
        if not sku or quantidade is None:
            continue
        custo_f = to_float(custo)
        if ensure_estoque_row(conn, sku, produto, custo_f):
            criados += 1
        conn.execute(
            """INSERT INTO compras (data_compra, fornecedor, sku_ean, quantidade, custo_unitario, nota_fiscal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (parse_date(data_compra), fornecedor, sku, to_float(quantidade), custo_f,
             str(nf).strip() if nf is not None else None),
        )
        n += 1
    return n, criados


def build_estoque_index(conn):
    cur = conn.execute("SELECT sku_ean, descricao FROM estoque")
    index = []
    for sku, descricao in cur.fetchall():
        index.append((sku, descricao, normalize_words(descricao)))
    return index


def match_produto(produto_nome, estoque_index):
    """Casa produto_nome (texto livre da venda) com descricao do estoque.
    So retorna SKU quando ha exatamente 1 candidato inequivoco (todas as palavras do
    nome da venda aparecem na descricao). Ambiguo ou sem match -> None."""
    palavras_venda = normalize_words(produto_nome)
    if not palavras_venda:
        return None, []
    candidatos = [
        (sku, descricao) for sku, descricao, palavras_desc in estoque_index
        if palavras_venda.issubset(palavras_desc)
    ]
    if len(candidatos) == 1:
        return candidatos[0][0], candidatos
    return None, candidatos


def import_vendas(conn):
    rows = load_workbook_rows(VENDAS_PATH, VENDAS_SHEET)
    estoque_index = build_estoque_index(conn)
    n = 0
    sem_match = []
    ambiguos = []
    for row in rows:
        data_venda, produto, qtd, valor = row[0], row[1], row[2], row[3]
        if not produto or qtd is None or valor is None:
            continue
        sku, candidatos = match_produto(str(produto), estoque_index)
        if sku is None:
            if len(candidatos) > 1:
                ambiguos.append((produto, [c[1] for c in candidatos]))
            else:
                sem_match.append(produto)
        conn.execute(
            """INSERT INTO vendas (data_venda, produto_nome_raw, sku_ean, quantidade, valor_total)
               VALUES (?, ?, ?, ?, ?)""",
            (parse_date(data_venda), str(produto).strip(), sku, to_float(qtd), to_float(valor)),
        )
        n += 1
    return n, sem_match, ambiguos


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    n_estoque = import_estoque(conn)
    n_compras, criados = import_compras(conn)
    n_vendas, sem_match, ambiguos = import_vendas(conn)

    conn.commit()
    conn.close()

    print(f"Banco criado em: {DB_PATH}")
    print(f"  estoque: {n_estoque} itens importados do catalogo Petro")
    print(f"  compras: {n_compras} lancamentos ({criados} SKU(s) novo(s) criado(s) automaticamente em estoque)")
    print(f"  vendas:  {n_vendas} lancamentos")

    if sem_match:
        print(f"\n  Vendas SEM correspondencia em estoque ({len(sem_match)}) — revisar manualmente:")
        for p in sem_match:
            print(f"    - {p!r}")

    if ambiguos:
        print(f"\n  Vendas AMBIGUAS ({len(ambiguos)}) — mais de um item de estoque casou com o nome:")
        for produto, candidatos in ambiguos:
            print(f"    - {produto!r} -> {candidatos}")


if __name__ == "__main__":
    main()
