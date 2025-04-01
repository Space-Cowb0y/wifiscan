import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from fpdf import FPDF


def init_db():
    conn = sqlite3.connect('redes_wifi.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS redes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            ssid TEXT,
            bssid TEXT,
            auth TEXT,
            signal INTEGER,
            FOREIGN KEY(scan_id) REFERENCES scans(id)
        )
    ''')

    conn.commit()
    conn.close()


def salvar_scan(area, redes):
    conn = sqlite3.connect('redes_wifi.db')
    cursor = conn.cursor()

    cursor.execute('INSERT INTO scans (area) VALUES (?)', (area,))
    scan_id = cursor.lastrowid

    for rede in redes:
        cursor.execute('''
            INSERT INTO redes (scan_id, ssid, bssid, auth, signal)
            VALUES (?, ?, ?, ?, ?)
        ''', (scan_id, rede['ssid'], rede['bssid'], rede['auth'], rede['signal']))

    conn.commit()
    conn.close()


def gerar_relatorio_pdf(nome_arquivo='Relatorio_Redes.pdf'):
    conn = sqlite3.connect('redes_wifi.db')
    cursor = conn.cursor()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Relatório de Varredura Wi-Fi', ln=1)

    cursor.execute('SELECT id, area, data FROM scans ORDER BY data DESC')
    scans = cursor.fetchall()

    pdf.set_font('Arial', '', 12)
    for scan_id, area, data in scans:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f'Área: {area} - Data: {data}', ln=1)

        cursor.execute('''
            SELECT ssid, bssid, auth, signal FROM redes WHERE scan_id = ?
        ''', (scan_id,))
        redes = cursor.fetchall()

        pdf.set_font('Arial', '', 11)
        if not redes:
            pdf.cell(0, 10, 'Nenhuma rede encontrada.', ln=1)
        else:
            for ssid, bssid, auth, signal in redes:
                status = 'ABERTA' if auth.lower() == 'open' else auth
                pdf.cell(0, 10, f'{ssid} ({bssid}) - {status} - Sinal: {signal}%', ln=1)

    conn.close()
    pdf.output(nome_arquivo)


def parse_netsh_output(raw_output):
    redes = []
    ssid, auth, signal, bssid = '', '', 0, ''
    lines = raw_output.splitlines()
    for i, line in enumerate(lines):
        if "SSID" in line and 'BSSID' not in line:
            ssid = line.split(':')[1].strip()
        elif "Authentication" in line:
            auth = line.split(':')[1].strip()
        elif "Signal" in line:
            try:
                signal = int(line.split(':')[1].replace('%', '').strip())
            except:
                signal = 0
        elif "BSSID" in line:
            bssid = line.split(':')[1].strip().lower()
            redes.append({"ssid": ssid, "auth": auth, "bssid": bssid, "signal": signal})
    return redes


def escanear_redes():
    area = input("Digite o número da área dessa varredura: ")
    print("Escaneando redes... Aguarde...")

    subprocess.run(['netsh', 'wlan', 'scan'])
    time.sleep(5)
    resultado = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                               capture_output=True, text=True)

    redes = parse_netsh_output(resultado.stdout)
    salvar_scan(area, redes)
    gerar_relatorio_pdf()
    print(f"Varredura salva e relatório gerado: Relatorio_Redes.pdf")


if __name__ == '__main__':
    init_db()
    escanear_redes()
