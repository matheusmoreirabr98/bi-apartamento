import time
import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client
import plotly.express as px

# ✅ TEM QUE SER O PRIMEIRO COMANDO STREAMLIT
st.set_page_config(page_title="Apartamento", layout="wide")

st.markdown("""
<script>
document.addEventListener("DOMContentLoaded", function() {
    const inputs = window.parent.document.querySelectorAll('input[data-testid="stTextInput"]');
    inputs.forEach(input => {
        input.setAttribute("inputmode", "numeric");
    });
});
</script>
""", unsafe_allow_html=True)

st.title("🏠 Apartamento")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}

.section-title {
    font-size: 28px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 0.3rem;
}

.section-subtitle {
    font-size: 14px;
    color: #94a3b8;
    margin-bottom: 1.2rem;
}

.tech-card {
    background: linear-gradient(135deg, rgba(17,24,39,0.95) 0%, rgba(15,23,42,0.95) 100%);
    border: 1px solid rgba(148,163,184,0.18);
    border-radius: 20px;
    padding: 18px 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.22);
    min-height: 122px;
}

.tech-label {
    font-size: 13px;
    color: #94a3b8;
    font-weight: 600;
    margin-bottom: 12px;
}

.tech-value {
    font-size: 34px;
    color: #f8fafc;
    font-weight: 800;
    line-height: 1.05;
}

.tech-sub {
    font-size: 13px;
    color: #cbd5e1;
    margin-top: 10px;
}

.metric-chip {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(59,130,246,0.16);
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 700;
}

div[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid rgba(148,163,184,0.18);
}

div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
}

div[data-testid="stSidebar"] * {
    color: #e5e7eb;
}

div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] > div {
    background: #111827 !important;
    border: 1px solid rgba(148,163,184,0.18) !important;
    border-radius: 14px !important;
}

div[data-testid="stDateInput"] > div > div,
div[data-testid="stTextInput"] > div > div {
    background: #111827 !important;
    border: 1px solid rgba(148,163,184,0.18) !important;
    border-radius: 14px !important;
}

.stButton > button {
    border-radius: 14px;
    border: 1px solid rgba(148,163,184,0.18);
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    color: white;
    font-weight: 700;
}

h1, h2, h3, h4, h5, h6, p, label {
    color: #e5e7eb !important;
}
</style>
""", unsafe_allow_html=True)

# ====== Secrets (Streamlit Cloud / Local) ======
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CATEGORIAS = [
    "Sinal Ato",
    "Sinal",
    "Diferença",
    "Evolução de Obra",
    "ITBI e Registro",
    "Parc. Entrada Direcional",
    "Financiamento Caixa",
]

LIMITES = {
    "Sinal Ato": 3,
    "Sinal": 3,
    "Diferença": 6,
    "Evolução de Obra": 28,
    "ITBI e Registro": 43,
    "Parc. Entrada Direcional": 57,
    "Financiamento Caixa": 420,
}

TOTAL_PREVISTO_MANUAL = 280000.00  # ajuste se quiser

CORES_CATEGORIAS = {
    "Sinal Ato": "#00C2FF",
    "Sinal": "#3B82F6",
    "Diferença": "#8B5CF6",
    "Evolução de Obra": "#14B8A6",
    "ITBI e Registro": "#F59E0B",
    "Parc. Entrada Direcional": "#EF4444",
    "Financiamento Caixa": "#6366F1",
}


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_df():
    res = supabase.table("pagamentos").select("*").order("data_pagamento").execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    df["data_pagamento"] = pd.to_datetime(df["data_pagamento"])
    df["valor"] = pd.to_numeric(df["valor"])
    df["mes"] = df["data_pagamento"].dt.to_period("M").astype(str)
    return df


# ====== LOGIN ======
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    pw = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if pw == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Senha incorreta")
    st.stop()

# ====== SESSION STATE ======
if "form_categoria" not in st.session_state:
    st.session_state.form_categoria = None

if "form_valor" not in st.session_state:
    st.session_state.form_valor = 0.0

if "form_obs" not in st.session_state:
    st.session_state.form_obs = ""

if "clear_valor_input" not in st.session_state:
    st.session_state.clear_valor_input = False

if "valor_digits" not in st.session_state:
    st.session_state.valor_digits = ""

if "valor_mask" not in st.session_state:
    st.session_state.valor_mask = ""


tab1, tab2, tab3 = st.tabs(["➕ Lançar", "📊 Dashboard", "🧾 Histórico"])

# ================== TAB 1: LANÇAR ==================
with tab1:
    st.subheader("Adicionar pagamento")

    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        d = st.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")

    with c2:
        df_tmp = get_df()

        counts = {}
        if not df_tmp.empty and "categoria" in df_tmp.columns:
            counts = df_tmp["categoria"].value_counts().to_dict()

        opcoes = []
        label_to_cat = {}

        for c in CATEGORIAS:
            limite = LIMITES.get(c, None)
            atual = counts.get(c, 0)

            if limite is not None and atual >= limite:
                continue

            label = f"{c} ({atual}/{limite})" if limite is not None else c
            opcoes.append(label)
            label_to_cat[label] = c

        if not opcoes:
            st.warning("✅ Todas as categorias com limite já foram concluídas.")
            st.stop()

        label_escolhido = st.selectbox("Categoria", [""] + opcoes, index=0)
        cat = None if label_escolhido == "" else label_to_cat[label_escolhido]

    with c3:
        # limpa antes de renderizar o widget
        if st.session_state.clear_valor_input:
            st.session_state.valor_digits = ""
            st.session_state.valor_mask = ""
            st.session_state.clear_valor_input = False

        def on_valor_change():
            s = st.session_state.valor_mask
            digits = "".join(ch for ch in s if ch.isdigit())
            st.session_state.valor_digits = digits
            v = (int(digits) / 100) if digits else 0.0

            # cuidado: no callback pode atualizar a chave do próprio widget
            st.session_state.valor_mask = brl(v)

        st.text_input(
            "Valor",
            key="valor_mask",
            on_change=on_valor_change,
            placeholder="R$ 0,00"
        )

        valor = (int(st.session_state.valor_digits) / 100) if st.session_state.valor_digits else 0.0
        st.caption(f"Valor: {brl(valor)}")

    if st.button("Salvar"):
        if cat is None or valor <= 0:
            st.error("Preencha a Categoria e um Valor maior que 0.")
        else:
            supabase.table("pagamentos").insert({
                "data_pagamento": str(d),
                "categoria": cat,
                "valor": float(valor)
            }).execute()

            st.session_state.clear_valor_input = True
            st.success("✅ Lançamento registrado!")
            time.sleep(0.8)
            st.rerun()

# ================== TAB 2: DASHBOARD ==================
with tab2:
    df = get_df()

    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
        df["ano"] = df["data_pagamento"].dt.year.astype(str)
        df["mes_ref"] = df["data_pagamento"].dt.strftime("%m/%Y")

        anos = sorted(df["ano"].unique().tolist())
        categorias_disp = sorted(df["categoria"].unique().tolist())
        meses_disp = sorted(
            df["mes_ref"].unique().tolist(),
            key=lambda x: pd.to_datetime(x, format="%m/%Y")
        )

        with st.sidebar:
            st.markdown("## ⚙️ Filtros")
            ano = st.selectbox("Ano", ["Todos"] + anos, key="dash_ano")
            categoria = st.selectbox("Categoria", ["Todas"] + categorias_disp, key="dash_categoria")
            meses_sel = st.multiselect("Meses", meses_disp, default=meses_disp, key="dash_meses")

        df_f = df.copy()

        if ano != "Todos":
            df_f = df_f[df_f["ano"] == ano]

        if categoria != "Todas":
            df_f = df_f[df_f["categoria"] == categoria]

        if meses_sel:
            df_f = df_f[df_f["mes_ref"].isin(meses_sel)]

        if df_f.empty:
            st.warning("Nenhum dado encontrado para os filtros selecionados.")
            st.stop()

        total_pago_filtro = df_f["valor"].sum()
        total_pago_geral = df["valor"].sum()
        media_filtro = df_f["valor"].mean()
        qtd_lanc = len(df_f)
        maior_pag = df_f["valor"].max()
        restante = max(TOTAL_PREVISTO_MANUAL - total_pago_geral, 0)
        percentual = (total_pago_geral / TOTAL_PREVISTO_MANUAL * 100) if TOTAL_PREVISTO_MANUAL > 0 else 0

        st.markdown('<div class="section-title">Dashboard Financeiro</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Visão consolidada dos pagamentos do apartamento com foco em progresso, distribuição e acompanhamento por categoria.</div>',
            unsafe_allow_html=True
        )

        k1, k2, k3, k4 = st.columns(4)

        with k1:
            st.markdown(f"""
            <div class="tech-card">
                <div class="tech-label">Total pago</div>
                <div class="tech-value">{brl(total_pago_geral)}</div>
                <div class="tech-sub">Valor acumulado geral</div>
            </div>
            """, unsafe_allow_html=True)

        with k2:
            st.markdown(f"""
            <div class="tech-card">
                <div class="tech-label">Restante estimado</div>
                <div class="tech-value">{brl(restante)}</div>
                <div class="tech-sub">Com base no total previsto manual</div>
            </div>
            """, unsafe_allow_html=True)

        with k3:
            st.markdown(f"""
            <div class="tech-card">
                <div class="tech-label">Percentual concluído</div>
                <div class="tech-value">{percentual:.1f}%</div>
                <div class="tech-sub">Progresso financeiro do projeto</div>
            </div>
            """, unsafe_allow_html=True)

        with k4:
            st.markdown(f"""
            <div class="tech-card">
                <div class="tech-label">Lançamentos no filtro</div>
                <div class="tech-value">{qtd_lanc}</div>
                <div class="tech-sub">Média: {brl(media_filtro)}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")

        c1, c2 = st.columns([1.7, 1])

        with c1:
            with st.container(border=True):
                st.markdown("### 🚀 Progresso do projeto")
                st.progress(min(max(percentual / 100, 0), 1))
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Previsto", brl(TOTAL_PREVISTO_MANUAL))
                p2.metric("Pago geral", brl(total_pago_geral))
                p3.metric("Pago no filtro", brl(total_pago_filtro))
                p4.metric("Maior pagamento", brl(maior_pag))

        with c2:
            with st.container(border=True):
                st.markdown("### 🧠 Resumo rápido")
                st.metric("Categorias ativas", f"{df_f['categoria'].nunique()}")
                st.metric("Meses analisados", f"{len(meses_sel)}")
                st.markdown('<span class="metric-chip">Visão tecnológica</span>', unsafe_allow_html=True)

        por_mes = df_f.groupby("mes_ref", as_index=False)["valor"].sum()
        por_mes["mes_ord"] = pd.to_datetime(por_mes["mes_ref"], format="%m/%Y")
        por_mes = por_mes.sort_values("mes_ord")

        por_cat = (
            df_f.groupby("categoria", as_index=False)["valor"]
            .sum()
            .sort_values("valor", ascending=False)
        )

        resumo_cat = (
            df.groupby("categoria")
            .size()
            .reindex(CATEGORIAS, fill_value=0)
            .reset_index(name="qtd_paga")
            .rename(columns={"index": "categoria"})
        )
        resumo_cat["limite"] = resumo_cat["categoria"].map(LIMITES)
        resumo_cat["percentual"] = ((resumo_cat["qtd_paga"] / resumo_cat["limite"]) * 100).round(1)
        resumo_cat["status"] = resumo_cat["qtd_paga"].astype(str) + "/" + resumo_cat["limite"].astype(str)

        g1, g2 = st.columns([1.6, 1])

        with g1:
            with st.container(border=True):
                st.markdown("### 📈 Evolução mensal")
                fig1 = px.line(
                    por_mes,
                    x="mes_ord",
                    y="valor",
                    markers=True
                )
                fig1.update_traces(
                    line=dict(width=4, color="#38BDF8"),
                    marker=dict(size=9, color="#38BDF8")
                )
                fig1.update_layout(
                    template="plotly_dark",
                    height=360,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="",
                    yaxis_title="Valor (R$)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E5E7EB")
                )
                fig1.update_xaxes(tickformat="%m/%Y", showgrid=False)
                fig1.update_yaxes(gridcolor="rgba(148,163,184,0.18)")
                st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

        with g2:
            with st.container(border=True):
                st.markdown("### 🥯 Distribuição por categoria")
                fig2 = px.pie(
                    por_cat,
                    names="categoria",
                    values="valor",
                    hole=0.68,
                    color="categoria",
                    color_discrete_map=CORES_CATEGORIAS
                )
                fig2.update_layout(
                    template="plotly_dark",
                    height=360,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E5E7EB"),
                    legend_title_text=""
                )
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        g3, g4 = st.columns([1.6, 1])

        with g3:
            with st.container(border=True):
                st.markdown("### 🏁 Ranking por categoria")
                fig3 = px.bar(
                    por_cat,
                    x="valor",
                    y="categoria",
                    orientation="h",
                    text="valor",
                    color="categoria",
                    color_discrete_map=CORES_CATEGORIAS
                )
                fig3.update_traces(
                    texttemplate="R$ %{text:,.2f}",
                    textposition="outside"
                )
                fig3.update_layout(
                    template="plotly_dark",
                    height=360,
                    margin=dict(l=10, r=20, t=10, b=10),
                    xaxis_title="Valor (R$)",
                    yaxis_title="",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E5E7EB"),
                    showlegend=False,
                    yaxis={"categoryorder": "total ascending"}
                )
                fig3.update_xaxes(gridcolor="rgba(148,163,184,0.18)")
                fig3.update_yaxes(showgrid=False)
                st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

        with g4:
            with st.container(border=True):
                st.markdown("### 📦 Progresso por categoria")
                resumo_show = resumo_cat.copy()
                resumo_show = resumo_show[["categoria", "status", "percentual"]]
                resumo_show.columns = ["Categoria", "Pago", "% Concluído"]
                st.dataframe(
                    resumo_show,
                    use_container_width=True,
                    hide_index=True,
                    height=360
                )

        with st.container(border=True):
            st.markdown("### 🧾 Histórico filtrado")
            df_show = df_f.copy().sort_values("data_pagamento", ascending=False)
            df_show["data_pagamento"] = df_show["data_pagamento"].dt.strftime("%d/%m/%Y")
            df_show["valor"] = df_show["valor"].apply(brl)

            st.dataframe(
                df_show[["data_pagamento", "categoria", "valor"]],
                use_container_width=True,
                hide_index=True,
                height=280
            )

# ================== TAB 3: HISTÓRICO ==================
with tab3:
    st.subheader("Histórico")

    df = get_df()
    if df.empty:
        st.info("Sem lançamentos ainda.")
    else:
        df_show = df.copy()
        df_show["data_pagamento"] = df_show["data_pagamento"].dt.date
        df_show["valor"] = df_show["valor"].apply(lambda x: brl(float(x)))

        st.dataframe(
            df_show[["id", "data_pagamento", "categoria", "valor"]],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### 🗑️ Excluir lançamento por ID")
        del_id = st.number_input("ID", min_value=1, step=1)
        if st.button("Excluir", type="secondary"):
            supabase.table("pagamentos").delete().eq("id", int(del_id)).execute()
            st.success(f"Excluído ID {int(del_id)}.")
            st.rerun()