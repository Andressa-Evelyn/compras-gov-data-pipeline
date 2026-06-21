package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"
	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/segmentio/kafka-go"
)

func parseFloatSeguro(v interface{}) float64 {
	if v == nil {
		return 0.0
	}
	switch val := v.(type) {
	case float64:
		return val
	case string:
		f, _ := strconv.ParseFloat(val, 64)
		return f
	default:
		return 0.0
	}
}

func main() {
	log.Println("Iniciando Worker em Go...")

	chConn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{"127.0.0.1:9000"},
		Auth: clickhouse.Auth{
			Database: "analytics",
		},
	})
	if err != nil {
		log.Fatalf("Erro ao conectar no ClickHouse: %v", err)
	}
	defer chConn.Close()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{KafkaBroker},
		Topic:    KafkaTopic,
		GroupID:  KafkaGroupID,
		MinBytes: 10e3, // 10KB
		MaxBytes: 10e6, // 10MB
	})
	defer reader.Close()

	log.Println("Worker conectado com sucesso. Aguardando mensagens do CDC...")

	ctx := context.Background()

	for {
		msg, err := reader.ReadMessage(ctx)
		if err != nil {
			log.Printf("Erro ao ler mensagem: %v", err)
			continue
		}

		var ev DebeziumPayload
		if err := json.Unmarshal(msg.Value, &ev); err != nil {
			log.Printf("ERRO DE PARSE: %v\n", err)
			//log.Printf("MENSAGEM CRUA: %s\n", string(msg.Value))
			continue
		}

		//log.Printf("MENSAGEM RECEBIDA! Operação: %s", ev.Payload.Op)

		// Valida se o evento traz uma alteração/inserção válida de dados
		if ev.Payload.Op == "c" || ev.Payload.Op == "u" {
			data := ev.Payload.After

			// --- HIGIENIZAÇÃO DE DADOS (Regra de Negócio) ---
			nomeFornecedorClean := strings.ToUpper(strings.TrimSpace(data.NomeFornecedor))
			orgaoClean := strings.TrimSpace(data.OrgaoGerenciador)
			objetoClean := strings.TrimSpace(data.Objeto)
			idOrgao := GerarHash(orgaoClean)
			now := time.Now()

			if nomeFornecedorClean == "" {
				nomeFornecedorClean = "NÃO INFORMADO"
			}

			// --- PERSISTÊNCIA NAS DIMENSÕES DO CLICKHOUSE ---
			
			// 1. Inserindo na dim_fornecedores
			err = chConn.Exec(ctx, "INSERT INTO dim_fornecedores VALUES (?, ?, ?)",
				data.CNPJFornecedor, nomeFornecedorClean, now)
			if err != nil {
				log.Printf("Erro dim_fornecedores: %v", err)
			}

			// 2. Inserindo na dim_orgaos
			err = chConn.Exec(ctx, "INSERT INTO dim_orgaos VALUES (?, ?, ?)",
				idOrgao, orgaoClean, now)
			if err != nil {
				log.Printf("Erro dim_orgaos: %v", err)
			}

			qtd := parseFloatSeguro(data.QuantidadeHomologada)
			vUnit := parseFloatSeguro(data.ValorUnitario)
			vTotal := parseFloatSeguro(data.ValorTotal)

			// 3. Inserindo na dim_itens (Tabela Fato)
			err = chConn.Exec(ctx, `INSERT INTO dim_itens VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
				data.IDRegistro, data.NumeroAta, data.CNPJFornecedor, idOrgao,
				objetoClean, data.ItemNumero, data.DescricaoItem,
				qtd, vUnit, vTotal, now)
			
			if err != nil {
				log.Printf("Erro dim_itens: %v", err)
			} else {
				fmt.Printf(" [CDC] Processado com Sucesso: Ata %s -> Item %d replicado para o ClickHouse\n", data.NumeroAta, data.ItemNumero)
			}
		}
	}
}