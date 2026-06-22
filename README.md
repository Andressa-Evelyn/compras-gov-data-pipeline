# 🚀 Pipeline de Dados - Atas de Registro de Preços (ARP)

Este projeto implementa um pipeline de dados ponta a ponta para extração, processamento e visualização de dados de compras públicas do Governo Federal (API Compras.gov.br). A solução utiliza conceitos modernos de RPA, Change Data Capture (CDC) e Data Warehousing.

---

## 🏗️ Desenho da Arquitetura

O fluxo de dados segue uma abordagem transacional-para-analítica em tempo real:

1. **Extração (RPA em Python):** Consome a API do governo e realiza UPSERT na área de Stage.
2. **Armazenamento Transacional (PostgreSQL):** Funciona como Stage e mantém o estado atualizado dos dados.
3. **Change Data Capture (Debezium/Kafka):** Monitora o Write-Ahead Log (WAL) do Postgres e transmite as alterações (inserts/updates).
4. **Data Warehouse (ClickHouse):** Recebe os dados via CDC e organiza as informações em um modelo dimensional para alta performance de leitura.
5. **Business Intelligence (Apache Superset):** Consome do ClickHouse para renderizar os dashboards interativos.

📊 Diagrama Entidade-Relacionamento (DER)
O modelo analítico no ClickHouse segue a modelagem dimensional (Star Schema), otimizado para agregações de BI, composto por uma tabela Fato consolidada e dimensões de suporte.

erDiagram
    FATO_REGISTRO_PRECOS {
        Date data_processamento
        String cnpj_fornecedor FK
        String id_orgao FK
        Float64 volume_financeiro_homologado
        Int32 total_atas
        Int32 total_itens
    }

    DIM_ITENS {
        String id_registro PK
        String numero_ata
        String cnpj_fornecedor FK
        String id_orgao FK
        String objeto
        Int32 item_numero
        String descricao_item
        Float64 quantidade_homologada
        Float64 valor_unitario
        Float64 valor_total
        DateTime atualizado_em
    }

    DIM_FORNECEDORES {
        String cnpj_fornecedor PK
        String nome_fornecedor
    }

    DIM_ORGAOS {
        String id_orgao PK
        String orgao_gerenciador
    }

    FATO_REGISTRO_PRECOS }|--|| DIM_FORNECEDORES : "Pertence a"
    FATO_REGISTRO_PRECOS }|--|| DIM_ORGAOS : "Gerenciado por"
    DIM_ITENS }|--|| DIM_FORNECEDORES : "Fornecido por"
    DIM_ITENS }|--|| DIM_ORGAOS : "Requisitado por"

🛠️ Tecnologias Utilizadas
Linguagens: Python 3.10 (RPA/Scripts), Go (Worker de Ingestão)

Bancos de Dados: PostgreSQL 15 (OLTP), ClickHouse 23.8 (OLAP)

Streaming & CDC: Apache Kafka, Debezium Connect 2.4

Orquestração: Apache Airflow 2.7.1

Visualização: Apache Superset 3.1.0

Infraestrutura: Docker & Docker Compose

🚀 Como Executar o Projeto
Pré-requisitos
Docker e Docker Compose instalados.

Go (Golang) instalado localmente (para rodar o worker).

Ambiente virtual Python configurado (venv).

1. Subir a Infraestrutura
Na raiz do projeto, execute o comando para inicializar todos os containers em background:

Bash
docker compose up -d
2. Configurar os Bancos de Dados e Conectores
Execute as migrações estruturais e ative o conector do Debezium para iniciar o CDC lógico do PostgreSQL:

Bash
# Inicializar tabelas analíticas no ClickHouse
cat sql/init_clickhouse.sql | docker exec -i clickhouse-rpa clickhouse-client --multiquery

# Registrar o conector no Debezium Connect
curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" localhost:8083/connectors/ -d @debezium_config.json
3. Inicializar o Superset (Primeiro Acesso)
Execute o setup inicial para criar as credenciais do painel de BI:

Bash
# Executa migrações do Superset e cria usuário admin (admin/admin)
docker exec -it superset-rpa superset db upgrade
docker exec -it superset-rpa superset fab create-admin --username admin --firstname Admin --lastname Admin --email admin@example.com --password admin
docker exec -it superset-rpa superset init
4. Executar os Workers e Scripts de Captura
Abra terminais dedicados para rodar o fluxo de ingestão:

Bash
# Terminal 1: Iniciar o Go Worker (Consumidor Kafka -> ClickHouse)
cd go-worker
go mod tidy
go run main.go config.go

# Terminal 2: Executar a Extração do Script RPA (Python)
source venv/bin/activate
pip install -r requirements.txt
python -m src.main
5. Orquestração e Dashboards
Airflow UI: Acesse http://localhost:8080 (admin/admin) para ativar a DAG dag_fato_compras e consolidar as tabelas analíticas.

Superset UI: Acesse http://localhost:8088 (admin/admin) para criar e visualizar os gráficos baseados nas tabelas do ClickHouse.