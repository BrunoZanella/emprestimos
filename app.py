

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
import sqlite3
import threading
import time



# Email Configuration
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'zanellabruno7@gmail.com'
EMAIL_HOST_PASSWORD = 'ygwk qrzo rcvg iztv'
DEFAULT_FROM_EMAIL = 'zanellabruno7@gmail.com'

def calculate_compound_interest(principal, rate, time, installments):
    """
    Calcula juros compostos mensais
    principal: valor inicial
    rate: taxa de juros anual em porcentagem
    time: tempo em meses
    installments: número de parcelas
    """
    # Garantir que installments não seja zero
    if installments == 0:
        installments = 1  # Define um valor padrão para evitar divisão por zero

    # Converter taxa anual para mensal
    monthly_rate = (rate / 100) / 12

    # Calcular montante final com juros compostos mensais
    amount = principal * (1 + monthly_rate) ** time

    # Calcular valor da parcela
    if monthly_rate == 0:  # Sem juros
        monthly_payment = principal / installments
    else:  # Com juros
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** installments) / (
            (1 + monthly_rate) ** installments - 1
        )

    return {
        'total_amount': amount,
        'monthly_payment': monthly_payment,
        'total_interest': amount - principal
    }




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
        time.sleep(86400)  # Check every 24 hours

def main():
    st.set_page_config(page_title="Zanella's Empréstimos", layout="wide")

    # Remover espaço em branco no topo da página e ajustar o título
    st.markdown("""
        <style>
            .css-18e3th9 {
                padding-top: 0 !important;
            }
            .css-1d391kg {
                padding-top: 0 !important;
                margin-top: 0 !important;
            }
            h1 {
                margin-top: 5px !important;
                margin-bottom: 20px;
                text-align: left;
            }
            
            /* Ajustar a distância da borda superior */
            .main-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;  /* Certifica que os itens começam do topo */
                background-color: #0E1117;
                color: #FAFAFA;
                padding-top: 0px;  /* Ajuste a distância da borda superior */
            }
            
            .button-container {
                margin-left: 10px; /* Ajuste o espaçamento entre título e botão, se necessário */
            }
            /* Movendo o título h2 15px mais para cima */
            .stMarkdown h2 {
                margin-top: -120px;  /* Subir o título */
                color: #FAFAFA;
                text-align: center;
            }
            /* Movendo o título h3 15px mais para cima */
            .stMarkdown h3 {
                margin-top: -50px;  /* Subir o título */
                color: #FAFAFA;
                text-align: left; /* Alinhar o título à esquerda */
            }
            /* Movendo o título h3 15px mais para cima */
            .stMarkdown h4 {
                margin-top:-10px;  /* Subir o título */
                color: #FAFAFA;
                text-align: left; /* Alinhar o título à esquerda */
            }            

            /* Background da sidebar */
            .css-1d391kg {
                background-color: #262730 !important;
            }

            /* Esconder cabeçalho padrão do Streamlit */
            header, .stApp > header {
                display: none;
            }

            /* Esconder rodapé padrão do Streamlit */
            footer, .stApp > footer {
                display: none;
            }

        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown("<h2>Zanella's Empréstimos</h2>", unsafe_allow_html=True)
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
                # Edição do empréstimo
                edit_col1, edit_col2, edit_col3 = st.columns(3)
                new_amount = edit_col1.number_input(
                    "Novo Valor",
                    value=float(loan['amount']),
                    key=f"amount_{loan['id']}"
                )
                new_rate = edit_col2.number_input(
                    "Nova Taxa",
                    value=float(loan['interest_rate']),
                    key=f"rate_{loan['id']}"
                )
                if edit_col3.button("Atualizar Empréstimo", key=f"update_{loan['id']}"):
                    c = conn.cursor()
                    c.execute(
                        "UPDATE loans SET amount = ?, interest_rate = ? WHERE id = ?",
                        (new_amount, new_rate, loan['id'])
                    )
                    
                    # Recalcular parcelas
                    calc = calculate_compound_interest(
                        new_amount,
                        new_rate,
                        loan['installments'],
                        loan['installments']
                    )
                    
                    c.execute(
                        "UPDATE payments SET amount = ? WHERE loan_id = ? AND paid = 0",
                        (calc['monthly_payment'], loan['id'])
                    )
                    
                    conn.commit()
                    st.success("Empréstimo atualizado com sucesso!")
                    st.rerun()
                
                # Métricas do empréstimo
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Valor Principal", f"R$ {loan['amount']:.2f}")
                col2.metric("Taxa de Juros", f"{loan['interest_rate']}%")
                col3.metric("Parcelas", loan['installments'])
                col4.metric("Data Início", loan['start_date'][:10])
                
                payments_df = pd.read_sql_query(
                    "SELECT * FROM payments WHERE loan_id = ? ORDER BY installment_number",
                    conn, params=(loan['id'],)
                )
                
                # Cálculo do total pago e restante
                total_paid = payments_df[payments_df['paid'] == 1]['amount'].sum()
                total_remaining = payments_df[payments_df['paid'] == 0]['amount'].sum()
                
                col1, col2 = st.columns(2)
                col1.metric("Total Pago", f"R$ {total_paid:.2f}")
                col2.metric("Total Restante", f"R$ {total_remaining:.2f}")
                
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



# Função principal do formulário
def show_new_loan_form():

#    st.subheader("Novo Empréstimo")
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown("<h3>Novo Empréstimo</h3>", unsafe_allow_html=True)


    # Botão para criar empréstimo e mensagens de status
    with st.columns([5, 1])[1]:  # Coluna 1: 75% (formulário), Coluna 2: 25% (botão e mensagens)

        # Botão para criar o empréstimo
        if st.button("Criar Empréstimo"):
            if client_name and amount > 0 and installments > 0:
                conn = sqlite3.connect('loans.db')
                c = conn.cursor()
                
                # Criar empréstimo
                c.execute('''
                    INSERT INTO loans (client_name, amount, interest_rate, installments, start_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (client_name, amount, interest_rate, installments, datetime.now().strftime('%Y-%m-%d')))
                
                loan_id = c.lastrowid
                
                # Criar pagamentos
                start_date = datetime.now()
                for i in range(installments):
                    due_date = start_date + timedelta(days=(i + 1) * 30)
                    c.execute('''
                        INSERT INTO payments (loan_id, installment_number, amount, due_date)
                        VALUES (?, ?, ?, ?)
                    ''', (loan_id, i + 1, calc['monthly_payment'], due_date.strftime('%Y-%m-%d')))
                
                conn.commit()
                conn.close()
                
                st.success(f"Empréstimo de {client_name} criado com sucesso!")
            else:
                st.error("Por favor, preencha todos os campos corretamente.")


    if 'form_data' not in st.session_state:
        st.session_state.form_data = {
            'amount': 0.0,
            'rate': 0.0,
            'installments': 1
        }

#    st.markdown("<br><br>", unsafe_allow_html=True)  # Adiciona dois saltos de linha para afastar as colunas do conteúdo acima

    col1, col2 = st.columns([2, 1])

    # 1/4 da página: Campos de entrada
    with col1:
        st.write("### Dados do Empréstimo")
        client_name = st.text_input("Nome do Cliente", key="client_name")
        amount = st.number_input(
            "Valor do Empréstimo",
            min_value=0.0,
            step=100.0,
            key='amount'
        )
        interest_rate = st.number_input(
            "Taxa de Juros Anual (%)",
            min_value=0.0,
            step=0.1,
            key='rate'
        )
        installments = st.number_input(
            "Número de Parcelas",
            min_value=1,
            step=1,
            key='installments'
        )

    # 2/4 da página: Tabela de parcelas
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)  # Adiciona dois saltos de linha para afastar as colunas do conteúdo acima
        st.write("### Previsão das Parcelas")
        
        if amount > 0 and installments >= 1 and interest_rate > 0:
            calc = calculate_compound_interest(amount, interest_rate, installments, installments)
            
            installment_data = []
            start_date = datetime.now()
            for i in range(installments):
                due_date = start_date + timedelta(days=(i + 1) * 30)
                installment_data.append({
                    'Parcela': i + 1,
                    'Vencimento': due_date.strftime('%d/%m/%Y'),
                    'Valor': f"R$ {calc['monthly_payment']:.2f}"
                })
            
            df = pd.DataFrame(installment_data)
            st.dataframe(df, height=250)

    st.markdown("<h4>Resumo do Empréstimo</h4>", unsafe_allow_html=True)

    # Metade inferior: Resultados em tempo real
#    st.write("### Resumo do Empréstimo")
    col3, col4, col5, col6 = st.columns(4)
    if amount > 0 and installments > 0 and interest_rate > 0:
        calc = calculate_compound_interest(amount, interest_rate, installments, installments)
        
        col3.metric("Valor Principal", f"R$ {amount:,.2f}")
        col4.metric("Valor Total com Juros", f"R$ {calc['total_amount']:,.2f}")
        col5.metric("Valor dos Juros", f"R$ {calc['total_interest']:,.2f}")
        col6.metric("Valor da Parcela", f"R$ {calc['monthly_payment']:,.2f}")
    
    

if __name__ == '__main__':
    main()
    
    