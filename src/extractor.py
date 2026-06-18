import requests
import time
from datetime import datetime

API_BASE_URL = "https://dadosabertos.compras.gov.br"

def extrair_dados_api(data_inicio, data_fim):
    """
    Função principal que o main.py chamará.
    Orquestra a busca das Atas e, em seguida, a extração dos Itens.
    """
    print(f"--- Iniciando busca de Atas ({data_inicio} até {data_fim}) ---")
    atas = buscar_capa_atas(data_inicio, data_fim)
    
    if not atas:
        print("Nenhuma ata encontrada no período especificado.")
        return []
        
    print(f"Total de Atas identificadas: {len(atas)}")
    
    # Passa as atas encontradas para buscar os itens de cada uma
    dados_completos = buscar_itens_das_atas(atas)
    return dados_completos


def buscar_capa_atas(data_inicio, data_fim):
    """
    Consome o endpoint 1_consultarARP.
    Retorna uma lista de dicionários contendo os dados gerais da Ata + o ID do PNCP.
    """
    endpoint = f"{API_BASE_URL}/modulo-arp/1_consultarARP"
    pagina_atual = 1
    tem_mais_dados = True
    atas_encontradas = []

    while tem_mais_dados:
        params = {
            "pagina": pagina_atual, 
            "dataVigenciaInicialMin": data_inicio, 
            "dataVigenciaInicialMax": data_fim
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            dados = response.json()
            
            registros = dados.get("resultado", [])
            print(f"Página {pagina_atual}: Encontrados {len(registros)} registros (Atas)")
            
            for item in registros:
                if "numeroControlePncpAta" in item:
                    # Capturamos o número PNCP (para a próxima requisição) e os dados da capa
                    atas_encontradas.append({
                        "pncp_ata": item["numeroControlePncpAta"],
                        "numero_ata": item.get("numeroAtaRegistroPreco", "N/A"),
                        "orgao_gerenciador": item.get("nomeUnidadeGerenciadora") or item.get("nomeOrgao", "N/A"),
                        "objeto": item.get("objeto", "Sem descrição de objeto")
                    })
            
            if dados.get("paginasRestantes", 0) == 0:
                tem_mais_dados = False
            else:
                pagina_atual += 1
                time.sleep(0.5) # Pausa para evitar bloqueio da API
                
        except Exception as e:
            print(f"Erro ao listar atas na página {pagina_atual}: {e}")
            break
            
    return atas_encontradas


def buscar_itens_das_atas(atas):
    """
    Consome o endpoint 2.1_consultarARPItem_Id para cada Ata encontrada.
    Cruza as informações da Capa com os Itens e retorna as tuplas para o banco de dados.
    """
    # Endpoint correto para buscar itens via ID/PNCP da Ata
    endpoint_itens = f"{API_BASE_URL}/modulo-arp/2.1_consultarARPItem_Id"
    dados_finais = []
    
    print(f"\n--- Iniciando extração de itens de {len(atas)} atas ---")

    for i, ata in enumerate(atas, 1):
        print(f"Processando itens da Ata {i}/{len(atas)}: {ata['numero_ata']} (PNCP: {ata['pncp_ata']})")
        
        try:
            params = {"numeroControlePncpAta": ata['pncp_ata']}
            response = requests.get(endpoint_itens, params=params, timeout=30)
            
            if response.status_code != 200: 
                continue
                
            dados = response.json()
            registros = dados.get("resultado", [])
            
            for item in registros:
                # Tratamento de campos que podem vir nulos
                cnpj = item.get("niFornecedor", "S_N")
                item_num = item.get("numeroItem", "0")
                
                # Gerar o ID Único para o banco transacional (Stage CDC)
                id_registro = f"{ata['numero_ata']}_{cnpj}_{item_num}".strip().replace(" ", "")
                
                # Quantidade: a API retorna vários tipos, vamos priorizar a do Vencedor
                qtd = item.get("quantidadeHomologadaVencedor") or item.get("quantidadeHomologadaItem") or 0.0
                
                # Monta a tupla EXATAMENTE na ordem que o banco de dados espera
                dados_finais.append((
                    id_registro,
                    ata['numero_ata'],
                    ata['orgao_gerenciador'],
                    ata['objeto'],
                    cnpj,
                    item.get("nomeRazaoSocialFornecedor", "Fornecedor Não Informado"),
                    int(item_num) if str(item_num).isdigit() else 0,
                    item.get("descricaoItem", "Sem descrição"),
                    float(qtd),
                    float(item.get("valorUnitario") or 0.0),
                    float(item.get("valorTotal") or 0.0),
                    datetime.now() # atualizado_em
                ))
                
        except Exception as e:
            print(f"Erro ao extrair itens da ata {ata['pncp_ata']}: {e}")
            
        time.sleep(0.5) # Importante: Rate limit para não sobrecarregar o servidor
        
    return dados_finais

#if __name__ == "__main__":
    # Teste rápido executando o arquivo diretamente
   # dados = extrair_dados_api("2024-01-01", "2024-01-01")
   # if dados:
   #     print(f"\nSucesso! {len(dados)} itens mapeados e prontos para o Banco de Dados.")