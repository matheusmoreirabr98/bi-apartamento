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
st.title("🏠Apartamento")
st.markdown("""
<style>
.stApp {
    background-color: #f3f4f6;
}

div[data-testid="stMetric"] {
    background-color: white;
    border: 1px solid #e5e7eb;
    padding: 16px;
    border-radius: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

div[data-testid="stDataFrame"] {
    background-color: white;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 6px;
}

div[data-baseweb="select"] > div {
    background-color: white;
    border-radius: 10px;
}

div[data-testid="stMultiSelect"] > div {
    background-color: white;
    border-radius: 10px;
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

# ====== Limites por categoria ======
LIMITES = {
    "Sinal Ato": 3,
    "Sinal": 3,
    "Diferença": 6,
    "Evolução de Obra": 28,
    "ITBI e Registro": 43,
    "Parc. Entrada Direcional": 57,
    "Financiamento Caixa": 420,
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


if "form_categoria" not in st.session_state:
    st.session_state.form_categoria = None

if "form_valor" not in st.session_state:
    st.session_state.form_valor = 0.0

if "form_obs" not in st.session_state:
    st.session_state.form_obs = ""

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
        # estado do input com máscara
        if "valor_digits" not in st.session_state:
            st.session_state.valor_digits = ""
        if "valor_mask" not in st.session_state:
            st.session_state.valor_mask = ""
    
        def on_valor_change():
            s = st.session_state.valor_mask
            digits = "".join(ch for ch in s if ch.isdigit())
            st.session_state.valor_digits = digits
            v = (int(digits) / 100) if digits else 0.0
            st.session_state.valor_mask = brl(v)

        st.text_input(
            "Valor",
            key="valor_mask",
            on_change=on_valor_change,
            placeholder="0,00"
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

            # limpa o campo depois de salvar
            st.session_state.valor_digits = ""
            st.session_state.valor_mask = ""

            st.success("✅ Lançamento registrado!")
            time.sleep(0.8)
            st.rerun()


# ================== TAB 2: DASHBOARD ==================
with tab2:
    st.subheader("📊 Dashboard Financeiro")

    df = get_df()
    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
        anos = sorted(df["data_pagamento"].dt.year.unique().tolist())

        # ===== FILTROS =====
        filtro1, filtro2, filtro3 = st.columns([1, 1, 2])

        with filtro1:
            ano = st.selectbox("Ano", ["Todos"] + [str(a) for a in anos])

        with filtro2:
            categoria = st.selectbox("Categoria", ["Todas"] + sorted(df["categoria"].unique().tolist()))

        with filtro3:
            meses = sorted(df["mes"].unique().tolist())
            meses_sel = st.multiselect("Meses", meses, default=meses)

        df_f = df.copy()

        if ano != "Todos":
            df_f = df_f[df_f["data_pagamento"].dt.year == int(ano)]

        if categoria != "Todas":
            df_f = df_f[df_f["categoria"] == categoria]

        if meses_sel:
            df_f = df_f[df_f["mes"].isin(meses_sel)]

        total = df_f["valor"].sum()
        media = df_f["valor"].mean() if not df_f.empty else 0
        qtd = len(df_f)
        maior = df_f["valor"].max() if not df_f.empty else 0

        # ===== KPIs =====
        st.markdown("### Indicadores")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Pago", brl(total))
        k2.metric("Média por Lançamento", brl(media))
        k3.metric("Nº de Lançamentos", qtd)
        k4.metric("Maior Pagamento", brl(maior))

        por_mes = (
            df_f.groupby("mes", as_index=False)["valor"]
            .sum()
            .sort_values("mes")
        )

        por_cat = (
            df_f.groupby("categoria", as_index=False)["valor"]
            .sum()
            .sort_values("valor", ascending=False)
        )

        # ===== GRÁFICOS 1 =====
        g1, g2 = st.columns(2)

        with g1:
            st.markdown("### Evolução mensal")
            fig1 = px.area(
                por_mes,
                x="mes",
                y="valor",
                markers=True
            )
            fig1.update_layout(
                template="plotly_white",
                height=420,
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_title="Mês",
                yaxis_title="Valor (R$)"
            )
            st.plotly_chart(fig1, use_container_width=True)

        with g2:
            st.markdown("### Total por categoria")
            fig2 = px.bar(
                por_cat,
                x="valor",
                y="categoria",
                orientation="h",
                text="valor"
            )
            fig2.update_traces(
                texttemplate="R$ %{text:,.2f}",
                textposition="outside"
            )
            fig2.update_layout(
                template="plotly_white",
                height=420,
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_title="Valor (R$)",
                yaxis_title="Categoria",
                yaxis={"categoryorder": "total ascending"}
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ===== GRÁFICOS 2 =====
        g3, g4 = st.columns(2)

        with g3:
            st.markdown("### Participação por categoria")
            fig3 = px.pie(
                por_cat,
                names="categoria",
                values="valor",
                hole=0.55
            )
            fig3.update_layout(
                template="plotly_white",
                height=420,
                margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig3, use_container_width=True)

        with g4:
            st.markdown("### Histórico filtrado")
            df_show = df_f.copy().sort_values("data_pagamento", ascending=False)
            df_show["data_pagamento"] = df_show["data_pagamento"].dt.strftime("%d/%m/%Y")
            df_show["valor"] = df_show["valor"].apply(brl)

            st.dataframe(
                df_show[["data_pagamento", "categoria", "valor"]],
                use_container_width=True,
                hide_index=True,
                height=420
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
            st.success(f"Excluído ID {int(del_id)}. (Atualize a página)")
            st.rerun()