import time
from datetime import datetime, date

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Apartamento 2.1", layout="wide")
st.title("🏠 Apartamento 2.1")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

USUARIOS = {
    st.secrets["PASSWORD_ANA"]: "Ana Luiza",
    st.secrets["PASSWORD_MATHEUS"]: "Matheus Moreira",
}

USUARIO_PODE_EDITAR = "Matheus Moreira"

STATUS_ORDEM = {
    "a vencer": 1,
    "pendente": 2,
    "atrasada": 3,
    "paga": 4,
}

# =========================================================
# FUNÇÕES UTILITÁRIAS
# =========================================================

def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def now_iso():
    return datetime.utcnow().isoformat()


def to_df(res):
    df = pd.DataFrame(res.data)
    return df if not df.empty else pd.DataFrame()


def load_parcelas(include_deleted=False):
    try:
        q = supabase.table("parcelas").select("*")
        if not include_deleted:
            q = q.is_("deleted_at", None)

        res = q.execute()

        df = pd.DataFrame(res.data)
        if df.empty:
            return df

        df["vencimento"] = pd.to_datetime(df["vencimento"], errors="coerce")
        df["valor_principal"] = pd.to_numeric(df["valor_principal"], errors="coerce").fillna(0.0)
        df["valor_total_atual"] = pd.to_numeric(df["valor_total_atual"], errors="coerce").fillna(0.0)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar parcelas: {e}")
        return pd.DataFrame()


def load_pagamentos(include_deleted=False):
    try:
        q = supabase.table("pagamentos").select("*").order("data_pagamento", desc=True)
        if not include_deleted:
            q = q.is_("deleted_at", None)

        res = q.execute()

        df = pd.DataFrame(res.data)
        if df.empty:
            return df

        df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce")
        return df
    except Exception as e:
        st.error(f"Erro ao carregar pagamentos: {e}")
        return pd.DataFrame()


def load_pagamento_itens(include_deleted=False):
    try:
        q = supabase.table("pagamento_itens").select("*")
        if not include_deleted:
            q = q.is_("deleted_at", None)

        res = q.execute()

        df = pd.DataFrame(res.data)
        if df.empty:
            return df

        df["valor_pago"] = pd.to_numeric(df["valor_pago"], errors="coerce").fillna(0.0)
        df["valor_total_atual_na_data"] = pd.to_numeric(
            df["valor_total_atual_na_data"], errors="coerce"
        ).fillna(0.0)
        df["desconto_amortizacao"] = pd.to_numeric(
            df["desconto_amortizacao"], errors="coerce"
        ).fillna(0.0)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar itens: {e}")
        return pd.DataFrame()


def calcular_status(parcelas_df, itens_df):
    df = parcelas_df.copy()

    if df.empty:
        return df

    paid_ids = set(itens_df["parcela_id"].tolist()) if not itens_df.empty else set()
    hoje = pd.Timestamp.today().normalize()
    mes_atual = hoje.to_period("M")

    df["paga"] = df["id"].isin(paid_ids)
    df["status"] = "pendente"

    df.loc[df["paga"], "status"] = "paga"
    df.loc[
        (~df["paga"]) & (df["vencimento"].dt.to_period("M") == mes_atual),
        "status",
    ] = "a vencer"
    df.loc[
        (~df["paga"]) & (df["vencimento"] < hoje),
        "status",
    ] = "atrasada"

    df["status_ordem"] = df["status"].map(STATUS_ORDEM).fillna(999)
    return df


def montar_base(parcelas_df, pagamentos_df, itens_df):
    if parcelas_df.empty:
        return pd.DataFrame()

    if itens_df.empty:
        base = parcelas_df.copy()
        base["data_pagamento"] = pd.NaT
        base["observacao"] = None
        base["valor_pago"] = None
        base["desconto_amortizacao"] = None
        base["pagamento_id"] = None
        base["parcela_id"] = base["id"]
        return base

    itens_x = itens_df.rename(columns={"id": "pagamento_item_id"})
    pag_x = pagamentos_df.rename(columns={"id": "pagamento_id"})
    parc_x = parcelas_df.rename(columns={"id": "parcela_id"})

    base = (
        parc_x.merge(itens_x, on="parcela_id", how="left", suffixes=("", "_item"))
        .merge(pag_x, on="pagamento_id", how="left", suffixes=("", "_pag"))
    )

    return base


def get_multiselect_key():
    if "multiselect_version" not in st.session_state:
        st.session_state.multiselect_version = 0
    return f"parcelas_multiselect_{st.session_state.multiselect_version}"


def reset_multiselect():
    st.session_state.multiselect_version += 1


# =========================================================
# LOGIN
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_name" not in st.session_state:
    st.session_state.user_name = None

if not st.session_state.logged_in:
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        user = USUARIOS.get(senha)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_name = user
            st.rerun()
        else:
            st.error("Senha incorreta")

    st.stop()

usuario_logado = st.session_state.user_name
pode_editar = usuario_logado == USUARIO_PODE_EDITAR

top_c1, top_c2 = st.columns([3, 1])
with top_c1:
    st.caption(f"Usuário logado: **{usuario_logado}**")
with top_c2:
    if st.button("Sair"):
        st.session_state.logged_in = False
        st.session_state.user_name = None
        st.rerun()

# =========================================================
# CARGA DE DADOS
# =========================================================

parcelas = load_parcelas()
pagamentos = load_pagamentos()
itens = load_pagamento_itens()

parcelas = calcular_status(parcelas, itens)
base = montar_base(parcelas, pagamentos, itens)

# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["💳 Lançar Pagamento", "📊 Dashboard", "📁 Parcelas", "🧾 Histórico", "🛠 Atualizar Parcelas"]
)

# =========================================================
# TAB 1 — LANÇAR PAGAMENTO
# =========================================================

with tab1:
    st.subheader("Lançar pagamento")

    if parcelas.empty:
        st.info("Não há parcelas cadastradas.")
    else:
        pendentes = parcelas[parcelas["status"] != "paga"].copy()

        if pendentes.empty:
            st.success("✅ Todas as parcelas estão pagas.")
        else:
            pendentes = pendentes.sort_values(
                ["status_ordem", "vencimento", "categoria_app", "numero_parcela"]
            ).copy()

            pendentes["label"] = (
                pendentes["categoria_app"]
                + " | "
                + pendentes["descricao_parcela"]
                + " | "
                + pendentes["status"].str.upper()
                + " | vence "
                + pendentes["vencimento"].dt.strftime("%d/%m/%Y")
                + " | atual "
                + pendentes["valor_total_atual"].apply(brl)
            )

            st.markdown("### Seleção rápida")
            r1, r2, r3 = st.columns(3)

            with r1:
                if st.button("Selecionar parcelas a vencer"):
                    st.session_state.parcelas_preselecionadas = pendentes.loc[
                        pendentes["status"] == "a vencer", "label"
                    ].tolist()
                    reset_multiselect()
                    st.rerun()

            with r2:
                if st.button("Selecionar parcelas atrasadas"):
                    st.session_state.parcelas_preselecionadas = pendentes.loc[
                        pendentes["status"] == "atrasada", "label"
                    ].tolist()
                    reset_multiselect()
                    st.rerun()

            with r3:
                if st.button("Limpar seleção"):
                    st.session_state.parcelas_preselecionadas = []
                    reset_multiselect()
                    st.rerun()

            default_sel = st.session_state.get("parcelas_preselecionadas", [])
            key_multi = get_multiselect_key()

            parcelas_sel = st.multiselect(
                "Parcelas para pagar",
                options=pendentes["label"].tolist(),
                default=default_sel,
                key=key_multi,
            )

            data_pag = st.date_input(
                "Data do pagamento",
                value=date.today(),
                format="DD/MM/YYYY",
                key="data_pagamento_form",
            )

            observacao = st.text_input(
                "Observação (opcional)",
                placeholder="Ex.: pagamento do mês, antecipação, etc.",
            )

            if parcelas_sel:
                df_sel = pendentes[pendentes["label"].isin(parcelas_sel)].copy()
                df_sel["juros_ev"] = df_sel["valor_total_atual"] - df_sel["valor_principal"]

                st.markdown("### Resumo do pagamento")
                k1, k2, k3 = st.columns(3)
                k1.metric("Parcelas selecionadas", len(df_sel))
                k2.metric("Total a pagar hoje", brl(df_sel["valor_total_atual"].sum()))
                k3.metric("Juros evitados", brl(df_sel["juros_ev"].sum()))

                show_sel = df_sel[
                    [
                        "categoria_app",
                        "descricao_parcela",
                        "status",
                        "vencimento",
                        "valor_principal",
                        "valor_total_atual",
                        "juros_ev",
                    ]
                ].copy()
                show_sel["vencimento"] = show_sel["vencimento"].dt.date
                show_sel["valor_principal"] = show_sel["valor_principal"].apply(brl)
                show_sel["valor_total_atual"] = show_sel["valor_total_atual"].apply(brl)
                show_sel["juros_ev"] = show_sel["juros_ev"].apply(brl)

                st.dataframe(show_sel, use_container_width=True, hide_index=True)

            if st.button("Registrar pagamento", type="primary"):
                if not parcelas_sel:
                    st.error("Selecione ao menos uma parcela.")
                else:
                    df_sel = pendentes[pendentes["label"].isin(parcelas_sel)].copy()

                    res_pag = supabase.table("pagamentos").insert(
                        {
                            "data_pagamento": str(data_pag),
                            "observacao": observacao if observacao else None,
                            "created_by": usuario_logado,
                            "updated_by": usuario_logado,
                        }
                    ).execute()

                    pagamento_id = res_pag.data[0]["id"]

                    for _, r in df_sel.iterrows():
                        desconto = float(r["valor_total_atual"] - r["valor_principal"])

                        supabase.table("pagamento_itens").insert(
                            {
                                "pagamento_id": int(pagamento_id),
                                "parcela_id": int(r["id"]),
                                "valor_pago": float(r["valor_total_atual"]),
                                "valor_total_atual_na_data": float(r["valor_total_atual"]),
                                "desconto_amortizacao": desconto,
                                "created_by": usuario_logado,
                                "updated_by": usuario_logado,
                            }
                        ).execute()

                    st.session_state.parcelas_preselecionadas = []
                    reset_multiselect()
                    st.success("✅ Pagamento registrado com sucesso!")
                    time.sleep(0.8)
                    st.rerun()

# =========================================================
# TAB 2 — DASHBOARD
# =========================================================

with tab2:
    st.subheader("Dashboard")

    if parcelas.empty:
        st.info("Sem dados para exibir.")
    else:
        total_parcelas = len(parcelas)
        total_pago_valor = itens["valor_pago"].sum() if not itens.empty else 0
        total_juros_ev = itens["desconto_amortizacao"].sum() if not itens.empty else 0
        total_em_aberto = parcelas.loc[parcelas["status"] != "paga", "valor_total_atual"].sum()
        total_pago_qtd = (parcelas["status"] == "paga").sum()
        total_pendente_qtd = (parcelas["status"] == "pendente").sum()
        total_avencer_qtd = (parcelas["status"] == "a vencer").sum()
        total_atrasada_qtd = (parcelas["status"] == "atrasada").sum()
        progresso_pct = (total_pago_qtd / total_parcelas * 100) if total_parcelas else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total pago", brl(total_pago_valor))
        k2.metric("Juros evitados", brl(total_juros_ev))
        k3.metric("Saldo em aberto", brl(total_em_aberto))
        k4.metric("Progresso", f"{progresso_pct:.1f}%")

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Parcelas pagas", int(total_pago_qtd))
        k6.metric("A vencer", int(total_avencer_qtd))
        k7.metric("Pendentes", int(total_pendente_qtd))
        k8.metric("Atrasadas", int(total_atrasada_qtd))

        st.progress(min(max(progresso_pct / 100, 0), 1.0))

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Situação das parcelas")
            status_df = (
                parcelas.groupby("status", as_index=False)
                .size()
                .rename(columns={"size": "quantidade"})
            )
            if not status_df.empty:
                fig_status = px.bar(status_df, x="status", y="quantidade")
                st.plotly_chart(fig_status, use_container_width=True)

        with c2:
            st.markdown("### Saldo em aberto por categoria")
            aberto_cat = (
                parcelas[parcelas["status"] != "paga"]
                .groupby("categoria_app", as_index=False)["valor_total_atual"]
                .sum()
                .sort_values("valor_total_atual", ascending=False)
            )
            if not aberto_cat.empty:
                fig_aberto = px.bar(aberto_cat, x="categoria_app", y="valor_total_atual")
                st.plotly_chart(fig_aberto, use_container_width=True)

        c3, c4 = st.columns(2)

        with c3:
            st.markdown("### Pago por mês")
            if not itens.empty and not pagamentos.empty:
                pag_mes = itens.merge(
                    pagamentos[["id", "data_pagamento"]],
                    left_on="pagamento_id",
                    right_on="id",
                    how="left",
                )
                pag_mes["mes"] = pd.to_datetime(pag_mes["data_pagamento"]).dt.to_period("M").astype(str)
                por_mes = pag_mes.groupby("mes", as_index=False)["valor_pago"].sum()
                fig_mes = px.line(por_mes, x="mes", y="valor_pago", markers=True)
                st.plotly_chart(fig_mes, use_container_width=True)
            else:
                st.info("Sem pagamentos suficientes para exibir.")

        with c4:
            st.markdown("### Juros evitados por categoria")
            if not base.empty:
                juros_cat = (
                    base[base["status"] == "paga"]
                    .groupby("categoria_app", as_index=False)["desconto_amortizacao"]
                    .sum()
                    .sort_values("desconto_amortizacao", ascending=False)
                )
                if not juros_cat.empty:
                    fig_juros = px.bar(juros_cat, x="categoria_app", y="desconto_amortizacao")
                    st.plotly_chart(fig_juros, use_container_width=True)
                else:
                    st.info("Sem dados para exibir.")

        st.markdown("### Próximas parcelas")
        proximas = (
            parcelas[parcelas["status"] != "paga"]
            .sort_values(["vencimento", "categoria_app", "numero_parcela"])
            .head(10)
            .copy()
        )
        if proximas.empty:
            st.info("Não há parcelas em aberto.")
        else:
            proximas["vencimento"] = proximas["vencimento"].dt.date
            proximas["valor_total_atual"] = proximas["valor_total_atual"].apply(brl)
            st.dataframe(
                proximas[
                    [
                        "categoria_app",
                        "descricao_parcela",
                        "status",
                        "vencimento",
                        "valor_total_atual",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

# =========================================================
# TAB 3 — PARCELAS
# =========================================================

with tab3:
    st.subheader("Parcelas")

    if parcelas.empty:
        st.info("Sem parcelas cadastradas.")
    else:
        f1, f2 = st.columns(2)

        with f1:
            categorias_disp = ["Todas"] + sorted(parcelas["categoria_app"].dropna().unique().tolist())
            categoria_filtro = st.selectbox("Categoria", categorias_disp)

        with f2:
            status_disp = ["Todos", "a vencer", "pendente", "atrasada", "paga"]
            status_filtro = st.selectbox("Status", status_disp)

        parc_f = parcelas.copy()

        if categoria_filtro != "Todas":
            parc_f = parc_f[parc_f["categoria_app"] == categoria_filtro]

        if status_filtro != "Todos":
            parc_f = parc_f[parc_f["status"] == status_filtro]

        parc_f = parc_f.sort_values(
            ["status_ordem", "vencimento", "categoria_app", "numero_parcela"]
        ).copy()

        parc_show = parc_f[
            [
                "categoria_app",
                "origem",
                "descricao_parcela",
                "numero_parcela",
                "total_parcelas",
                "vencimento",
                "valor_principal",
                "valor_total_atual",
                "status",
            ]
        ].copy()

        parc_show["vencimento"] = parc_show["vencimento"].dt.date
        parc_show["valor_principal"] = parc_show["valor_principal"].apply(brl)
        parc_show["valor_total_atual"] = parc_show["valor_total_atual"].apply(brl)

        st.dataframe(parc_show, use_container_width=True, hide_index=True)

        st.markdown("### Resumo por status")
        resumo_status = (
            parc_f.groupby("status", as_index=False)
            .agg(
                quantidade=("id", "count"),
                total_atual=("valor_total_atual", "sum"),
            )
            .sort_values("status")
        )
        if not resumo_status.empty:
            resumo_status["total_atual"] = resumo_status["total_atual"].apply(brl)
            st.dataframe(resumo_status, use_container_width=True, hide_index=True)

# =========================================================
# TAB 4 — HISTÓRICO
# =========================================================

with tab4:
    st.subheader("Histórico de pagamentos")

    if base.empty or itens.empty:
        st.info("Nenhum pagamento encontrado.")
    else:
        hist = base[base["status"] == "paga"].copy()

        hist["data_pagamento"] = pd.to_datetime(hist["data_pagamento"]).dt.date
        hist["vencimento"] = pd.to_datetime(hist["vencimento"]).dt.date
        hist["valor_pago_fmt"] = hist["valor_pago"].apply(brl)
        hist["desconto_fmt"] = hist["desconto_amortizacao"].apply(brl)
        hist["valor_total_atual_na_data_fmt"] = hist["valor_total_atual_na_data"].apply(brl)

        st.markdown("### Itens pagos")
        st.dataframe(
            hist[
                [
                    "pagamento_id",
                    "data_pagamento",
                    "categoria_app",
                    "descricao_parcela",
                    "vencimento",
                    "valor_total_atual_na_data_fmt",
                    "valor_pago_fmt",
                    "desconto_fmt",
                    "observacao",
                ]
            ].rename(
                columns={
                    "pagamento_id": "id pagamento",
                    "valor_total_atual_na_data_fmt": "valor tabela",
                    "valor_pago_fmt": "valor pago",
                    "desconto_fmt": "juros evitados",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Resumo por pagamento")
        resumo_pag = (
            hist.groupby(["pagamento_id", "data_pagamento", "observacao"], dropna=False, as_index=False)
            .agg(
                qtd_parcelas=("parcela_id", "count"),
                total_pago=("valor_pago", "sum"),
                juros_ev=("desconto_amortizacao", "sum"),
            )
            .sort_values(["data_pagamento", "pagamento_id"], ascending=[False, False])
        )

        resumo_show = resumo_pag.copy()
        resumo_show["total_pago"] = resumo_show["total_pago"].apply(brl)
        resumo_show["juros_ev"] = resumo_show["juros_ev"].apply(brl)

        st.dataframe(resumo_show, use_container_width=True, hide_index=True)

        if pode_editar and not resumo_pag.empty:
            st.markdown("---")
            st.subheader("Editar pagamento")

            pagamento_ids = resumo_pag["pagamento_id"].tolist()
            pagamento_id_sel = st.selectbox("Selecione o pagamento", pagamento_ids)

            pag_sel = pagamentos[pagamentos["id"] == pagamento_id_sel].iloc[0]

            with st.form("form_editar_pagamento"):
                nova_data = st.date_input(
                    "Data do pagamento",
                    value=pag_sel["data_pagamento"].date(),
                    format="DD/MM/YYYY",
                )
                nova_obs = st.text_input(
                    "Observação",
                    value=pag_sel["observacao"] if pd.notnull(pag_sel["observacao"]) else "",
                )
                salvar_pag = st.form_submit_button("Salvar alterações")

            if salvar_pag:
                supabase.table("pagamentos").update(
                    {
                        "data_pagamento": str(nova_data),
                        "observacao": nova_obs if nova_obs else None,
                        "updated_by": usuario_logado,
                        "updated_at": now_iso(),
                    }
                ).eq("id", int(pagamento_id_sel)).execute()

                st.success("✅ Pagamento atualizado.")
                time.sleep(0.8)
                st.rerun()

            st.markdown("---")
            st.subheader("Excluir pagamento")

            pagamento_id_del = st.selectbox(
                "Selecione o pagamento para excluir",
                pagamento_ids,
                key="pag_del",
            )

            if st.button("Excluir pagamento", type="secondary"):
                supabase.table("pagamento_itens").update(
                    {
                        "deleted_at": now_iso(),
                        "deleted_by": usuario_logado,
                        "updated_by": usuario_logado,
                        "updated_at": now_iso(),
                    }
                ).eq("pagamento_id", int(pagamento_id_del)).execute()

                supabase.table("pagamentos").update(
                    {
                        "deleted_at": now_iso(),
                        "deleted_by": usuario_logado,
                        "updated_by": usuario_logado,
                        "updated_at": now_iso(),
                    }
                ).eq("id", int(pagamento_id_del)).execute()

                st.success("✅ Pagamento excluído.")
                time.sleep(0.8)
                st.rerun()

        elif not pode_editar:
            st.markdown("---")
            st.info("Você tem permissão apenas para visualizar o histórico. Edição e exclusão estão disponíveis somente para Matheus Moreira.")

# =========================================================
# TAB 5 — ATUALIZAR PARCELAS
# =========================================================

with tab5:
    st.subheader("Atualizar parcelas")

    if not pode_editar:
        st.info("Somente Matheus Moreira pode atualizar parcelas.")
    elif parcelas.empty:
        st.info("Sem parcelas cadastradas.")
    else:
        u1, u2 = st.columns(2)

        with u1:
            categorias_upd = ["Todas"] + sorted(parcelas["categoria_app"].dropna().unique().tolist())
            categoria_upd = st.selectbox("Categoria", categorias_upd, key="upd_categoria")

        with u2:
            status_upd = ["Todos", "a vencer", "pendente", "atrasada", "paga"]
            status_upd_sel = st.selectbox("Status", status_upd, key="upd_status")

        parcelas_upd = parcelas.copy()

        if categoria_upd != "Todas":
            parcelas_upd = parcelas_upd[parcelas_upd["categoria_app"] == categoria_upd]

        if status_upd_sel != "Todos":
            parcelas_upd = parcelas_upd[parcelas_upd["status"] == status_upd_sel]

        parcelas_upd = parcelas_upd.sort_values(
            ["status_ordem", "vencimento", "categoria_app", "numero_parcela"]
        ).copy()

        if parcelas_upd.empty:
            st.info("Nenhuma parcela encontrada com esses filtros.")
        else:
            parcelas_upd["vencimento_edit"] = parcelas_upd["vencimento"].dt.date
            parcelas_upd["valor_total_atual"] = parcelas_upd["valor_total_atual"].round(2)

            edit_df = parcelas_upd[
                [
                    "id",
                    "categoria_app",
                    "descricao_parcela",
                    "status",
                    "vencimento_edit",
                    "valor_principal",
                    "valor_total_atual",
                ]
            ].rename(columns={"vencimento_edit": "vencimento"}).copy()

            edit_df["valor_principal"] = edit_df["valor_principal"].round(2)

            st.markdown("### Edite os campos abaixo e clique em salvar")
            edited = st.data_editor(
                edit_df,
                use_container_width=True,
                hide_index=True,
                disabled=["id", "categoria_app", "descricao_parcela", "status", "valor_principal"],
                column_config={
                    "id": st.column_config.NumberColumn("ID"),
                    "categoria_app": st.column_config.TextColumn("Categoria"),
                    "descricao_parcela": st.column_config.TextColumn("Parcela"),
                    "status": st.column_config.TextColumn("Status"),
                    "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                    "valor_principal": st.column_config.NumberColumn("Valor principal", format="%.2f"),
                    "valor_total_atual": st.column_config.NumberColumn("Valor atual", format="%.2f"),
                },
                key="editor_parcelas",
            )

            if st.button("Salvar alterações das parcelas", type="primary"):
                try:
                    original = edit_df.set_index("id")
                    novo = edited.set_index("id")

                    alteradas = 0

                    for parcela_id in novo.index:
                        row_old = original.loc[parcela_id]
                        row_new = novo.loc[parcela_id]

                        venc_old = pd.to_datetime(row_old["vencimento"]).date()
                        venc_new = pd.to_datetime(row_new["vencimento"]).date()

                        valor_old = round(float(row_old["valor_total_atual"]), 2)
                        valor_new = round(float(row_new["valor_total_atual"]), 2)

                        if venc_old != venc_new or valor_old != valor_new:
                            supabase.table("parcelas").update(
                                {
                                    "vencimento": str(venc_new),
                                    "valor_total_atual": valor_new,
                                    "updated_by": usuario_logado,
                                    "updated_at": now_iso(),
                                }
                            ).eq("id", int(parcela_id)).execute()
                            alteradas += 1

                    if alteradas == 0:
                        st.info("Nenhuma alteração detectada.")
                    else:
                        st.success(f"✅ {alteradas} parcela(s) atualizada(s) com sucesso!")
                        time.sleep(0.8)
                        st.rerun()

                except Exception as e:
                    st.error(f"Erro ao salvar alterações: {e}")