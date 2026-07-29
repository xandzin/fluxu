"""
Acrescenta produtos novos ao estoque a partir de um CSV complementar do
catalogo Petro (mesmas colunas do estoque_mestre_petro_importado.xlsx
original: SKU/EAN, Descricao, Categoria, Unidade, Custo Unitario, Preco
Venda, Saldo Contado, Validade).

Diferente do import_dados.py (que recria o banco do zero), este script SO
ACRESCENTA: nunca apaga nem sobrescreve venda, compra ou produto que ja
exista — se o SKU ja estiver cadastrado, a linha e pulada (nada e alterado,
mesmo que a descricao/categoria no CSV seja diferente). Seguro de rodar
quantas vezes quiser, com CSVs diferentes.

Uso:
    python importar_complemento.py caminho\\para\\arquivo.csv
"""

import csv
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "estoque.db")


def main():
    if len(sys.argv) < 2:
        print("Uso: python importar_complemento.py caminho\\para\\arquivo.csv")
        sys.exit(1)

    caminho_csv = sys.argv[1]
    if not os.path.exists(caminho_csv):
        print(f"Arquivo nao encontrado: {caminho_csv}")
        sys.exit(1)
    if not os.path.exists(DB_PATH):
        print(f"Banco nao encontrado em {DB_PATH}. Rode import_dados.py primeiro (uma unica vez).")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    novos = 0
    ja_existiam = []
    ignorados = 0
    vistos_no_csv = set()
    duplicados_no_csv = []

    with open(caminho_csv, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        for linha in leitor:
            sku = (linha.get("SKU/EAN") or "").strip()
            descricao = (linha.get("Descricao") or "").strip()
            if not sku or not descricao:
                ignorados += 1
                continue

            if sku in vistos_no_csv:
                duplicados_no_csv.append(sku)
                continue
            vistos_no_csv.add(sku)

            existe = conn.execute("SELECT 1 FROM estoque WHERE sku_ean = ?", (sku,)).fetchone()
            if existe:
                ja_existiam.append((sku, descricao))
                continue

            categoria = (linha.get("Categoria") or "").strip() or None
            unidade = (linha.get("Unidade") or "UN").strip() or "UN"

            conn.execute(
                "INSERT INTO estoque (sku_ean, descricao, categoria, unidade, "
                "custo_unitario, preco_venda, saldo_atual, validade) "
                "VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL)",
                (sku, descricao, categoria, unidade),
            )
            novos += 1

    conn.commit()
    conn.close()

    print(f"Arquivo: {caminho_csv}")
    print(f"Produtos novos adicionados ao estoque: {novos}")
    print(f"Ja existiam (pulados, nada foi sobrescrito): {len(ja_existiam)}")
    if ja_existiam:
        for sku, descricao in ja_existiam[:10]:
            print(f"    - {sku} {descricao}")
        if len(ja_existiam) > 10:
            print(f"    ... e mais {len(ja_existiam) - 10}")
    if duplicados_no_csv:
        print(f"SKUs duplicados dentro do proprio CSV (so a primeira ocorrencia foi usada): {len(duplicados_no_csv)}")
    if ignorados:
        print(f"Linhas ignoradas (sem SKU ou descricao): {ignorados}")


if __name__ == "__main__":
    main()
