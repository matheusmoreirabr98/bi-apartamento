import time
import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client
import plotly.express as px

# ✅ TEM QUE SER O PRIMEIRO COMANDO STREAMLIT
st.set_page_config(page_title="Apartamento", layout="wide")
st.title("🏠 Apartamento")

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

    with st.form("form_lancamento", clear_on_submit=True):
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
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0, value=0.0)

        obs = st.text_input("Observação (opcional)", value="")

        submitted = st.form_submit_button("Salvar")

    if submitted:
        if cat is None or valor <= 0:
            st.error("Preencha a Categoria e um Valor maior que 0.")
        else:
            supabase.table("pagamentos").insert({
                "data_pagamento": str(d),
                "categoria": cat,
                "valor": float(valor),
                "observacao": obs
            }).execute()

            st.success("✅ Lançamento registrado!")
            time.sleep(0.8)
            st.rerun()

# ================== TAB 2: DASHBOARD ==================
with tab2:
    st.subheader("Dashboard")

    st.sidebar.title("Filtros")

    df = get_df()
    anos = sorted(df["data_pagamento"].dt.year.unique().tolist()) if not df.empty else []

    ano = st.sidebar.selectbox("Ano", ["Todos"] + [str(a) for a in anos])
    categoria = st.sidebar.selectbox("Categoria", ["Todas"] + (sorted(df["categoria"].unique().tolist()) if not df.empty else []))

    st.markdown("### Progresso por categoria")

    for cat, limite in LIMITES.items():
        atual = counts.get(cat, 0)
        prog = min(atual / limite, 1.0)
        st.write(f"**{cat}** — {atual}/{limite}")
        st.progress(prog)


    df = get_df()
    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
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

        st.dataframe(
            df_show[["id", "data_pagamento", "categoria", "valor", "observacao"]],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### 🗑️ Excluir lançamento por ID")
        del_id = st.number_input("ID", min_value=1, step=1)
        if st.button("Excluir", type="secondary"):
            supabase.table("pagamentos").delete().eq("id", int(del_id)).execute()
            st.success(f"Excluído ID {int(del_id)}. (Atualize a página)")
            st.rerun()