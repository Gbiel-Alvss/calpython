from datetime import datetime, timedelta

def pausas_devidas(minutos_trabalhados):
    return (minutos_trabalhados // 90) * 10


def contar_dias(inicio, fim):
    seg_sex = 0
    sabados = 0

    d = inicio
    while d <= fim:
        if d.weekday() <= 4:
            seg_sex += 1
        elif d.weekday() == 5:
            sabados += 1
        d += timedelta(days=1)

    return seg_sex, sabados


def calcular():
    print("\n=== CÁLCULO DE PAUSAS – TEMA 245 TST ===\n")

    # INPUTS
    data_inicio_str = input("Digite a data inicial (dd/mm/aaaa): ")
    data_fim_str = input("Digite a data final (dd/mm/aaaa): ")
    salario = float(input("Digite o salário (ex: 1555): ").replace(",", "."))
    divisor = float(input("Digite o divisor mensal (ex: 244): ").replace(",", "."))
    adicional_percentual = float(input("Digite o adicional em % (ex: 50): ").replace(",", "."))

    adicional = adicional_percentual / 100

    # CONVERTE PARA DATA
    inicio = datetime.strptime(data_inicio_str, "%d/%m/%Y").date()
    fim = datetime.strptime(data_fim_str, "%d/%m/%Y").date()

    minutos_seg_sex = 8 * 60
    minutos_sabado = 4 * 60

    seg_sex, sabados = contar_dias(inicio, fim)

    pausa_dia_util = pausas_devidas(minutos_seg_sex)
    pausa_sab = pausas_devidas(minutos_sabado)

    minutos_total = (seg_sex * pausa_dia_util) + (sabados * pausa_sab)
    horas_total = minutos_total / 60

    valor_hora = salario / divisor
    valor_total = horas_total * valor_hora * (1 + adicional)

    print("\n===== RESULTADO =====")
    print("Período:", inicio.strftime("%d/%m/%Y"), "até", fim.strftime("%d/%m/%Y"))
    print("Dias seg-sex:", seg_sex)
    print("Sábados:", sabados)
    print("Minutos suprimidos:", minutos_total)
    print("Horas suprimidas:", round(horas_total, 2))
    print("Valor da hora: R$", round(valor_hora, 2))
    print("Valor total devido: R$", round(valor_total, 2))


if __name__ == "__main__":
    calcular()
