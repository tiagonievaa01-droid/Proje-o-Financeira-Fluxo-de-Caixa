import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA & ESTILO EXECUTIVO
# ---------------------------------------------------------
st.set_page_config(
    page_title="OdontoPrime Paulista | Projeção de Fluxo de Caixa",
    page_icon="🦷",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main { background-color: #F4F6F9; }
    .header-box {
        background: linear-gradient(90deg, #1B365D 0%, #152B4B 100%);
        padding: 20px 28px;
        border-radius: 10px;
        border-bottom: 4px solid #0D9488;
        color: white;
        margin-bottom: 18px;
    }
    .header-title { font-size: 24px; font-weight: 700; margin: 0; letter-spacing: 0.5px; }
    .header-sub { font-size: 13px; color: #CBD5E1; margin-top: 4px; }
    .kpi-card {
        background-color: #FFFFFF;
        padding: 16px 18px;
        border-radius: 10px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
        border-top: 4px solid #1B365D;
        text-align: center;
    }
    .kpi-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }
    .kpi-value { font-size: 24px; font-weight: 800; margin-top: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# CARREGAMENTO E MODELAGEM STAR SCHEMA
# ---------------------------------------------------------
ARQUIVO_EXCEL = "Base_Projecao_Caixa_OdontoPrime.xlsx"
LINK_DRIVE_PBIX = "https://drive.google.com/file/d/1JJE2ej18jxc0cdc1ohCZRdxVCgeV6v8F/view?usp=drive_link"


def fmt_brl(valor: float) -> str:
    neg = valor < 0
    v = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {v}" if neg else f"R$ {v}"


@st.cache_data
def carregar_dados():
    xls = pd.ExcelFile(ARQUIVO_EXCEL)
    f_lanc = pd.read_excel(xls, "fLancamentos")
    d_contas = pd.read_excel(xls, "dPlanoContas")
    d_esp = pd.read_excel(xls, "dEspecialidades")
    d_pag = pd.read_excel(xls, "dFormasPagamento")
    d_saldo = pd.read_excel(xls, "dSaldoInicial")

    # Padronização de chaves e junções
    df = f_lanc.merge(d_contas, on="ID_Conta", how="left")
    if "ID_Especialidade" in df.columns:
        df = df.merge(d_esp, on="ID_Especialidade", how="left")
    if "ID_Pagamento" in df.columns:
        df = df.merge(d_pag, on="ID_Pagamento", how="left")
    if "ID_Conta_Bancaria" in df.columns:
        df = df.merge(d_saldo[["ID_Conta_Bancaria", "Banco", "Conta_Bancaria"]], on="ID_Conta_Bancaria", how="left")

    # Coluna de data de vencimento / caixa
    col_data = next((c for c in ["Data_Vencimento", "Data_Caixa", "Data"] if c in df.columns), None)
    df["Data_Ref"] = pd.to_datetime(df[col_data], dayfirst=True)
    df["AnoMes"] = df["Data_Ref"].dt.to_period("M")

    meses_pt = {
        1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"
    }
    df["Mes_Ano"] = df["Data_Ref"].apply(lambda d: f"{meses_pt[d.month]}/{str(d.year)[2:]}")

    # Valores Bruto, Líquido e MDR
    col_bruto = next((c for c in ["Valor_Bruto", "Valor"] if c in df.columns), None)
    col_liq = "Valor_Liquido" if "Valor_Liquido" in df.columns else col_bruto

    df["Vlr_Bruto"] = pd.to_numeric(df[col_bruto], errors="coerce").fillna(0.0).abs()
    df["Vlr_Liquido"] = pd.to_numeric(df[col_liq], errors="coerce").fillna(0.0).abs()
    df["Custo_MDR"] = (df["Vlr_Bruto"] - df["Vlr_Liquido"]).clip(lower=0.0)

    d_saldo["Saldo_Inicial"] = pd.to_numeric(d_saldo["Saldo_Inicial"], errors="coerce").fillna(0.0)
    return df, d_saldo


df_raw, df_saldo = carregar_dados()

# ---------------------------------------------------------
# CABEÇALHO E BOTÃO DE DOWNLOAD DO .PBIX
# ---------------------------------------------------------
col_head, col_btn = st.columns([3.2, 1])
with col_head:
    st.markdown(
        """
        <div class="header-box">
            <div class="header-title">🦷 ODONTOPRIME PAULISTA</div>
            <div class="header-sub">Projeção de Fluxo de Caixa Executivo & Matriz Analítica • Horizonte: Mai/2026 a Abr/2027 • Data de Corte: 12/11/2026</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_btn:
    st.write("")
    st.link_button("📥 Baixar Arquivo Power BI (.pbix)", LINK_DRIVE_PBIX, use_container_width=True, type="primary")
    st.caption("Modelo completo com Star Schema, DAX e What-If no Google Drive.")

# ---------------------------------------------------------
# BARRA DE FILTROS & SIMULADOR WHAT-IF
# ---------------------------------------------------------
f1, f2, f3, f4 = st.columns([1.1, 1.2, 1.1, 1.6])

bancos = ["Todos"] + sorted(df_saldo["Banco"].dropna().unique().tolist())
banco_sel = f1.selectbox("Conta Bancária", bancos)

especialidades = ["Todas"] + sorted(df_raw["Especialidade"].dropna().unique().tolist()) if "Especialidade" in df_raw.columns else ["Todas"]
esp_sel = f2.selectbox("Especialidade Clínica", especialidades)

status_lista = ["Todos"] + sorted(df_raw["Status"].dropna().unique().tolist()) if "Status" in df_raw.columns else ["Todos"]
status_sel = f3.selectbox("Status Lançamento", status_lista)

simulador_pct = f4.slider("Simulador de Receita Futura (%)", min_value=-30, max_value=30, value=0, step=1, format="%d%%")
fator_sim = 1 + (simulador_pct / 100.0)

# Aplicação dos filtros
df = df_raw.copy()
saldo_ini_df = df_saldo.copy()

if banco_sel != "Todos":
    df = df[df["Banco"] == banco_sel]
    saldo_ini_df = saldo_ini_df[saldo_ini_df["Banco"] == banco_sel]

if esp_sel != "Todas" and "Especialidade" in df.columns:
    df = df[df["Especialidade"] == esp_sel]

if status_sel != "Todos" and "Status" in df.columns:
    df = df[df["Status"] == status_sel]

saldo_inicial = saldo_ini_df["Saldo_Inicial"].sum()

# Cálculo do Fluxo com Simulador What-If (aplica sobre Receitas Previstas)
def calcular_fluxo_simulado(row):
    is_entrada = str(row.get("Natureza", "")).strip().lower() == "entrada"
    status = str(row.get("Status", "")).strip().lower()
    val = row["Vlr_Liquido"]
    if is_entrada:
        if status == "previsto":
            return val * fator_sim
        return val
    return -val

df["Fluxo_Simulado"] = df.apply(calcular_fluxo_simulado, axis=1)

# Indicadores Executivos (KPIs)
is_realizado = df["Status"].str.lower() == "realizado"
is_previsto = df["Status"].str.lower() == "previsto"
is_inadimplente = ~df["Status"].str.lower().isin(["realizado", "previsto"])

saldo_em_caixa = saldo_inicial + df.loc[is_realizado, "Fluxo_Simulado"].sum()
geracao_liquida_proj = df.loc[is_realizado | is_previsto, "Fluxo_Simulado"].sum()
saldo_projetado_acum = saldo_inicial + geracao_liquida_proj
inadimplencia = df.loc[is_inadimplente & (df["Natureza"].str.lower() == "entrada"), "Vlr_Bruto"].sum()
custo_mdr = df.loc[(is_realizado | is_previsto) & (df["Natureza"].str.lower() == "entrada"), "Custo_MDR"].sum()

k1, k2, k3, k4, k5 = st.columns(5)
cards = [
    (k1, "Saldo em Caixa", fmt_brl(saldo_em_caixa), "#1B365D"),
    (k2, "Saldo Projetado Acumulado", fmt_brl(saldo_projetado_acum), "#0D9488"),
    (k3, "Geração Líquida Projetada", fmt_brl(geracao_liquida_proj), "#0284C7"),
    (k4, "Inadimplência (R$)", fmt_brl(inadimplencia), "#E11D48"),
    (k5, "Custo Taxas Cartão (MDR)", fmt_brl(custo_mdr), "#D97706"),
]
for col, titulo, valor, cor in cards:
    col.markdown(
        f"""
        <div class="kpi-card" style="border-top-color: {cor};">
            <div class="kpi-title" style="color: {cor};">{titulo}</div>
            <div class="kpi-value" style="color: {cor};">{valor}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# ---------------------------------------------------------
# ABAS (PÁGINA 1: VISÃO EXECUTIVA | PÁGINA 2: MATRIZ ANALÍTICA)
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Visão Executiva", "📑 Matriz Analítica (Fluxo Direto)"])

with tab1:
    c_left, c_right = st.columns([1.45, 1])

    # Gráfico 1: Fluxo de Caixa Mensal e Evolução do Saldo
    df_valid = df[is_realizado | is_previsto].copy()
    meses_ord = (
        df_valid[["AnoMes", "Mes_Ano"]]
        .drop_duplicates()
        .sort_values("AnoMes")
    )

    ent_real, ent_prev, sai_real, sai_prev, saldo_acum_lista = [], [], [], [], []
    acum = saldo_inicial

    for _, m in meses_ord.iterrows():
        sub = df_valid[df_valid["AnoMes"] == m["AnoMes"]]
        er = sub[(sub["Natureza"].str.lower() == "entrada") & (sub["Status"].str.lower() == "realizado")]["Fluxo_Simulado"].sum()
        ep = sub[(sub["Natureza"].str.lower() == "entrada") & (sub["Status"].str.lower() == "previsto")]["Fluxo_Simulado"].sum()
        sr = sub[(sub["Natureza"].str.lower() == "saída") & (sub["Status"].str.lower() == "realizado")]["Fluxo_Simulado"].sum()
        sp = sub[(sub["Natureza"].str.lower() == "saída") & (sub["Status"].str.lower() == "previsto")]["Fluxo_Simulado"].sum()
        acum += (er + ep + sr + sp)

        ent_real.append(er)
        ent_prev.append(ep)
        sai_real.append(sr)
        sai_prev.append(sp)
        saldo_acum_lista.append(acum)

    fig_combo = go.Figure()
    x_labels = meses_ord["Mes_Ano"].tolist()

    fig_combo.add_trace(go.Bar(name="Entradas Realizadas", x=x_labels, y=ent_real, marker_color="#0D9488"))
    fig_combo.add_trace(go.Bar(name="Entradas Previstas", x=x_labels, y=ent_prev, marker_color="#5EEAD4"))
    fig_combo.add_trace(go.Bar(name="Saídas Realizadas", x=x_labels, y=sai_real, marker_color="#E11D48"))
    fig_combo.add_trace(go.Bar(name="Saídas Previstas", x=x_labels, y=sai_prev, marker_color="#FDA4AF"))
    fig_combo.add_trace(
        go.Scatter(
            name="Saldo Projetado Acumulado",
            x=x_labels,
            y=saldo_acum_lista,
            mode="lines+markers",
            line=dict(color="#1B365D", width=3),
            marker=dict(size=6),
        )
    )
    fig_combo.update_layout(
        title="Fluxo de Caixa Mensal e Evolução do Saldo",
        barmode="relative",
        template="plotly_white",
        height=430,
        legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=45, b=60),
    )
    c_left.plotly_chart(fig_combo, use_container_width=True)

    # Gráfico 2: Ponte de Geração de Caixa (Waterfall)
    wf_df = (
        df_valid.groupby("Grupo_Fluxo", as_index=False)["Fluxo_Simulado"]
        .sum()
        .sort_values("Fluxo_Simulado", ascending=False)
    )
    x_wf = wf_df["Grupo_Fluxo"].tolist() + ["Total"]
    y_wf = wf_df["Fluxo_Simulado"].tolist() + [0]
    measures = ["relative"] * len(wf_df) + ["total"]

    fig_wf = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=measures,
            x=x_wf,
            y=y_wf,
            increasing=dict(marker=dict(color="#0D9488")),
            decreasing=dict(marker=dict(color="#E11D48")),
            totals=dict(marker=dict(color="#1B365D")),
            connector=dict(line=dict(color="#CBD5E1")),
        )
    )
    fig_wf.update_layout(
        title="Ponte de Geração de Caixa (12 Meses)",
        template="plotly_white",
        height=430,
        margin=dict(l=20, r=20, t=45, b=60),
    )
    c_right.plotly_chart(fig_wf, use_container_width=True)

with tab2:
    st.subheader("Demonstrativo de Fluxo de Caixa Direto (Mensal por Especialidade)")
    nivel = st.radio(
        "Nível de detalhamento da matriz:",
        ["Grupo de Fluxo", "Grupo + Categoria", "Completo (Grupo + Categoria + Subcategoria)"],
        horizontal=True,
    )

    if nivel == "Grupo de Fluxo":
        idx_cols = ["Grupo_Fluxo"]
    elif nivel == "Grupo + Categoria":
        idx_cols = ["Grupo_Fluxo", "Categoria"]
    else:
        idx_cols = ["Grupo_Fluxo", "Categoria", "Subcategoria"]

    piv = pd.pivot_table(
        df_valid,
        values="Fluxo_Simulado",
        index=idx_cols,
        columns="Mes_Ano",
        aggfunc="sum",
        fill_value=0.0,
    )

    cols_ordenadas = [m for m in meses_ord["Mes_Ano"].tolist() if m in piv.columns]
    piv = piv[cols_ordenadas]
    piv["Total"] = piv.sum(axis=1)

    # Linha de Geração Líquida Total
    total_row = pd.DataFrame([piv.sum(axis=0)], index=pd.MultiIndex.from_tuples([tuple(["GERAÇÃO LÍQUIDA (R$)"] + [""] * (len(idx_cols) - 1))], names=idx_cols) if len(idx_cols) > 1 else pd.Index(["GERAÇÃO LÍQUIDA (R$)"], name=idx_cols[0]))
    piv_final = pd.concat([piv, total_row])

    def cor_condicional(val):
        if isinstance(val, (int, float)):
            if val < 0:
                return "color: #E11D48; font-weight: 600;"
            elif val > 0:
                return "color: #0D9488; font-weight: 600;"
        return ""

    st.dataframe(
        piv_final.style.format(fmt_brl).map(cor_condicional),
        use_container_width=True,
        height=480,
    )