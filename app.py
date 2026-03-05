import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client
import plotly.express as px

# ====== Secrets (Streamlit Cloud / Local) ======
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CATEGORIAS = [
    "Sinal Ato",
    "Sinal",
    "Diferença",
    "Parc. Entrada Direcional (57x)",
    "ITBI e Registro (40x)",
    "Evolução de Obra",
    "Financiamento Caixa (420x)",
]

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

st.set_page_config(page_title="BI Apartamento", layout="wide")
st.title("🏠 BI do Apartamento")

pw = st.text_input("Senha", type="password")
if pw != st.secrets["APP_PASSWORD"]:
    st.stop()

tab1, tab2, tab3 = st.tabs(["➕ Lançar", "📊 Dashboard", "🧾 Histórico"])

# ================== TAB 1: LANÇAR ==================
with tab1:
    st.subheader("Adicionar pagamento")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        d = st.date_input("Data do pagamento", value=date.today())
    with c2:
        cat = st.selectbox("Categoria", CATEGORIAS)
    with c3:
        valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)

    obs = st.text_input("Observação (opcional)")

    if st.button("Salvar", type="primary"):
        if valor <= 0:
            st.error("Informe um valor maior que 0.")
        else:
            supabase.table("pagamentos").insert({
                "data_pagamento": str(d),
                "categoria": cat,
                "valor": float(valor),
                "observacao": obs
            }).execute()
            st.success("✅ Lançamento salvo!")

# ================== TAB 2: DASHBOARD ==================
with tab2:
    st.subheader("Dashboard")

    df = get_df()
    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
        # filtros
        anos = sorted(df["data_pagamento"].dt.year.unique().tolist())
        c1, c2 = st.columns([1, 2])
        with c1:
            ano = st.selectbox("Ano", ["Todos"] + [str(a) for a in anos])
        with c2:
            categoria = st.selectbox("Categoria", ["Todas"] + sorted(df["categoria"].unique().tolist()))

        df_f = df.copy()
        if ano != "Todos":
            df_f = df_f[df_f["data_pagamento"].dt.year == int(ano)]
        if categoria != "Todas":
            df_f = df_f[df_f["categoria"] == categoria]

        total = df_f["valor"].sum()
        por_mes = df_f.groupby("mes", as_index=False)["valor"].sum()
        por_cat = df_f.groupby("categoria", as_index=False)["valor"].sum().sort_values("valor", ascending=False)

        k1, k2, k3 = st.columns(3)
        k1.metric("Total pago (filtros)", brl(total))
        k2.metric("Média mensal (filtros)", brl(por_mes["valor"].mean() if not por_mes.empty else 0))
        k3.metric("Nº lançamentos", str(len(df_f)))

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### 📅 Total por mês")
            fig = px.line(por_mes, x="mes", y="valor", markers=True)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("### 🧩 Total por categoria")
            fig2 = px.bar(por_cat, x="categoria", y="valor")
            st.plotly_chart(fig2, use_container_width=True)

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
        st.dataframe(df_show[["id", "data_pagamento", "categoria", "valor", "observacao"]], use_container_width=True, hide_index=True)

        st.markdown("### 🗑️ Excluir lançamento por ID")
        del_id = st.number_input("ID", min_value=1, step=1)
        if st.button("Excluir", type="secondary"):
            supabase.table("pagamentos").delete().eq("id", int(del_id)).execute()
            st.success(f"Excluído ID {int(del_id)}. (Atualize a página)")