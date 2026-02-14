from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date, timedelta

# PDF (reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


# =========================
# REGRAS FIXAS (ESCRITÓRIO)
# =========================
MINUTOS_SEG_SEX = 8 * 60   # 480
MINUTOS_SABADO = 4 * 60    # 240

def pausas_devidas_em_minutos(min_trabalhados: int) -> int:
    """10 minutos a cada 90 minutos trabalhados."""
    return (min_trabalhados // 90) * 10

PAUSA_DIA_UTIL_MIN = pausas_devidas_em_minutos(MINUTOS_SEG_SEX)  # 50
PAUSA_SABADO_MIN = pausas_devidas_em_minutos(MINUTOS_SABADO)     # 20


# =========================
# UTILITÁRIOS
# =========================
def parse_data_br(s: str) -> date:
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()

def fmt_data_br(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def parse_float_br(s: str) -> float:
    """
    Aceita: 1555 | 1555.00 | 1.555,00 | 1555,00
    """
    s = s.strip().replace(" ", "")
    if not s:
        raise ValueError("Campo numérico vazio.")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)

def brl(v: float, casas: int = 2) -> str:
    """
    Formata número para padrão Brasil: 1.234,56
    """
    fmt = f"{v:,.{casas}f}"
    return fmt.replace(",", "X").replace(".", ",").replace("X", ".")

def primeiro_dia_mes(d: date) -> date:
    return date(d.year, d.month, 1)

def proximo_mes(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)

def ultimo_dia_mes(d: date) -> date:
    return proximo_mes(primeiro_dia_mes(d)) - timedelta(days=1)

def contar_dias_periodo(inicio: date, fim: date) -> tuple[int, int]:
    """
    Conta (seg-sex, sábados) no período inclusive.
    Domingos ignorados.
    """
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

def contar_dias_mes(inicio: date, fim: date) -> dict:
    """
    Conta dias no intervalo [inicio, fim]:
      - seg_sex: seg a sex
      - sab: sábado
      - dom: domingo
    """
    seg_sex = sab = dom = 0
    d = inicio
    while d <= fim:
        wd = d.weekday()
        if 0 <= wd <= 4:
            seg_sex += 1
        elif wd == 5:
            sab += 1
        else:
            dom += 1
        d += timedelta(days=1)
    return {"seg_sex": seg_sex, "sab": sab, "dom": dom}

def app_base_dir() -> str:
    """
    Pasta base para salvar PDFs/logs:
    - Se for .exe (PyInstaller), usa a pasta do executável.
    - Se for .py, usa a pasta do arquivo.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# =========================
# CÁLCULO (BASE + REFLEXOS)
# =========================
def calcular_mensal(
    inicio: date,
    fim: date,
    salario: float,
    divisor: float,
    adicional: float,
    pausa_dia_util_min: int = PAUSA_DIA_UTIL_MIN,
    pausa_sab_min: int = PAUSA_SABADO_MIN,
) -> list[dict]:
    """
    Retorna lista mês a mês contendo:
      - valor_base (pausas)
      - dsr (considerando domingos como descanso)
      - base_mais_dsr
    Observação: sábado é dia trabalhado (jornada 4h).
    """
    if divisor <= 0 or salario <= 0:
        raise ValueError("Salário e divisor devem ser maiores que zero.")

    valor_hora = salario / divisor
    atual = primeiro_dia_mes(inicio)
    out: list[dict] = []

    while atual <= fim:
        ini_mes = max(inicio, atual)
        fim_mes = min(fim, ultimo_dia_mes(atual))

        dias = contar_dias_mes(ini_mes, fim_mes)
        dias_trabalhados = dias["seg_sex"] + dias["sab"]
        domingos = dias["dom"]

        minutos_base = dias["seg_sex"] * pausa_dia_util_min + dias["sab"] * pausa_sab_min
        horas_base = minutos_base / 60.0
        valor_base = horas_base * valor_hora * (1.0 + adicional)

        # DSR: (Base / dias trabalhados) * domingos
        dsr = (valor_base / dias_trabalhados) * domingos if dias_trabalhados > 0 else 0.0

        out.append(
            {
                "mes": f"{ini_mes.year:04d}-{ini_mes.month:02d}",
                "intervalo": f"{fmt_data_br(ini_mes)} a {fmt_data_br(fim_mes)}",
                "dias_trabalhados": int(dias_trabalhados),
                "domingos": int(domingos),
                "minutos_base": int(minutos_base),
                "horas_base": round(horas_base, 4),
                "valor_base": round(valor_base, 2),
                "dsr": round(dsr, 2),
                "base_mais_dsr": round(valor_base + dsr, 2),
            }
        )

        atual = proximo_mes(atual)

    return out

def calcular_reflexos(
    mensal: list[dict],
    fgts_aliquota: float = 0.08,
    fgts_sobre_13_ferias: bool = False,
) -> dict:
    """
    Reflexos (padrão escritório, editável por checkbox):
      - FGTS sobre (Base + DSR)
      - 13º proporcional: média mensal (Base+DSR) * (meses/12)
      - Férias + 1/3 proporcional: média mensal (Base+DSR) * (meses/12) + 1/3
      - Opcional: FGTS também sobre 13º e Férias+1/3
    """
    meses = len(mensal)
    soma_base = sum(m["valor_base"] for m in mensal)
    soma_dsr = sum(m["dsr"] for m in mensal)
    soma_base_dsr = sum(m["base_mais_dsr"] for m in mensal)

    media = (soma_base_dsr / meses) if meses else 0.0

    decimo_terceiro = media * (meses / 12.0)
    ferias = media * (meses / 12.0)
    terco = ferias / 3.0
    ferias_mais_terco = ferias + terco

    fgts_base = soma_base_dsr * fgts_aliquota
    fgts_extra = (decimo_terceiro + ferias_mais_terco) * fgts_aliquota if fgts_sobre_13_ferias else 0.0
    fgts_total = fgts_base + fgts_extra

    total_geral = soma_base_dsr + decimo_terceiro + ferias_mais_terco + fgts_total

    return {
        "meses": meses,
        "soma_base": round(soma_base, 2),
        "soma_dsr": round(soma_dsr, 2),
        "soma_base_dsr": round(soma_base_dsr, 2),
        "media_mensal_base_dsr": round(media, 2),
        "13o_proporcional": round(decimo_terceiro, 2),
        "ferias_proporcional": round(ferias, 2),
        "terco_constitucional": round(terco, 2),
        "ferias_mais_terco": round(ferias_mais_terco, 2),
        "fgts_base": round(fgts_base, 2),
        "fgts_extra": round(fgts_extra, 2),
        "fgts_total": round(fgts_total, 2),
        "total_geral": round(total_geral, 2),
    }


# =========================
# PDF
# =========================
def gerar_pdf_relatorio(
    caminho_pdf: str,
    titulo: str,
    linhas: list[str],
    meta: dict,
):
    """
    Gera PDF simples e limpo, padrão escritório.
    - meta pode conter: escritorio, processo, cliente, empregador, cct, data_emissao
    """
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    largura, altura = A4

    margem_x = 2.0 * cm
    y = altura - 2.0 * cm

    # Cabeçalho
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margem_x, y, meta.get("escritorio", "ESCRITÓRIO"))
    y -= 0.6 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margem_x, y, titulo)
    y -= 0.7 * cm

    c.setFont("Helvetica", 10)
    dados = [
        f"Cliente: {meta.get('cliente','')}",
        f"Empregador: {meta.get('empregador','')}",
        f"Processo: {meta.get('processo','')}",
        f"CCT/Norma: {meta.get('cct','')}",
        f"Data de emissão: {meta.get('data_emissao','')}",
    ]
    for item in dados:
        if item.strip().endswith(":"):
            continue
        if len(item.strip()) > 2:
            c.drawString(margem_x, y, item)
            y -= 0.45 * cm

    y -= 0.2 * cm
    c.line(margem_x, y, largura - margem_x, y)
    y -= 0.6 * cm

    # Corpo
    c.setFont("Helvetica", 10)
    line_height = 0.45 * cm

    for linha in linhas:
        # Quebra de página
        if y < 2.0 * cm:
            c.showPage()
            y = altura - 2.0 * cm
            c.setFont("Helvetica", 10)

        # Quebra simples por largura (sem hyphenation)
        max_chars = 110
        if len(linha) <= max_chars:
            c.drawString(margem_x, y, linha)
            y -= line_height
        else:
            # quebra em blocos
            start = 0
            while start < len(linha):
                if y < 2.0 * cm:
                    c.showPage()
                    y = altura - 2.0 * cm
                    c.setFont("Helvetica", 10)
                chunk = linha[start:start + max_chars]
                c.drawString(margem_x, y, chunk)
                y -= line_height
                start += max_chars

    # Rodapé
    c.showPage()
    c.save()


# =========================
# INTERFACE (TKINTER)
# =========================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema Definitivo – Pausas (Tema 245 TST) + Reflexos + PDF")
        self.geometry("1100x720")
        self.minsize(1100, 720)

        self.resultado_linhas: list[str] = []
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        container = ttk.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        # ---------- Cabeçalho / Metadados ----------
        ttk.Label(container, text="Dados do Relatório (PDF)", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=8, sticky="w")

        ttk.Label(container, text="Escritório:").grid(row=1, column=0, sticky="w")
        self.ent_escritorio = ttk.Entry(container, width=40)
        self.ent_escritorio.insert(0, "SEU ESCRITÓRIO – ADVOCACIA")
        self.ent_escritorio.grid(row=1, column=1, sticky="w", padx=(0, 14))

        ttk.Label(container, text="Processo:").grid(row=1, column=2, sticky="w")
        self.ent_processo = ttk.Entry(container, width=24)
        self.ent_processo.grid(row=1, column=3, sticky="w", padx=(0, 14))

        ttk.Label(container, text="CCT/Norma:").grid(row=1, column=4, sticky="w")
        self.ent_cct = ttk.Entry(container, width=30)
        self.ent_cct.insert(0, "CCT – piso R$ 1.555,00 e divisor 244 (ajustar)")
        self.ent_cct.grid(row=1, column=5, sticky="w")

        ttk.Label(container, text="Cliente:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.ent_cliente = ttk.Entry(container, width=40)
        self.ent_cliente.grid(row=2, column=1, sticky="w", padx=(0, 14), pady=(6, 0))

        ttk.Label(container, text="Empregador:").grid(row=2, column=2, sticky="w", pady=(6, 0))
        self.ent_empregador = ttk.Entry(container, width=40)
        self.ent_empregador.grid(row=2, column=3, columnspan=3, sticky="w", pady=(6, 0))

        # ---------- Parâmetros de cálculo ----------
        ttk.Label(container, text="Parâmetros do Cálculo", font=("Segoe UI", 11, "bold")).grid(row=3, column=0, columnspan=8, sticky="w", pady=(12, 0))

        ttk.Label(container, text="Data inicial (dd/mm/aaaa):").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.ent_inicio = ttk.Entry(container, width=18)
        self.ent_inicio.grid(row=4, column=1, sticky="w", pady=(6, 0), padx=(0, 14))

        ttk.Label(container, text="Data final (dd/mm/aaaa):").grid(row=4, column=2, sticky="w", pady=(6, 0))
        self.ent_fim = ttk.Entry(container, width=18)
        self.ent_fim.grid(row=4, column=3, sticky="w", pady=(6, 0), padx=(0, 14))

        ttk.Label(container, text="Salário (R$):").grid(row=4, column=4, sticky="w", pady=(6, 0))
        self.ent_salario = ttk.Entry(container, width=14)
        self.ent_salario.insert(0, "1.555,00")
        self.ent_salario.grid(row=4, column=5, sticky="w", pady=(6, 0), padx=(0, 14))

        ttk.Label(container, text="Divisor:").grid(row=4, column=6, sticky="w", pady=(6, 0))
        self.ent_divisor = ttk.Entry(container, width=10)
        self.ent_divisor.insert(0, "244")
        self.ent_divisor.grid(row=4, column=7, sticky="w", pady=(6, 0))

        ttk.Label(container, text="Adicional (%):").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.ent_adicional = ttk.Entry(container, width=18)
        self.ent_adicional.insert(0, "50")
        self.ent_adicional.grid(row=5, column=1, sticky="w", pady=(6, 0), padx=(0, 14))

        ttk.Label(container, text="FGTS (%):").grid(row=5, column=2, sticky="w", pady=(6, 0))
        self.ent_fgts = ttk.Entry(container, width=18)
        self.ent_fgts.insert(0, "8")
        self.ent_fgts.grid(row=5, column=3, sticky="w", pady=(6, 0), padx=(0, 14))

        self.var_reflexos = tk.BooleanVar(value=True)
        ttk.Checkbutton(container, text="Incluir reflexos (DSR, 13º, Férias+1/3, FGTS)", variable=self.var_reflexos)\
            .grid(row=5, column=4, columnspan=4, sticky="w", pady=(6, 0))

        self.var_fgts_13_ferias = tk.BooleanVar(value=False)
        ttk.Checkbutton(container, text="FGTS também sobre 13º e Férias+1/3", variable=self.var_fgts_13_ferias)\
            .grid(row=6, column=4, columnspan=4, sticky="w", pady=(2, 0))

        info = ttk.Label(
            container,
            text=f"Regras: Dia útil = {PAUSA_DIA_UTIL_MIN} min | Sábado = {PAUSA_SABADO_MIN} min | DSR mensal considera domingos como descanso.",
            foreground="#1F4E79",
        )
        info.grid(row=7, column=0, columnspan=8, sticky="w", pady=(10, 8))

        # ---------- Botões ----------
        btn = ttk.Frame(container)
        btn.grid(row=8, column=0, columnspan=8, sticky="w", pady=(0, 10))

        ttk.Button(btn, text="Calcular", command=self.on_calcular).pack(side="left")
        ttk.Button(btn, text="Limpar", command=self.on_limpar).pack(side="left", padx=(8, 0))
        ttk.Button(btn, text="Copiar resultado", command=self.on_copiar).pack(side="left", padx=(8, 0))
        ttk.Button(btn, text="Gerar PDF", command=self.on_pdf).pack(side="left", padx=(8, 0))

        # ---------- Resultado ----------
        ttk.Label(container, text="Resultado:").grid(row=9, column=0, sticky="w")
        self.txt = tk.Text(container, height=22, wrap="word", font=("Consolas", 10))
        self.txt.grid(row=10, column=0, columnspan=8, sticky="nsew", pady=(6, 0))

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.txt.yview)
        scroll.grid(row=10, column=8, sticky="ns", pady=(6, 0))
        self.txt.configure(yscrollcommand=scroll.set)

        # Responsividade
        for col in range(8):
            container.columnconfigure(col, weight=1 if col in (3, 5, 7) else 0)
        container.rowconfigure(10, weight=1)

        footer = ttk.Label(container, text="Dica: datas em dd/mm/aaaa. Valores podem ser 1.555,00.", foreground="#666666")
        footer.grid(row=11, column=0, columnspan=8, sticky="w", pady=(8, 0))

    def on_limpar(self):
        self.ent_inicio.delete(0, "end")
        self.ent_fim.delete(0, "end")
        self.txt.delete("1.0", "end")
        self.resultado_linhas = []

    def on_copiar(self):
        content = self.txt.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Copiar", "Não há resultado para copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copiar", "Resultado copiado para a área de transferência.")

    def _montar_relatorio(self) -> tuple[str, list[str], dict]:
        """
        Calcula e monta o relatório como lista de linhas (para tela e PDF).
        Retorna: (titulo, linhas, meta)
        """
        inicio = parse_data_br(self.ent_inicio.get())
        fim = parse_data_br(self.ent_fim.get())

        salario = parse_float_br(self.ent_salario.get())
        divisor = parse_float_br(self.ent_divisor.get())
        adicional_pct = parse_float_br(self.ent_adicional.get())
        adicional = adicional_pct / 100.0

        fgts_pct = parse_float_br(self.ent_fgts.get())
        fgts_aliquota = fgts_pct / 100.0

        incluir_reflexos = bool(self.var_reflexos.get())
        fgts_13_ferias = bool(self.var_fgts_13_ferias.get())

        # Totais do período (base sem reflexos)
        seg_sex, sab = contar_dias_periodo(inicio, fim)
        minutos_total = seg_sex * PAUSA_DIA_UTIL_MIN + sab * PAUSA_SABADO_MIN
        horas_total = minutos_total / 60.0

        valor_hora = salario / divisor
        total_base = horas_total * valor_hora * (1.0 + adicional)

        linhas: list[str] = []
        linhas.append("=== CÁLCULO DE PAUSAS (TEMA 245 TST) – SEM CARTÃO-PONTO ===")
        linhas.append(f"Período: {fmt_data_br(inicio)} a {fmt_data_br(fim)}")
        linhas.append("")
        linhas.append("Premissas adotadas:")
        linhas.append("• Jornada presumida: 8h (seg–sex) e 4h (sábado).")
        linhas.append("• Pausa: 10 minutos a cada 90 minutos trabalhados.")
        linhas.append("• Considera-se ausência de concessão das pausas.")
        linhas.append("")
        linhas.append(f"Pausa devida por dia útil: {PAUSA_DIA_UTIL_MIN} min")
        linhas.append(f"Pausa devida por sábado:   {PAUSA_SABADO_MIN} min")
        linhas.append("")
        linhas.append(f"Dias seg–sex no período: {seg_sex}")
        linhas.append(f"Sábados no período:      {sab}")
        linhas.append("")
        linhas.append(f"Minutos suprimidos (total): {minutos_total} min")
        linhas.append(f"Horas suprimidas (total):   {horas_total:.2f} h")
        linhas.append("")
        linhas.append(f"Salário:        R$ {brl(salario)}")
        linhas.append(f"Divisor mensal: {divisor:g}")
        linhas.append(f"Valor-hora:     R$ {brl(valor_hora, 4)}")
        linhas.append(f"Adicional:      {adicional_pct:.2f}%")
        linhas.append("")
        linhas.append(f"TOTAL BASE (pausas): R$ {brl(total_base)}")

        if incluir_reflexos:
            mensal = calcular_mensal(
                inicio=inicio,
                fim=fim,
                salario=salario,
                divisor=divisor,
                adicional=adicional,
                pausa_dia_util_min=PAUSA_DIA_UTIL_MIN,
                pausa_sab_min=PAUSA_SABADO_MIN,
            )
            ref = calcular_reflexos(
                mensal,
                fgts_aliquota=fgts_aliquota,
                fgts_sobre_13_ferias=fgts_13_ferias,
            )

            linhas.append("")
            linhas.append("=== RESUMO MENSAL (BASE + DSR) ===")
            for m in mensal:
                linhas.append(
                    f"{m['mes']} ({m['intervalo']}) | "
                    f"Dias trab.: {m['dias_trabalhados']} | Domingos: {m['domingos']} | "
                    f"Base: R$ {brl(m['valor_base'])} | DSR: R$ {brl(m['dsr'])} | "
                    f"Total mês: R$ {brl(m['base_mais_dsr'])}"
                )

            linhas.append("")
            linhas.append("=== REFLEXOS ===")
            linhas.append(f"Soma Base (pausas):          R$ {brl(ref['soma_base'])}")
            linhas.append(f"Soma DSR:                    R$ {brl(ref['soma_dsr'])}")
            linhas.append(f"Soma Base + DSR:             R$ {brl(ref['soma_base_dsr'])}")
            linhas.append(f"Média mensal (Base+DSR):      R$ {brl(ref['media_mensal_base_dsr'])}")
            linhas.append("")
            linhas.append(f"13º proporcional:            R$ {brl(ref['13o_proporcional'])}")
            linhas.append(f"Férias proporcionais:        R$ {brl(ref['ferias_proporcional'])}")
            linhas.append(f"1/3 constitucional:          R$ {brl(ref['terco_constitucional'])}")
            linhas.append(f"Férias + 1/3:                R$ {brl(ref['ferias_mais_terco'])}")
            linhas.append("")
            linhas.append(f"FGTS ({fgts_pct:.2f}%):")
            linhas.append(f"• sobre Base+DSR:             R$ {brl(ref['fgts_base'])}")
            if fgts_13_ferias:
                linhas.append(f"• sobre 13º e Férias+1/3:     R$ {brl(ref['fgts_extra'])}")
            linhas.append(f"FGTS total:                  R$ {brl(ref['fgts_total'])}")
            linhas.append("")
            linhas.append(f"TOTAL GERAL (c/ reflexos):   R$ {brl(ref['total_geral'])}")
            linhas.append("")
            linhas.append("Notas técnicas (parâmetros do sistema):")
            linhas.append("• DSR mensal calculado como: (Base do mês / dias trabalhados no mês) × domingos do mês.")
            linhas.append("• Sábado é considerado dia trabalhado (jornada de 4h).")
            linhas.append("• Feriados não são considerados neste modelo (pode ser implementado se necessário).")

        titulo = "Relatório de Cálculo – Pausas (Tema 245 TST) + Reflexos"
        meta = {
            "escritorio": self.ent_escritorio.get().strip(),
            "processo": self.ent_processo.get().strip(),
            "cliente": self.ent_cliente.get().strip(),
            "empregador": self.ent_empregador.get().strip(),
            "cct": self.ent_cct.get().strip(),
            "data_emissao": fmt_data_br(date.today()),
        }
        return titulo, linhas, meta

    def on_calcular(self):
        try:
            titulo, linhas, _meta = self._montar_relatorio()
            self.resultado_linhas = [titulo] + [""] + linhas

            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", "\n".join(self.resultado_linhas))

        except ValueError as e:
            messagebox.showerror("Erro de validação", str(e))
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao calcular.\n\nDetalhe: {e}")

    def on_pdf(self):
        try:
            if not self.resultado_linhas:
                # se ainda não calculou, calcula primeiro
                self.on_calcular()
                if not self.resultado_linhas:
                    return

            titulo, linhas, meta = self._montar_relatorio()

            # Sugestão de nome
            nome_base = "Relatorio_Pausas_Tema245"
            if meta.get("cliente"):
                nome_base += "_" + meta["cliente"].replace(" ", "_")[:30]
            nome_base += "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".pdf"

            caminho_inicial = os.path.join(app_base_dir(), nome_base)

            caminho_pdf = filedialog.asksaveasfilename(
                title="Salvar PDF",
                defaultextension=".pdf",
                initialfile=os.path.basename(caminho_inicial),
                initialdir=app_base_dir(),
                filetypes=[("PDF", "*.pdf")],
            )
            if not caminho_pdf:
                return

            gerar_pdf_relatorio(
                caminho_pdf=caminho_pdf,
                titulo=titulo,
                linhas=linhas,
                meta=meta,
            )

            messagebox.showinfo("PDF gerado", f"PDF gerado com sucesso:\n\n{caminho_pdf}")

        except Exception as e:
            messagebox.showerror("Erro PDF", f"Não foi possível gerar o PDF.\n\nDetalhe: {e}")


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        # Log para quando virar .exe e fechar silencioso
        import traceback
        msg = f"Erro ao iniciar:\n{e}\n\n{traceback.format_exc()}"
        try:
            with open(os.path.join(app_base_dir(), "erro_execucao.log"), "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        try:
            import tkinter.messagebox as mb
            mb.showerror("Erro", msg)
        except Exception:
            pass
