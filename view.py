import sqlite3

def view_db():
    # Conectar ao banco de dados
    conn = sqlite3.connect('wifi_scans.db')
    c = conn.cursor()

    # Executar o comando para listar as tabelas
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    print("Tabelas no banco de dados:")
    for table in tables:
        print(table[0])

    # Executar o comando para visualizar os dados na tabela 'scans'
    c.execute("SELECT * FROM scans;")
    rows = c.fetchall()
    print("\nDados na tabela '':")
    for row in rows:
        print(row)

    c.execute("SELECT * FROM open_scans;")
    rows = c.fetchall()
    print("\nDados na tabela 'open_scans':")
    for row in rows:
        print(row)
        
    c.execute("SELECT * FROM open_bssids;")
    rows = c.fetchall()
    print("\nDados na tabela 'open_bssids':")
    for row in rows:
        print(row)
    
    # Fechar a conexão
    conn.close()

# Chamar a função para visualizar o banco de dados
view_db()
