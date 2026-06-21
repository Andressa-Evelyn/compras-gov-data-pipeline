package main

import "hash/fnv"

const (
	KafkaBroker      = "localhost:9092"
	KafkaTopic       = "cdc.stage.stg_atas_registro_precos"
	KafkaGroupID     = "go-worker-group"
	ClickHouseDSN    = "clickhouse://127.0.0.1:9000?database=analytics"
)

// Estrutura do payload enviado pelo Debezium (simplificada para captura do 'after')
type DebeziumPayload struct {
	Payload struct {
		After struct {
			IDRegistro           string  `json:"id_registro"`
			NumeroAta            string  `json:"numero_ata"`
			OrgaoGerenciador     string  `json:"orgao_gerenciador"`
			Objeto               string  `json:"objeto"`
			CNPJFornecedor       string  `json:"cnpj_fornecedor"`
			NomeFornecedor       string  `json:"nome_fornecedor"`
			ItemNumero           int32   `json:"item_numero"`
			DescricaoItem        string  `json:"descricao_item"`
			QuantidadeHomologada interface{} `json:"quantidade_homologada"` 
			ValorUnitario        interface{} `json:"valor_unitario"`        
			ValorTotal           interface{} `json:"valor_total"`           
		} `json:"after"`
		Op string `json:"op"` // c = create, u = update
	} `json:"payload"`
}

// Auxiliar para gerar ID numérico único do Órgão no ClickHouse
func GerarHash(s string) uint64 {
	h := fnv.New64a()
	h.Write([]byte(s))
	return h.Sum64()
}