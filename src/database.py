from config import DB_CONFIG
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

def inicializar_banco():
    """
    Cria o schema, a tabela e configura os requisitos técnicos para o CDC.
    """
    ddl_query = """
    -- 1. Criação do Schema para organizar a área de Stage
    CREATE SCHEMA IF NOT EXISTS stage;

    -- 3. Criação da Tabela (Agora com DOUBLE PRECISION no lugar de NUMERIC)
    CREATE TABLE stage.stg_atas_registro_precos (
        id_registro VARCHAR(150) PRIMARY KEY,
        numero_ata VARCHAR(100) NOT NULL,
        orgao_gerenciador TEXT,
        objeto TEXT,
        cnpj_fornecedor VARCHAR(50),
        nome_fornecedor TEXT,
        item_numero INTEGER,
        descricao_item TEXT,
        quantidade_homologada DOUBLE PRECISION,
        valor_unitario DOUBLE PRECISION,
        valor_total DOUBLE PRECISION,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. Preparação para CDC (Change Data Capture)
    ALTER TABLE stage.stg_atas_registro_precos REPLICA IDENTITY DEFAULT;
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(ddl_query)
        conn.commit()
        print("Banco de dados reinicializado com novos tipos de dados (DOUBLE PRECISION).")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

def limpar_moeda(valor):
    """
    Remove formatação brasileira (ex: 1.500,00 -> 1500.00) 
    para salvar com segurança no banco de dados.
    """
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    val_str = str(valor).strip()
    if not val_str or val_str.lower() in ['none', 'null', '']:
        return 0.0
    
    try:
        if '.' in val_str and ',' in val_str:
            val_str = val_str.replace('.', '')
        val_str = val_str.replace(',', '.')
        return float(val_str)
    except ValueError:
        return 0.0


def carregar_dados_postgresql(dados):
    """
    Persiste os dados de forma transacional usando UPSERT,
    aplicando a limpeza de dados numéricos antes da inserção.
    """
    if not dados:
        print("Nenhum dado recebido para inserir no banco.")
        return

    # Tratamento dos dados brutos recebidos
    dados_tratados = []
    agora = datetime.now()
    
    for item in dados:
        # Se os dados vierem do extractor como dicionários
        if isinstance(item, dict):
            qtd = limpar_moeda(item.get('quantidade_homologada'))
            v_unit = limpar_moeda(item.get('valor_unitario'))
            v_total = limpar_moeda(item.get('valor_total'))
            
            # Recalcula o total caso a API tenha enviado zerado/nulo
            if v_total == 0.0 and v_unit > 0 and qtd > 0:
                v_total = qtd * v_unit
                
            dados_tratados.append((
                item.get('id_registro'),
                item.get('numero_ata'),
                item.get('orgao_gerenciador'),
                item.get('objeto'),
                item.get('cnpj_fornecedor'),
                item.get('nome_fornecedor'),
                item.get('item_numero'),
                item.get('descricao_item'),
                qtd,
                v_unit,
                v_total,
                agora # Preenche o atualizado_em exigido pelo VALUES
            ))
        # Se os dados já vierem como tuplas/listas
        elif isinstance(item, (list, tuple)):
            lista_item = list(item)
            # Índices correspondentes às colunas numéricas no INSERT
            qtd = limpar_moeda(lista_item[8])
            v_unit = limpar_moeda(lista_item[9])
            v_total = limpar_moeda(lista_item[10])
            
            if v_total == 0.0 and v_unit > 0 and qtd > 0:
                v_total = qtd * v_unit
                
            lista_item[8] = qtd
            lista_item[9] = v_unit
            lista_item[10] = v_total
            
            # Adiciona o timestamp caso a tupla só tenha 11 colunas
            if len(lista_item) == 11:
                lista_item.append(agora)
                
            dados_tratados.append(tuple(lista_item))

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
        
        # Inserindo os dados TRATADOS
        execute_values(cursor, query, dados_tratados)
        conn.commit()
        
        print(f"Transação concluída: {len(dados_tratados)} registros inseridos/atualizados no Stage com valores corrigidos.")
    except Exception as e:
        print(f"Erro durante a transação no banco de dados: {e}")
        if conn:
            conn.rollback() # Em caso de erro, desfaz a transação inteira
    finally:
        if conn:
            cursor.close()
            conn.close()