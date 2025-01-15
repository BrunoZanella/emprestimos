def calcular_emprestimo(valor, parcelas, taxa_juros_mensal):
    """
    Calcula o valor da parcela, total a ser pago e os juros de um empréstimo
    usando o Sistema de Amortização Price (juros compostos).
    
    valor: valor do empréstimo
    parcelas: número de parcelas
    taxa_juros_mensal: taxa de juros mensal (em porcentagem)
    
    Retorna:
    valor_parcela: valor da parcela
    total_pago: total a ser pago
    juros: total de juros pagos
    """
    
    # Converter taxa de juros mensal para decimal
    taxa_juros_mensal /= 100  # Ajuste para transformar em decimal
    
    # Calcular valor da parcela (Sistema Price)
    if taxa_juros_mensal == 0:
        valor_parcela = valor / parcelas  # Sem juros
    else:
        valor_parcela = valor * (taxa_juros_mensal * (1 + taxa_juros_mensal) ** parcelas) / ((1 + taxa_juros_mensal) ** parcelas - 1)
    
    # Calcular total a ser pago
    total_pago = valor_parcela * parcelas
    
    # Calcular total de juros pagos
    juros = total_pago - valor
    
    return valor_parcela, total_pago, juros

# Função para entrada de dados
def entrada_dados():
    valor = float(input("Digite o valor do empréstimo: R$ "))
    parcelas = int(input("Digite o número de parcelas: "))
    taxa_juros_mensal = float(input("Digite a taxa de juros mensal (%): "))
    
    # Chama a função para calcular os valores
    valor_parcela, total_pago, juros = calcular_emprestimo(valor, parcelas, taxa_juros_mensal)
    
    # Exibe os resultados
    print("\nDetalhes do Empréstimo:")
    print(f"Valor do Empréstimo: R$ {valor:.2f}")
    print(f"Número de Parcelas: {parcelas}")
    print(f"Taxa de Juros Mensal: {taxa_juros_mensal * 100:.2f}%")
    print(f"Valor da Parcela: R$ {valor_parcela:.2f}")
    print(f"Valor Total a Pagar: R$ {total_pago:.2f}")
    print(f"Total de Juros: R$ {juros:.2f}")

# Chama a função de entrada
entrada_dados()
