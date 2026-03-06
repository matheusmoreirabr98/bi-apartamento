import time
from datetime import datetime, date
import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Apartamento", layout="wide")
st.title("🏠 Apartamento")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

USUARIOS = {
    st.secrets["PASSWORD_ANA"]: "Ana Luiza",
    st.secrets["PASSWORD_MATHEUS"]: "Matheus Moreira",
}

USUARIO_PODE_EDITAR = "Matheus Moreira"

# =========================================================
# FUNÇÕES
# =========================================================

def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def now_iso():
    return datetime.utcnow().isoformat()

def load_parcelas():
    res = supabase.table("parcelas").select("*").is_("deleted_at", None).execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    df["vencimento"] = pd.to_datetime(df["vencimento"])
    return df


def load_pagamentos():
    res = supabase.table("pagamentos").select("*").is_("deleted_at", None).execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    df["data_pagamento"] = pd.to_datetime(df["data_pagamento"])
    return df


def load_pagamento_itens():
    res = supabase.table("pagamento_itens").select("*").is_("deleted_at", None).execute()
    df = pd.DataFrame(res.data)
    return df


def calcular_status(parcelas, itens):

    parcelas["paga"] = parcelas["id"].isin(itens["parcela_id"])

    hoje = pd.Timestamp.today()

    parcelas["status"] = "pendente"

    parcelas.loc[parcelas["paga"], "status"] = "paga"

    parcelas.loc[
        (~parcelas["paga"]) &
        (parcelas["vencimento"].dt.to_period("M") == hoje.to_period("M")),
        "status"
    ] = "a vencer"

    parcelas.loc[
        (~parcelas["paga"]) &
        (parcelas["vencimento"] < hoje),
        "status"
    ] = "atrasada"

    return parcelas


# =========================================================
# LOGIN
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_name" not in st.session_state:
    st.session_state.user_name = None

if not st.session_state.logged_in:

    pw = st.text_input("Senha", type="password")

    if st.button("Entrar"):

        user = USUARIOS.get(pw)

        if user:
            st.session_state.logged_in = True
            st.session_state.user_name = user
            st.rerun()

        else:
            st.error("Senha incorreta")

    st.stop()

usuario_logado = st.session_state.user_name
pode_editar = usuario_logado == USUARIO_PODE_EDITAR

st.caption(f"Usuário logado: **{usuario_logado}**")

if st.button("Sair"):
    st.session_state.logged_in = False
    st.session_state.user_name = None
    st.rerun()

# =========================================================
# LOAD DATA
# =========================================================

parcelas = load_parcelas()
pagamentos = load_pagamentos()
itens = load_pagamento_itens()

parcelas = calcular_status(parcelas, itens)

# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3 = st.tabs(["💳 Lançar Pagamento", "📊 Dashboard", "🧾 Histórico"])

# =========================================================
# TAB 1 — PAGAMENTO
# =========================================================

with tab1:

    st.subheader("Lançar pagamento")

    pendentes = parcelas[parcelas["status"] != "paga"].copy()

    pendentes["label"] = (
        pendentes["categoria_app"]
        + " | "
        + pendentes["descricao_parcela"]
        + " | vence "
        + pendentes["vencimento"].dt.strftime("%d/%m/%Y")
        + " | "
        + pendentes["valor_total_atual"].apply(brl)
    )

    parcelas_sel = st.multiselect(
        "Parcelas",
        pendentes["label"]
    )

    data_pag = st.date_input(
        "Data do pagamento",
        value=date.today(),
        format="DD/MM/YYYY"
    )

    if parcelas_sel:

        df_sel = pendentes[pendentes["label"].isin(parcelas_sel)]

        total = df_sel["valor_total_atual"].sum()

        st.metric("Total a pagar", brl(total))

    if st.button("Registrar pagamento"):

        if not parcelas_sel:
            st.error("Selecione ao menos uma parcela")
            st.stop()

        pagamento = supabase.table("pagamentos").insert({

            "data_pagamento": str(data_pag),
            "created_by": usuario_logado,
            "updated_by": usuario_logado

        }).execute()

        pagamento_id = pagamento.data[0]["id"]

        df_sel = pendentes[pendentes["label"].isin(parcelas_sel)]

        for _, r in df_sel.iterrows():

            desconto = r["valor_total_atual"] - r["valor_principal"]

            supabase.table("pagamento_itens").insert({

                "pagamento_id": pagamento_id,
                "parcela_id": int(r["id"]),
                "valor_pago": float(r["valor_total_atual"]),
                "valor_total_atual_na_data": float(r["valor_total_atual"]),
                "desconto_amortizacao": float(desconto),
                "created_by": usuario_logado,
                "updated_by": usuario_logado

            }).execute()

        st.success("Pagamento registrado!")

        time.sleep(1)
        st.rerun()

# =========================================================
# TAB 2 — DASHBOARD
# =========================================================

with tab2:

    st.subheader("Dashboard")

    total_pago = itens["valor_pago"].sum()

    total_amortizado = itens["desconto_amortizacao"].sum()

    parcelas_pagas = parcelas[parcelas["status"] == "paga"].shape[0]

    parcelas_pendentes = parcelas[parcelas["status"] != "paga"].shape[0]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total pago", brl(total_pago))
    c2.metric("Juros evitados", brl(total_amortizado))
    c3.metric("Parcelas pagas", parcelas_pagas)
    c4.metric("Parcelas pendentes", parcelas_pendentes)

    if not pagamentos.empty:

        pagamentos["mes"] = pagamentos["data_pagamento"].dt.to_period("M").astype(str)

        df_mes = itens.merge(pagamentos, left_on="pagamento_id", right_on="id")

        por_mes = df_mes.groupby("mes")["valor_pago"].sum().reset_index()

        fig = px.line(por_mes, x="mes", y="valor_pago", markers=True)

        st.plotly_chart(fig, use_container_width=True)

# =========================================================
# TAB 3 — HISTÓRICO
# =========================================================

with tab3:

    st.subheader("Histórico de pagamentos")

    if itens.empty:

        st.info("Nenhum pagamento registrado.")

    else:

        df_hist = itens.merge(
            parcelas,
            left_on="parcela_id",
            right_on="id"
        ).merge(
            pagamentos,
            left_on="pagamento_id",
            right_on="id"
        )

        df_hist["valor_pago_fmt"] = df_hist["valor_pago"].apply(brl)
        df_hist["amortizacao_fmt"] = df_hist["desconto_amortizacao"].apply(brl)

        df_hist["data_pagamento"] = pd.to_datetime(df_hist["data_pagamento"]).dt.date

        cols = [
            "data_pagamento",
            "categoria_app",
            "descricao_parcela",
            "valor_pago_fmt",
            "amortizacao_fmt",
        ]

        st.dataframe(
            df_hist[cols].rename(columns={
                "valor_pago_fmt": "valor pago",
                "amortizacao_fmt": "juros evitado"
            }),
            use_container_width=True,
            hide_index=True
        )