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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import sqlite3
import threading
import time

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
    filename = f"loan_{loan_data['id']}_{loan_data['client_name']}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Loan Details for {loan_data['client_name']}", styles['Title']))
    elements.append(Paragraph(f"Loan Amount: R${loan_data['amount']:.2f}", styles['Normal']))
    elements.append(Paragraph(f"Interest Rate: {loan_data['interest_rate']}%", styles['Normal']))
    elements.append(Paragraph(f"Number of Installments: {loan_data['installments']}", styles['Normal']))
    
    # Create table data
    data = [['Installment', 'Due Date', 'Amount', 'Status']]
    for payment in payments_data:
        data.append([
            payment['installment_number'],
            payment['due_date'],
            f"R${payment['amount']:.2f}",
            'Paid' if payment['paid'] else 'Pending'
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
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
            subject = f"Payment Reminder - Installment {payment[2]}"
            body = f"""
            <h2>Payment Reminder</h2>
            <p>Dear {payment[6]},</p>
            <p>This is a reminder that your loan payment is due today.</p>
            <p>Amount: R${payment[3]:.2f}</p>
            <p>Installment: {payment[2]} of {payment[7]}</p>
            """
            send_email(EMAIL_HOST_USER, subject, body)
        
        conn.close()
        time.sleep(86400)  # Check every 24 hours

def main():
    st.set_page_config(page_title="Sistema de Empréstimos", layout="wide")
    st.title("Sistema de Empréstimos")
    
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
#                        st.experimental_rerun()
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
                
                subject = f"New Loan Agreement - {client_name}"
                body = f"""
                <h2>Loan Agreement</h2>
                <p>Client: {client_name}</p>
                <p>Amount: R${amount:.2f}</p>
                <p>Interest Rate: {interest_rate}%</p>
                <p>Number of Installments: {installments}</p>
                <p>Monthly Payment: R${monthly_amount:.2f}</p>
                """
                
                send_email(EMAIL_HOST_USER, subject, body, pdf_path)
                os.remove(pdf_path)  # Clean up PDF file
                
                conn.close()
                st.success("Empréstimo criado com sucesso!")
#                st.experimental_rerun()
                st.rerun()

            else:
                st.error("Por favor, preencha todos os campos corretamente.")

if __name__ == '__main__':
    main()