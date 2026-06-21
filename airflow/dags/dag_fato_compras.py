from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, date
import pandas as pd
import clickhouse_connect

default_args = {
    'owner': 'engenharia_dados',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
}

def processar_camada_fato():
    """
    Job em Python/Pandas que consolida os dados do ClickHouse
    """
    print("Conectando ao banco de dados analítico (ClickHouse)...")
    client = clickhouse_connect.get_client(host='clickhouse-rpa', port=8123, database='analytics')
    
    # 1. EXTRAÇÃO: Busca os dados da tabela Fato/Dimensão Detalhada
    # O comando 'FINAL' garante que estamos pegando a versão mais atual de cada linha (CDC)
    query = "SELECT * FROM dim_itens FINAL"
    df_itens = client.query_df(query)
    
    if df_itens.empty:
        print("Nenhum dado encontrado para processar.")
        return

    print(f"{len(df_itens)} registros extraídos. Iniciando processamento Batch...")

    # 2. TRANSFORMAÇÃO E ENRIQUECIMENTO (Pandas)
    df_itens['valor_total'] = df_itens['valor_total'].astype(float)
    df_itens['valor_unitario'] = df_itens['valor_unitario'].astype(float)
    
    # Construção da Fato Agregada (Métricas de Negócio)
    df_fato = df_itens.groupby(['id_orgao', 'cnpj_fornecedor']).agg(
        total_atas=('numero_ata', 'nunique'),
        total_itens=('item_numero', 'count'),
        volume_financeiro_homologado=('valor_total', 'sum'),
        preco_medio_unitario=('valor_unitario', 'mean')
    ).reset_index()
    
    # Adicionando metadados de controle temporal
    hoje = date.today()
    df_fato['data_processamento'] = hoje
    df_fato['atualizado_em'] = datetime.now()
    
    # Reordenando colunas para casar exatamente com a DDL da tabela no ClickHouse
    colunas_finais = [
        'data_processamento', 'id_orgao', 'cnpj_fornecedor', 'total_atas', 
        'total_itens', 'volume_financeiro_homologado', 'preco_medio_unitario', 'atualizado_em'
    ]
    df_fato = df_fato[colunas_finais]

    # 3. CARGA: Persistindo a Fato consolidada
    client.command(f"ALTER TABLE fato_registro_precos DELETE WHERE data_processamento = '{hoje}'")
    
    print(f"Inserindo {len(df_fato)} linhas agregadas na tabela fato_registro_precos...")
    client.insert_df('fato_registro_precos', df_fato)
    print("Job Batch finalizado com Sucesso!")


with DAG(
    'processamento_batch_atas',
    default_args=default_args,
    description='Job analítico para consolidação da Tabela Fato no ClickHouse',
    schedule_interval='@daily', 
    start_date=datetime(2024, 1, 1),
    catchup=False, # Impede que rode retroativamente para os dias que o Airflow esteve desligado
    tags=['financeiro', 'compras', 'batch'],
) as dag:

    task_processar_fato = PythonOperator(
        task_id='consolidar_fato_compras',
        python_callable=processar_camada_fato,
    )