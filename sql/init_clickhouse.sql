CREATE DATABASE IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.dim_fornecedores (
    cnpj_fornecedor String,
    nome_fornecedor String,
    atualizado_em DateTime
) ENGINE = ReplacingMergeTree(atualizado_em)
ORDER BY cnpj_fornecedor;

CREATE TABLE IF NOT EXISTS analytics.dim_orgaos (
    id_orgao UInt64,
    orgao_gerenciador String,
    atualizado_em DateTime
) ENGINE = ReplacingMergeTree(atualizado_em)
ORDER BY id_orgao;

CREATE TABLE IF NOT EXISTS analytics.dim_itens (
    id_registro String,
    numero_ata String,
    cnpj_fornecedor String,
    id_orgao UInt64,
    objeto String,
    item_numero Int32,
    descricao_item String,
    quantidade_homologada Decimal(18, 4),
    valor_unitario Decimal(18, 4),
    valor_total Decimal(18, 4),
    atualizado_em DateTime
) ENGINE = ReplacingMergeTree(atualizado_em)
ORDER BY (numero_ata, item_numero);