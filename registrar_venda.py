"""
Fase 2 — Registro de venda no terminal, com baixa automatica de estoque.

Fluxo por item:
  1. Localiza o produto por SKU/EAN exato ou por busca textual na descricao.
  2. Pede quantidade e preco (sugere preco_venda do cadastro, aceita sobrescrever).
  3. Avisa se o saldo ficaria negativo, mas nao bloqueia (inventario fisico
     ainda nao foi fechado, entao nem todo saldo_atual e confiavel hoje).
  4. Grava a venda e decrementa o saldo em estoque numa unica transacao —
     se uma das duas operacoes falhar, nenhuma e efetivada.

Roda em loop ate o operador digitar 'fim'. Preparado pra virar leitura por
leitor de codigo de barras USB na Fase 4: SKU/EAN completo bate direto,
sem passar pela busca textual.
"""

import os
import sqlite3
import sys

# Console do Windows usa cp1252 por padrao pro stdin/stdout do Python; forcar
# UTF-8 evita corromper acentos (nomes de produto) e bytes de BOM vindos de
# redirecionamento/colar texto.
if sys.stdin.encoding and sys.stdin.encoding.lower() != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "estoque.db")


class ItemCancelado(Exception):
    pass


BOM = "﻿"


def ask(prompt):
    return input(prompt).strip().lstrip(BOM)


def ask_float(prompt, default=None, min_value=None):
    while True:
        raw = ask(prompt)
        if raw.lower() in ("cancelar", "cancel"):
            raise ItemCancelado()
        if raw == "" and default is not None:
            return default
        try:
            valor = float(raw.replace(",", "."))
        except ValueError:
            print("  Valor invalido. Digite um numero (ou 'cancelar').")
            continue
        if min_value is not None and valor < min_value:
            print(f"  Valor deve ser >= {min_value}.")
            continue
        return valor


def buscar_por_sku(conn, sku):
    cur = conn.execute(
        "SELECT sku_ean, descricao, preco_venda, saldo_atual FROM estoque WHERE sku_ean = ?",
        (sku,),
    )
    return cur.fetchone()


def buscar_por_texto(conn, termo, limite=20):
    palavras = termo.upper().split()
    if not palavras:
        return []
    condicoes = " AND ".join(["UPPER(descricao) LIKE ?" for _ in palavras])
    params = [f"%{p}%" for p in palavras]
    cur = conn.execute(
        f"SELECT sku_ean, descricao, preco_venda, saldo_atual FROM estoque "
        f"WHERE {condicoes} ORDER BY descricao LIMIT ?",
        params + [limite + 1],
    )
    return cur.fetchall()


def formatar_produto(p):
    sku, descricao, preco, saldo = p
    preco_txt = f"R$ {preco:.2f}" if preco is not None else "sem preco"
    saldo_txt = f"{saldo:g}" if saldo is not None else "sem contagem"
    return f"{sku} - {descricao} - {preco_txt} - saldo: {saldo_txt}"


def selecionar_produto(conn):
    while True:
        termo = ask("\nSKU/EAN ou nome do produto ('fim' encerra): ")
        if termo.lower() in ("fim", "sair", ""):
            return None

        if termo.isdigit():
            produto = buscar_por_sku(conn, termo)
            if produto:
                return produto
            print("  SKU nao encontrado no cadastro, tentando como busca por nome...")

        resultados = buscar_por_texto(conn, termo)
        if not resultados:
            print("  Nenhum produto encontrado. Tente outro termo.")
            continue

        limitado = len(resultados) > 20
        resultados = resultados[:20]
        for i, p in enumerate(resultados, start=1):
            print(f"  {i}) {formatar_produto(p)}")
        if limitado:
            print("  (mais de 20 resultados, refine a busca se nao achar o item)")

        escolha = ask("Numero do item (Enter cancela a busca): ")
        if escolha == "":
            continue
        if escolha.isdigit() and 1 <= int(escolha) <= len(resultados):
            return resultados[int(escolha) - 1]
        print("  Opcao invalida.")


def registrar_item(conn, produto):
    sku, descricao, preco_venda, saldo_atual = produto
    print(f"\n{descricao}")

    quantidade = ask_float("Quantidade: ", min_value=0.0001)

    if preco_venda is not None:
        preco = ask_float(f"Preco unitario [R$ {preco_venda:.2f}]: ", default=preco_venda, min_value=0)
    else:
        print("  Item sem preco de venda cadastrado.")
        preco = ask_float("Preco unitario: ", min_value=0)

    valor_total = round(quantidade * preco, 2)

    if saldo_atual is None:
        print("  Aviso: item sem contagem de estoque (inventario pendente) — saldo nao sera decrementado.")
    elif quantidade > saldo_atual:
        print(f"  Aviso: saldo atual e {saldo_atual:g}, ficaria negativo ({saldo_atual - quantidade:g}).")

    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO vendas (data_venda, produto_nome_raw, sku_ean, quantidade, valor_total) "
            "VALUES (date('now', 'localtime'), ?, ?, ?, ?)",
            (descricao, sku, quantidade, valor_total),
        )
        if saldo_atual is not None:
            conn.execute(
                "UPDATE estoque SET saldo_atual = saldo_atual - ? WHERE sku_ean = ?",
                (quantidade, sku),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    print(f"  OK: {quantidade:g}x {descricao} = R$ {valor_total:.2f}")
    return descricao, quantidade, valor_total


def main():
    if not os.path.exists(DB_PATH):
        print(f"Banco nao encontrado em {DB_PATH}. Rode import_dados.py primeiro.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("=== Registro de venda ===")
    itens_vendidos = []

    try:
        while True:
            produto = selecionar_produto(conn)
            if produto is None:
                break
            try:
                itens_vendidos.append(registrar_item(conn, produto))
            except ItemCancelado:
                print("  Item cancelado.")
                continue
    except KeyboardInterrupt:
        print("\nInterrompido pelo operador.")
    finally:
        conn.close()

    if itens_vendidos:
        print("\n=== Resumo da venda ===")
        total = 0.0
        for descricao, quantidade, valor_total in itens_vendidos:
            print(f"  {quantidade:g}x {descricao} = R$ {valor_total:.2f}")
            total += valor_total
        print(f"Total: R$ {total:.2f}")
    else:
        print("\nNenhum item registrado.")


if __name__ == "__main__":
    main()
