from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta


# ---------------------------
# Regras do cálculo (seu caso)
# ---------------------------
MINUTOS_SEG_SEX = 8 * 60   # 480
MINUTOS_SABADO = 4 * 60    # 240

def pausas_devidas(min_trabalhados: int) -> int:
    """10 minutos a cada 90 minutos trabalhados."""
    return (min_trabalhados // 90) * 10

PAUSA_DIA_UTIL = pausas_devidas(MINUTOS_SEG_SEX)  # 50
PAUSA_SABADO = pausas_devidas(MINUTOS_SABADO)     # 20


def parse_data_br(s: str) -> date:
    """dd/mm/aaaa -> date"""
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()

def fmt_data_br(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def parse_float_br(s: str) -> float:
    """Aceita 1555, 1.555,00, 1555.00 etc."""
    s = s.strip().replace(" ", "")
    if not s:
        raise ValueError("Campo numérico vazio.")
    # Se tiver vírgula, assume vírgula decimal e remove pontos de milhar
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)

def contar_dias(inicio: date, fim: date) -> tuple[int, int]:
    """Conta (seg-sex, sábados) no período inclusive. Domingo ignora."""
    if fim < inicio:
        raise ValueError("A data final não pode ser anterior à data inicial.")
    seg_sex = 0
    sab = 0
    d = inicio
    while d <= fim:
        wd = d.weekday()  # seg=0 ... dom=6
        if 0 <= wd <= 4:
            seg_sex += 1
        elif wd == 5:
            sab += 1
        d += timedelta(days=1)
    return seg_sex, sab


# ---------------------------
# GUI
# ---------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cálculo de Pausas (Tema 245 TST) – 10 min a cada 90 min")
        self.geometry("820x520")
        self.minsize(820, 520)

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except:
            pass

        container = ttk.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        # Título
        title = ttk.Label(
            container,
            text="Cálculo de Pausas – Tema 245 (TST) | Jornada 8h seg-sex + 4h sábado | Sem cartão-ponto",
            font=("Segoe UI", 12, "bold"),
        )
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        # Campos
        ttk.Label(container, text="Data inicial (dd/mm/aaaa):").grid(row=1, column=0, sticky="w")
        self.ent_inicio = ttk.Entry(container, width=18)
        self.ent_inicio.grid(row=1, column=1, sticky="w", padx=(0, 18))

        ttk.Label(container, text="Data final (dd/mm/aaaa):").grid(row=1, column=2, sticky="w")
        self.ent_fim = ttk.Entry(container, width=18)
        self.ent_fim.grid(row=1, column=3, sticky="w")

        ttk.Label(container, text="Salário (R$):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.ent_salario = ttk.Entry(container, width=18)
        self.ent_salario.grid(row=2, column=1, sticky="w", padx=(0, 18), pady=(10, 0))

        ttk.Label(container, text="Divisor mensal (horas):").grid(row=2, column=2, sticky="w", pady=(10, 0))
        self.ent_divisor = ttk.Entry(container, width=18)
        self.ent_divisor.grid(row=2, column=3, sticky="w", pady=(10, 0))

        ttk.Label(container, text="Adicional (%):").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.ent_adicional = ttk.Entry(container, width=18)
        self.ent_adicional.grid(row=3, column=1, sticky="w", padx=(0, 18), pady=(10, 0))

        # Defaults (seu padrão)
        self.ent_salario.insert(0, "1555,00")
        self.ent_divisor.insert(0, "244")
        self.ent_adicional.insert(0, "50")
        # Datas em branco para evitar erro automático

        # Info fixa
        info = ttk.Label(
            container,
            text=f"Regras aplicadas: Dia útil = {PAUSA_DIA_UTIL} min de pausa | Sábado = {PAUSA_SABADO} min de pausa | Domingo = 0",
            foreground="#1F4E79",
        )
        info.grid(row=4, column=0, columnspan=4, sticky="w", pady=(12, 8))

        # Botões
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=(0, 10))

        self.btn_calc = ttk.Button(btn_frame, text="Calcular", command=self.on_calcular)
        self.btn_calc.pack(side="left")

        self.btn_limpar = ttk.Button(btn_frame, text="Limpar", command=self.on_limpar)
        self.btn_limpar.pack(side="left", padx=(8, 0))

        self.btn_copiar = ttk.Button(btn_frame, text="Copiar resultado", command=self.on_copiar)
        self.btn_copiar.pack(side="left", padx=(8, 0))

        # Área de resultado
        ttk.Label(container, text="Resultado:").grid(row=6, column=0, sticky="w")
        self.txt = tk.Text(container, height=16, wrap="word", font=("Consolas", 10))
        self.txt.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(6, 0))

        # Scroll
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.txt.yview)
        scroll.grid(row=7, column=4, sticky="ns", pady=(6, 0))
        self.txt.configure(yscrollcommand=scroll.set)

        # Layout
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=0)
        container.columnconfigure(2, weight=0)
        container.columnconfigure(3, weight=1)
        container.rowconfigure(7, weight=1)

        # Rodapé
        footer = ttk.Label(
            container,
            text="Dica: use vírgula para centavos (ex.: 1.555,00).",
            foreground="#666666",
        )
        footer.grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def on_limpar(self):
        self.ent_inicio.delete(0, "end")
        self.ent_fim.delete(0, "end")
        self.txt.delete("1.0", "end")

    def on_copiar(self):
        content = self.txt.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Copiar", "Não há resultado para copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copiar", "Resultado copiado para a área de transferência.")

    def on_calcular(self):
        try:
            inicio = parse_data_br(self.ent_inicio.get())
            fim = parse_data_br(self.ent_fim.get())

            salario = parse_float_br(self.ent_salario.get())
            divisor = parse_float_br(self.ent_divisor.get())
            adicional_pct = parse_float_br(self.ent_adicional.get())

            if salario <= 0 or divisor <= 0:
                raise ValueError("Salário e divisor devem ser maiores que zero.")

            adicional = adicional_pct / 100.0

            seg_sex, sab = contar_dias(inicio, fim)

            minutos_total = seg_sex * PAUSA_DIA_UTIL + sab * PAUSA_SABADO
            horas_total = minutos_total / 60.0

            valor_hora = salario / divisor
            valor_total = horas_total * valor_hora * (1.0 + adicional)

            # Monta relatório
            linhas = []
            linhas.append("=== CÁLCULO DE PAUSAS (TEMA 245 TST) ===")
            linhas.append(f"Período: {fmt_data_br(inicio)} a {fmt_data_br(fim)}")
            linhas.append("")
            linhas.append(f"Dias seg-sex: {seg_sex}")
            linhas.append(f"Sábados:      {sab}")
            linhas.append("")
            linhas.append(f"Pausa devida por dia útil: {PAUSA_DIA_UTIL} min")
            linhas.append(f"Pausa devida por sábado:   {PAUSA_SABADO} min")
            linhas.append("")
            linhas.append(f"Minutos suprimidos (total): {minutos_total} min")
            linhas.append(f"Horas suprimidas (total):   {horas_total:.2f} h")
            linhas.append("")
            linhas.append(f"Salário:        R$ {salario:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            linhas.append(f"Divisor mensal: {divisor:g} h")
            linhas.append(f"Valor-hora:     R$ {valor_hora:,.4f}".replace(",", "X").replace(".", ",").replace("X", "."))
            linhas.append(f"Adicional:      {adicional_pct:.2f}%")
            linhas.append("")
            linhas.append(f"TOTAL DEVIDO:   R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            linhas.append("")
            linhas.append("Obs.: cálculo sem cartão-ponto, assumindo inexistência de concessão das pausas.")

            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", "\n".join(linhas))

        except ValueError as e:
            messagebox.showerror("Erro de validação", str(e))
        except Exception:
            messagebox.showerror("Erro", "Verifique se as datas estão no formato dd/mm/aaaa e os números estão corretos.")


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        import traceback
        msg = f"Erro ao iniciar:\n{e}\n\n{traceback.format_exc()}"
        # grava log
        with open("erro_execucao.log", "w", encoding="utf-8") as f:
            f.write(msg)
        # tenta mostrar popup
        try:
            import tkinter.messagebox as mb
            mb.showerror("Erro", msg)
        except:
            pass

