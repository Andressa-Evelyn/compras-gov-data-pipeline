from config import DB_CONFIG
import psycopg2
from psycopg2.extras import execute_values

def inicializar_banco():
    """
    Cria o schema, a tabela e configura os requisitos técnicos para o CDC.
    Deve ser chamado na primeira execução do pipeline.
    """
    ddl_query = """
    -- 1. Criação do Schema para organizar a área de Stage
    CREATE SCHEMA IF NOT EXISTS stage;

    -- 2. Criação da Tabela com Chave Primária e Timestamps
    CREATE TABLE IF NOT EXISTS stage.stg_atas_registro_precos (
        id_registro VARCHAR(150) PRIMARY KEY, -- Chave Primária Clara (Obrigatório para CDC)
        numero_ata VARCHAR(100) NOT NULL,
        orgao_gerenciador TEXT,
        objeto TEXT,
        cnpj_fornecedor VARCHAR(50),
        nome_fornecedor TEXT,
        item_numero INTEGER,
        descricao_item TEXT,
        quantidade_homologada NUMERIC(15, 4),
        valor_unitario NUMERIC(15, 4),
        valor_total NUMERIC(15, 4),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 3. Preparação para CDC (Change Data Capture) via Log
    -- Garante que o PostgreSQL registre no WAL (Write-Ahead Log) a chave primária
    -- da linha sempre que houver um UPDATE ou DELETE.
    ALTER TABLE stage.stg_atas_registro_precos REPLICA IDENTITY DEFAULT;
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(ddl_query)
        conn.commit()
        print("Banco de dados verificado/inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


def carregar_dados_postgresql(dados):
    """
    Persiste os dados de forma transacional usando UPSERT.
    """
    if not dados:
        print("Nenhum dado recebido para inserir no banco.")
        return

    # A query de UPSERT: Se o ID não existir, insere. Se existir, atualiza.
    query = """
        INSERT INTO stage.stg_atas_registro_precos (
            id_registro, numero_ata, orgao_gerenciador, objeto, cnpj_fornecedor, 
            nome_fornecedor, item_numero, descricao_item, quantidade_homologada, 
            valor_unitario, valor_total, atualizado_em
        ) VALUES %s
        ON CONFLICT (id_registro) DO UPDATE SET
            orgao_gerenciador = EXCLUDED.orgao_gerenciador,
            objeto = EXCLUDED.objeto,
            nome_fornecedor = EXCLUDED.nome_fornecedor,
            descricao_item = EXCLUDED.descricao_item,
            quantidade_homologada = EXCLUDED.quantidade_homologada,
            valor_unitario = EXCLUDED.valor_unitario,
            valor_total = EXCLUDED.valor_total,
            -- O campo criado_em fica intacto, alteramos apenas o atualizado_em
            atualizado_em = CURRENT_TIMESTAMP;
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # execute_values é otimizado para inserção em lote (batch transacional)
        execute_values(cursor, query, dados)
        conn.commit()
        
        print(f"Transação concluída: {len(dados)} registros inseridos/atualizados no Stage.")
    except Exception as e:
        print(f"Erro durante a transação no banco de dados: {e}")
        if conn:
            conn.rollback() # Em caso de erro, desfaz a transação inteira
    finally:
        if conn:
            cursor.close()
            conn.close()