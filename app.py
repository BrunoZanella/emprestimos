import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
import sqlite3
import threading
import time
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

# Email Configuration
EMAIL_HOST = st.secrets["EMAIL_HOST"]
EMAIL_PORT = int(st.secrets["EMAIL_PORT"])
EMAIL_HOST_USER = st.secrets["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = st.secrets["EMAIL_HOST_PASSWORD"]
DEFAULT_FROM_EMAIL = st.secrets["DEFAULT_FROM_EMAIL"]


# Database setup
def init_db():
    conn = sqlite3.connect('loans.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS loans
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         client_name TEXT NOT NULL,
         amount REAL NOT NULL,
         interest_rate REAL NOT NULL,
         installments INTEGER NOT NULL,
         start_date TEXT NOT NULL)
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         loan_id INTEGER NOT NULL,
         installment_number INTEGER NOT NULL,
         amount REAL NOT NULL,
         due_date TEXT NOT NULL,
         paid INTEGER DEFAULT 0,
         FOREIGN KEY (loan_id) REFERENCES loans (id))
    ''')
    conn.commit()
    conn.close()

def create_pdf(loan_data, payments_data):
    # Nome do arquivo PDF
#    filename = f"emprestimo_{loan_data['id']}_{loan_data['client_name']}.pdf"
    filename = f"loan_{loan_data['id']}_{loan_data['client_name']}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    title_style.fontSize = 18
    title_style.leading = 22
    title_style.textColor = colors.HexColor('#2F4F4F')
    
    normal_style = styles['Normal']
    normal_style.fontSize = 12
    normal_style.leading = 16
    normal_style.spaceAfter = 12
    
    # Cabeçalho
    elements.append(Paragraph(f"Detalhes do Empréstimo - {loan_data['client_name']}", title_style))
    elements.append(Spacer(1, 12))  # Espaçamento
    
    # Informações do empréstimo
    elements.append(Paragraph(f"Valor do Empréstimo: R${loan_data['amount']:.2f}", normal_style))
    elements.append(Paragraph(f"Taxa de Juros: {loan_data['interest_rate']}%", normal_style))
    elements.append(Paragraph(f"Número de Parcelas: {loan_data['installments']}", normal_style))
    elements.append(Spacer(1, 20))  # Espaçamento maior antes da tabela
    
    # Dados da tabela
    data = [['Parcela', 'Data de Vencimento', 'Valor', 'Status']]
    for payment in payments_data:
        data.append([
            payment['installment_number'],
            payment['due_date'],
            f"R${payment['amount']:.2f}",
            'Pago' if payment['paid'] else 'Pendente'
        ])
    
    # Configuração da tabela
    table = Table(data, colWidths=[80, 120, 100, 100])
    table.setStyle(TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        
        # Corpo
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Linhas alternadas
        ('BACKGROUND', (0, 2), (-1, -1), colors.HexColor('#ffffff')),
        ('BACKGROUND', (0, 3), (-1, -1), colors.HexColor('#f2f2f2')),
        
        # Grade
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))  # Espaçamento após a tabela
    
    # Nota final
    elements.append(Paragraph("Por favor, entre em contato conosco caso tenha dúvidas sobre seu empréstimo.", normal_style))
    
    # Construção do PDF
    doc.build(elements)
    return filename

def send_email(to_email, subject, body, attachment_path=None):
    msg = MIMEMultipart()
    msg['From'] = DEFAULT_FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            pdf = MIMEApplication(f.read(), _subtype='pdf')
            pdf.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
            msg.attach(pdf)

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.send_message(msg)


def check_due_payments():
    while True:
        conn = sqlite3.connect('loans.db')
        c = conn.cursor()
        today = datetime.now().date()

        c.execute('''
            SELECT p.*, l.client_name, l.installments
            FROM payments p
            JOIN loans l ON p.loan_id = l.id
            WHERE p.paid = 0 AND date(p.due_date) = date(?)
        ''', (today.strftime('%Y-%m-%d'),))

        payments = c.fetchall()
        for payment in payments:
            subject = f"Lembrete de Pagamento - Parcela {payment[2]}"
            body = f"""
            <html>
            <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                }}
                h2 {{
                    color: #4CAF50;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                p {{
                    margin: 10px 0;
                    font-size: 16px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                table th, table td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: center;
                }}
                table th {{
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                }}
                table tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
                .footer {{
                    margin-top: 30px;
                    text-align: center;
                    font-size: 14px;
                    color: #666;
                }}
            </style>
            </head>
            <body>
            <div class="container">
                <h2>Lembrete de Pagamento</h2>
                <p>Prezado(a) {payment[6]},</p>
                <p>Este é um lembrete de que o pagamento da sua parcela do empréstimo vence hoje. Seguem os detalhes:</p>
                <table>
                    <tr>
                        <th>Parcela</th>
                        <th>Data de Vencimento</th>
                        <th>Valor</th>
                        <th>Status</th>
                    </tr>
                    <tr>
                        <td>{payment[2]}</td>
                        <td>{payment[4]}</td>
                        <td>R${payment[3]:.2f}</td>
                        <td>Pendente</td>
                    </tr>
                </table>
                <p style="margin-top: 20px;">
                    Por favor, certifique-se de realizar o pagamento até o final do dia para evitar encargos adicionais.
                </p>
                <p>
                    Em caso de dúvidas, entre em contato com a nossa equipe de suporte.
                </p>
                <div class="footer">
                    <p>Este é um email automático. Não responda a este endereço.</p>
                </div>
            </div>
            </body>
            </html>
            """
            send_email(EMAIL_HOST_USER, subject, body)

        conn.close()
        time.sleep(86400)  # Verifica a cada 24 horas


def main():
    st.set_page_config(page_title="Empréstimos Zanella's", layout="wide")
    st.title("Empréstimos Zanella's")
    
    init_db()
    
    # Start payment checker in a separate thread
    if 'payment_checker' not in st.session_state:
        payment_checker = threading.Thread(target=check_due_payments)
        payment_checker.daemon = True
        payment_checker.start()
        st.session_state.payment_checker = True
    
    # Sidebar navigation
    page = st.sidebar.selectbox("Navegação", ["Lista de Empréstimos", "Novo Empréstimo"])
    
    if page == "Lista de Empréstimos":
        show_loans_list()
    else:
        show_new_loan_form()

def delete_loan(loan_id):
    conn = sqlite3.connect('loans.db')
    c = conn.cursor()
    
    # Remover pagamentos associados ao empréstimo
    c.execute("DELETE FROM payments WHERE loan_id = ?", (loan_id,))
    
    # Remover o empréstimo
    c.execute("DELETE FROM loans WHERE id = ?", (loan_id,))
    
    conn.commit()
    conn.close()


def show_loans_list():
    conn = sqlite3.connect('loans.db')
    loans_df = pd.read_sql_query("SELECT * FROM loans", conn)
    
    if not loans_df.empty:
        st.subheader("Empréstimos Ativos")
        
        for _, loan in loans_df.iterrows():
            with st.expander(f"Cliente: {loan['client_name']} - R$ {loan['amount']:.2f}"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Valor", f"R$ {loan['amount']:.2f}")
                col2.metric("Taxa de Juros", f"{loan['interest_rate']}%")
                col3.metric("Parcelas", loan['installments'])
                col4.metric("Data Início", loan['start_date'][:10])
                
                payments_df = pd.read_sql_query(
                    "SELECT * FROM payments WHERE loan_id = ? ORDER BY installment_number",
                    conn, params=(loan['id'],)
                )
                
                st.write("### Parcelas")
                for _, payment in payments_df.iterrows():
                    cols = st.columns([1, 2, 2, 2, 3])
                    cols[0].write(f"#{payment['installment_number']}")
                    cols[1].write(payment['due_date'][:10])
                    cols[2].write(f"R$ {payment['amount']:.2f}")
                    status = "🟢 Pago" if payment['paid'] else "🔴 Pendente"
                    cols[3].write(status)
                    if cols[4].button(
                        "Marcar como Não Pago" if payment['paid'] else "Marcar como Pago",
                        key=f"btn_{payment['id']}"
                    ):
                        c = conn.cursor()
                        c.execute(
                            "UPDATE payments SET paid = ? WHERE id = ?",
                            (1 - payment['paid'], payment['id'])
                        )
                        conn.commit()
                        st.rerun()

                # Botão para apagar o empréstimo
                if st.button(f"Excluir Empréstimo - {loan['client_name']}", key=f"delete_{loan['id']}"):
                    delete_loan(loan['id'])
                    st.success(f"Empréstimo de {loan['client_name']} excluído com sucesso!")
                    st.rerun()
                        
    else:
        st.info("Nenhum empréstimo cadastrado.")
    
    conn.close()

def show_new_loan_form():
    st.subheader("Novo Empréstimo")
    
    with st.form("new_loan"):
        client_name = st.text_input("Nome do Cliente")
        amount = st.number_input("Valor do Empréstimo", min_value=0.0, step=100.0)
        interest_rate = st.number_input("Taxa de Juros (%)", min_value=0.0, step=0.1)
        installments = st.number_input("Número de Parcelas", min_value=1, step=1)
        
        if st.form_submit_button("Criar Empréstimo"):
            if client_name and amount > 0 and installments > 0:
                conn = sqlite3.connect('loans.db')
                c = conn.cursor()
                
                # Create loan
                c.execute('''
                    INSERT INTO loans (client_name, amount, interest_rate, installments, start_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (client_name, amount, interest_rate, installments, datetime.now().strftime('%Y-%m-%d')))
                
                loan_id = c.lastrowid
                
                # Create payments
                monthly_amount = (amount * (1 + interest_rate/100)) / installments
                start_date = datetime.now()
                
                for i in range(installments):
                    due_date = start_date + timedelta(days=(i+1)*30)
                    c.execute('''
                        INSERT INTO payments (loan_id, installment_number, amount, due_date)
                        VALUES (?, ?, ?, ?)
                    ''', (loan_id, i+1, monthly_amount, due_date.strftime('%Y-%m-%d')))
                
                conn.commit()
                
                # Get loan and payments data for PDF
                c.execute("SELECT * FROM loans WHERE id = ?", (loan_id,))
                loan_data = dict(zip([col[0] for col in c.description], c.fetchone()))
                
                c.execute("SELECT * FROM payments WHERE loan_id = ?", (loan_id,))
                payments_data = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
                
                # Generate PDF and send email
                pdf_path = create_pdf(loan_data, payments_data)
                
                subject = f"Novo acordo de empréstimo - {client_name}"
                body = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            color: #333;
                            line-height: 1.6;
                        }}
                        h2 {{
                            color: #4CAF50;
                        }}
                        p {{
                            margin: 10px 0;
                        }}
                        .highlight {{
                            background-color: #f9f9f9;
                            padding: 10px;
                            border-left: 5px solid #4CAF50;
                            margin: 20px 0;
                        }}
                        .footer {{
                            margin-top: 30px;
                            font-size: 12px;
                            color: #777;
                            border-top: 1px solid #ddd;
                            padding-top: 10px;
                        }}
                    </style>
                </head>
                <body>
                    <h2>Confirmação de Novo Empréstimo</h2>
                    <p>Olá, <strong>{client_name}</strong>,</p>
                    <p>Estamos felizes em confirmar os detalhes do seu novo empréstimo. Por favor, revise as informações abaixo:</p>

                    <div class="highlight">
                        <p><strong>Valor do Empréstimo:</strong> R${amount:.2f}</p>
                        <p><strong>Taxa de Juros:</strong> {interest_rate}% ao ano</p>
                        <p><strong>Número de Parcelas:</strong> {installments}</p>
                        <p><strong>Valor da Parcela Mensal (aproximado):</strong> R${monthly_amount:.2f}</p>
                        <p><strong>Data de Início:</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
                    </div>

                    <p>Anexamos a este e-mail uma cópia do contrato do empréstimo em formato PDF para sua conveniência.</p>
                    <p>Se você tiver alguma dúvida ou precisar de assistência, não hesite em entrar em contato conosco.</p>

                    <div class="footer">
                        <p>Atenciosamente,</p>
                        <p><strong>Equipe Financeira</strong></p>
                        <p>E-mail: {EMAIL_HOST_USER}</p>
                        <p>Telefone: (62)9 8295-7089</p>
                    </div>
                </body>
                </html>
                """

                
                send_email(EMAIL_HOST_USER, subject, body, pdf_path)
                os.remove(pdf_path)  # Clean up PDF file
                
                conn.close()
                st.success("Empréstimo criado com sucesso!")
                st.rerun()

            else:
                st.error("Por favor, preencha todos os campos corretamente.")

if __name__ == '__main__':
    main()