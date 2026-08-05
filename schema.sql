-- Schema Fase 1 — controle de conveniência de posto
-- SQLite. Datas gravadas em texto ISO-8601 (YYYY-MM-DD) por ordenação/comparação simples.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS estoque (
    sku_ean         TEXT PRIMARY KEY,
    descricao       TEXT NOT NULL,
    categoria       TEXT,
    unidade         TEXT,
    custo_unitario  REAL,
    preco_venda     REAL,
    saldo_atual     REAL,
    validade        TEXT,
    favorito        INTEGER NOT NULL DEFAULT 0,
    estoque_minimo  REAL
);

CREATE TABLE IF NOT EXISTS compras (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    data_compra     TEXT NOT NULL,
    fornecedor      TEXT,
    sku_ean         TEXT NOT NULL REFERENCES estoque(sku_ean),
    quantidade      REAL NOT NULL,
    custo_unitario  REAL,
    nota_fiscal     TEXT
);

CREATE TABLE IF NOT EXISTS caixa (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    data                TEXT NOT NULL,
    hora_abertura       TEXT NOT NULL,
    valor_abertura      REAL NOT NULL,
    hora_fechamento     TEXT,
    valor_fechamento    REAL,
    observacoes         TEXT,
    operador_abertura   TEXT,
    operador_fechamento TEXT
);

-- Sangria (retirada) e reforco (entrada extra) de dinheiro durante o turno,
-- sem precisar fechar o caixa pra isso. Sem registrar, essas movimentacoes
-- viram diferenca "fantasma" na hora de conferir a gaveta.
CREATE TABLE IF NOT EXISTS caixa_movimentacoes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    caixa_id    INTEGER NOT NULL REFERENCES caixa(id),
    tipo        TEXT NOT NULL CHECK (tipo IN ('sangria', 'reforco')),
    valor       REAL NOT NULL,
    motivo      TEXT,
    hora        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    data_venda          TEXT NOT NULL,
    produto_nome_raw    TEXT NOT NULL,
    sku_ean             TEXT REFERENCES estoque(sku_ean),
    quantidade          REAL NOT NULL,
    valor_total         REAL NOT NULL,
    forma_pagamento     TEXT,
    caixa_id            INTEGER REFERENCES caixa(id),
    venda_grupo         TEXT
);

-- Configuracoes simples do sistema (senha de acesso, etc), guardadas como
-- pares chave/valor pra nao precisar de migracao de schema a cada ajuste.
CREATE TABLE IF NOT EXISTS config (
    chave   TEXT PRIMARY KEY,
    valor   TEXT
);

CREATE INDEX IF NOT EXISTS idx_compras_sku ON compras(sku_ean);
CREATE INDEX IF NOT EXISTS idx_compras_data ON compras(data_compra);
CREATE INDEX IF NOT EXISTS idx_vendas_sku ON vendas(sku_ean);
CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_venda);
CREATE INDEX IF NOT EXISTS idx_vendas_caixa ON vendas(caixa_id);
CREATE INDEX IF NOT EXISTS idx_caixa_mov_caixa ON caixa_movimentacoes(caixa_id);
CREATE INDEX IF NOT EXISTS idx_vendas_grupo ON vendas(venda_grupo);
CREATE INDEX IF NOT EXISTS idx_estoque_categoria ON estoque(categoria);
CREATE INDEX IF NOT EXISTS idx_estoque_favorito ON estoque(favorito);
