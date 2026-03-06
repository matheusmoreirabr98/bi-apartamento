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

# Senhas e usuários
USUARIOS = {
    st.secrets["PASSWORD_ANA"]: "Ana Luiza",
    st.secrets["PASSWORD_MATHEUS"]: "Matheus Moreira",
}

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


# =========================================================
# FUNÇÕES
# =========================================================
def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def now_iso():
    return datetime.utcnow().isoformat()


def get_df(include_deleted=False):
    query = supabase.table("pagamentos").select("*").order("data_pagamento")

    if not include_deleted:
        query = query.is_("deleted_at", None)

    res = query.execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    if "data_pagamento" in df.columns:
        df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce")

    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)

    if "data_pagamento" in df.columns:
        df["mes"] = df["data_pagamento"].dt.to_period("M").astype(str)

    return df


def get_categoria_options(df_base, categoria_atual=None):
    counts = {}
    if not df_base.empty and "categoria" in df_base.columns:
        counts = df_base["categoria"].value_counts().to_dict()

    opcoes = []
    label_to_cat = {}

    for c in CATEGORIAS:
        limite = LIMITES.get(c)
        atual = counts.get(c, 0)

        # Permite manter a categoria atual durante edição mesmo se já atingiu o limite
        if categoria_atual != c and limite is not None and atual >= limite:
            continue

        label = f"{c} ({atual}/{limite})" if limite is not None else c
        opcoes.append(label)
        label_to_cat[label] = c

    return opcoes, label_to_cat


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
        user_name = USUARIOS.get(pw)

        if user_name:
            st.session_state.logged_in = True
            st.session_state.user_name = user_name
            st.rerun()
        else:
            st.error("Senha incorreta")

    st.stop()

st.caption(f"Usuário logado: **{st.session_state.user_name}**")

if st.button("Sair"):
    st.session_state.logged_in = False
    st.session_state.user_name = None
    st.rerun()

usuario_logado = st.session_state.user_name

# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3 = st.tabs(["➕ Lançar", "📊 Dashboard", "🧾 Histórico / Editar"])


# =========================================================
# TAB 1: LANÇAR
# =========================================================
with tab1:
    st.subheader("Adicionar pagamento")

    with st.form("form_lancamento", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            d = st.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")

        with c2:
            df_tmp = get_df()
            opcoes, label_to_cat = get_categoria_options(df_tmp)

            if not opcoes:
                st.warning("✅ Todas as categorias com limite já foram concluídas.")
                st.stop()

            label_escolhido = st.selectbox("Categoria", [""] + opcoes, index=0)
            cat = None if label_escolhido == "" else label_to_cat[label_escolhido]

        with c3:
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0, value=0.0)

        submitted = st.form_submit_button("Salvar")

    if submitted:
        if cat is None or valor <= 0:
            st.error("Preencha a Categoria e um Valor maior que 0.")
        else:
            supabase.table("pagamentos").insert({
                "data_pagamento": str(d),
                "categoria": cat,
                "valor": float(valor),
                "created_by": usuario_logado,
                "updated_by": usuario_logado,
            }).execute()

            st.success("✅ Lançamento registrado!")
            time.sleep(0.8)
            st.rerun()


# =========================================================
# TAB 2: DASHBOARD
# =========================================================
with tab2:
    st.subheader("Dashboard")

    df = get_df()
    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
        anos = sorted(df["data_pagamento"].dt.year.dropna().unique().tolist())
        c1, c2 = st.columns([1, 2])

        with c1:
            ano = st.selectbox("Ano", ["Todos"] + [str(a) for a in anos])

        with c2:
            categoria = st.selectbox("Categoria", ["Todas"] + sorted(df["categoria"].dropna().unique().tolist()))

        df_f = df.copy()

        if ano != "Todos":
            df_f = df_f[df_f["data_pagamento"].dt.year == int(ano)]

        if categoria != "Todas":
            df_f = df_f[df_f["categoria"] == categoria]

        total = df_f["valor"].sum()
        por_mes = df_f.groupby("mes", as_index=False)["valor"].sum() if not df_f.empty else pd.DataFrame()
        por_cat = (
            df_f.groupby("categoria", as_index=False)["valor"]
            .sum()
            .sort_values("valor", ascending=False)
            if not df_f.empty else pd.DataFrame()
        )

        k1, k2, k3 = st.columns(3)
        k1.metric("Total pago (filtros)", brl(total))
        k2.metric("Média mensal (filtros)", brl(por_mes["valor"].mean() if not por_mes.empty else 0))
        k3.metric("Nº lançamentos", str(len(df_f)))

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### 📅 Total por mês")
            if not por_mes.empty:
                fig = px.line(por_mes, x="mes", y="valor", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados para exibir.")

        with c2:
            st.markdown("### 🧩 Total por categoria")
            if not por_cat.empty:
                fig2 = px.bar(por_cat, x="categoria", y="valor")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sem dados para exibir.")


# =========================================================
# TAB 3: HISTÓRICO / EDITAR / EXCLUIR
# =========================================================
with tab3:
    st.subheader("Histórico")

    df = get_df()

    if df.empty:
        st.info("Sem lançamentos ainda.")
    else:
        df_show = df.copy()
        df_show["data_pagamento"] = df_show["data_pagamento"].dt.date
        df_show["valor_fmt"] = df_show["valor"].apply(lambda x: brl(float(x)))

        cols_hist = ["id", "data_pagamento", "categoria", "valor_fmt", "created_by", "updated_by"]
        cols_hist = [c for c in cols_hist if c in df_show.columns]

        st.dataframe(
            df_show[cols_hist].rename(columns={"valor_fmt": "valor"}),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.subheader("Editar lançamento")

        ids = df["id"].tolist()
        registro_id = st.selectbox("Selecione o ID para editar", ids)

        registro = df[df["id"] == registro_id].iloc[0]

        df_sem_registro = df[df["id"] != registro_id].copy()
        opcoes_edit, label_to_cat_edit = get_categoria_options(df_sem_registro, categoria_atual=registro["categoria"])

        label_default = None
        for label, cat_nome in label_to_cat_edit.items():
            if cat_nome == registro["categoria"]:
                label_default = label
                break

        with st.form("form_edicao"):
            c1, c2, c3 = st.columns([1, 1, 1])

            with c1:
                data_edit = st.date_input(
                    "Data do pagamento",
                    value=registro["data_pagamento"].date() if pd.notnull(registro["data_pagamento"]) else date.today(),
                    format="DD/MM/YYYY",
                    key="edit_data"
                )

            with c2:
                label_escolhido_edit = st.selectbox(
                    "Categoria",
                    opcoes_edit,
                    index=opcoes_edit.index(label_default) if label_default in opcoes_edit else 0,
                    key="edit_cat"
                )
                categoria_edit = label_to_cat_edit[label_escolhido_edit]

            with c3:
                valor_edit = st.number_input(
                    "Valor (R$)",
                    min_value=0.0,
                    step=10.0,
                    value=float(registro["valor"]),
                    key="edit_valor"
                )

            salvar_edicao = st.form_submit_button("Salvar alterações")

        if salvar_edicao:
            if valor_edit <= 0:
                st.error("Informe um valor maior que 0.")
            else:
                supabase.table("pagamentos").update({
                    "data_pagamento": str(data_edit),
                    "categoria": categoria_edit,
                    "valor": float(valor_edit),
                    "updated_by": usuario_logado,
                }).eq("id", int(registro_id)).execute()

                st.success("✅ Registro atualizado com sucesso!")
                time.sleep(0.8)
                st.rerun()

        st.markdown("---")
        st.subheader("Excluir lançamento")

        del_id = st.selectbox("Selecione o ID para excluir", ids, key="delete_id")

        if st.button("Excluir", type="secondary"):
            supabase.table("pagamentos").update({
                "deleted_at": now_iso(),
                "deleted_by": usuario_logado,
                "updated_by": usuario_logado,
            }).eq("id", int(del_id)).execute()

            st.success(f"Lançamento {int(del_id)} removido.")
            time.sleep(0.8)
            st.rerun()