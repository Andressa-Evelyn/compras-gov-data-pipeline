from extractor import extrair_dados_api
from database import inicializar_banco, carregar_dados_postgresql

def main():
    print("--- INICIANDO PIPELINE DE EXTRAÇÃO (ARP) ---")
    
    # 1. Preparar o banco (cria tabela e configura CDC se não existir)
    inicializar_banco()
    
    # 2. Extração via API
    dados = extrair_dados_api("2024-01-01", "2024-01-08")
    
    # 3. Carga no Stage (Transacional)
    if dados:
        print(f"\nSucesso! {len(dados)} itens mapeados. Enviando para o banco...")
        carregar_dados_postgresql(dados)
    else:
        print("\nNenhum dado foi coletado. Verifique o período ou a API.")

    print("--- PIPELINE FINALIZADO ---")

if __name__ == "__main__":
    main()