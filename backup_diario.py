"""
Faz uma copia de seguranca do estoque.db, com data no nome do arquivo, na
pasta "backups" ao lado deste script. Mantem so os ultimos 30 dias — apaga
backups mais antigos automaticamente.

Usa a API de backup do sqlite3 (Connection.backup), que gera uma copia
consistente mesmo com o banco em modo WAL e mesmo que o servidor esteja
rodando e recebendo vendas na hora — uma copia simples do arquivo .db
poderia pegar um estado inconsistente ou faltando as ultimas transacoes.

Pra rodar sozinho todo dia, agende no Agendador de Tarefas do Windows
(veja GUIA_IMPLANTACAO.md).
"""

import os
import sqlite3
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "estoque.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DIAS_PARA_MANTER = 30


def main():
    if not os.path.exists(DB_PATH):
        print(f"Banco nao encontrado em {DB_PATH}, nada pra fazer backup.")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    nome_arquivo = f"estoque_{date.today().isoformat()}.db"
    destino = os.path.join(BACKUP_DIR, nome_arquivo)

    origem_conn = sqlite3.connect(DB_PATH)
    destino_conn = sqlite3.connect(destino)
    with destino_conn:
        origem_conn.backup(destino_conn)
    origem_conn.close()
    destino_conn.close()

    print(f"Backup criado: {destino}")

    limite = date.today() - timedelta(days=DIAS_PARA_MANTER)
    removidos = 0
    for arquivo in os.listdir(BACKUP_DIR):
        if not (arquivo.startswith("estoque_") and arquivo.endswith(".db")):
            continue
        data_txt = arquivo[len("estoque_"):-len(".db")]
        try:
            data_arquivo = date.fromisoformat(data_txt)
        except ValueError:
            continue
        if data_arquivo < limite:
            os.remove(os.path.join(BACKUP_DIR, arquivo))
            removidos += 1

    if removidos:
        print(f"Backups com mais de {DIAS_PARA_MANTER} dias removidos: {removidos}")


if __name__ == "__main__":
    main()
