import time
from datetime import datetime, date

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Apartamento 3.0", layout="wide")
st.title("🏠 Apartamento 3.0")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

USUARIOS = {
    st.secrets["PASSWORD_ANA"]: "Ana Luiza",
    st.secrets["PASSWORD_MATHEUS"]: "Matheus Moreira",
}

USUARIO_PODE_EDITAR = "Matheus Moreira"

STATUS_ORDEM = {
    "pendente": 1,
    "atrasado": 2,
    "pago": 3,
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


def load_parcelas():
    try:
        res = supabase.table("parcelas").select("*").order("numero_parcela").execute()
        df = pd.DataFrame(res.data)

        if df.empty:
            return df

        if "data_vencimento" in df.columns:
            df["data_vencimento"] = pd.to_datetime(df["data_vencimento"], errors="coerce")

        if "data_pagamento" in df.columns:
            df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce")

        for col in ["valor_principal", "valor_total", "valor_pago"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        for col in [
            "contrato",
            "categoria",
            "origem",
            "descricao_parcela",
            "status",
            "responsavel_pagamento",
        ]:
            if col not in df.columns:
                df[col] = None

        return df

    except Exception as e:
        st.error(f"Erro ao carregar parcelas: {e}")
        return pd.DataFrame()


def normalizar_status(df):
    if df.empty:
        return df

    hoje = pd.Timestamp.today().normalize()

    df = df.copy()
    df["status_exibicao"] = df["status"].fillna("pendente")

    nao_pago = df["status_exibicao"] != "pago"

    df.loc[
        nao_pago & (df["data_vencimento"] < hoje),
        "status_exibicao",
    ] = "atrasado"

    df.loc[
        nao_pago & (df["data_vencimento"] >= hoje),
        "status_exibicao",
    ] = "pendente"

    df["status_ordem"] = df["status_exibicao"].map(STATUS_ORDEM).fillna(999)
    return df


def filtrar_contrato(df, contrato):
    if df.empty:
        return df
    return df[df["contrato"] == contrato].copy()


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
parcelas = normalizar_status(parcelas)

if parcelas.empty:
    st.warning("Nenhuma parcela encontrada na tabela `parcelas`.")

contratos_disponiveis = []
if not parcelas.empty and "contrato" in parcelas.columns:
    contratos_disponiveis = sorted(parcelas["contrato"].dropna().unique().tolist())

contrato_padrao = "Taxas Cartoriais" if "Taxas Cartoriais" in contratos_disponiveis else (
    contratos_disponiveis[0] if contratos_disponiveis else None
)

contrato_selecionado = st.selectbox(
    "Selecione o contrato",
    options=contratos_disponiveis if contratos_disponiveis else ["Sem dados"],
    index=contratos_disponiveis.index(contrato_padrao) if contrato_padrao in contratos_disponiveis else 0,
)

if contrato_selecionado == "Sem dados":
    st.stop()

parcelas_contrato = filtrar_contrato(parcelas, contrato_selecionado)

# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Dashboard", "📁 Parcelas", "💸 Registrar / Editar Pagamento", "🛠 Atualizar Parcelas"]
)

# =========================================================
# TAB 1 — DASHBOARD
# =========================================================

with tab1:
    st.subheader(f"Dashboard — {contrato_selecionado}")

    if parcelas_contrato.empty:
        st.info("Sem dados para exibir.")
    else:
        total_pago_geral = parcelas_contrato.loc[
            parcelas_contrato["status"] == "pago", "valor_pago"
        ].sum()

        total_pago_compradores = parcelas_contrato.loc[
            (parcelas_contrato["status"] == "pago")
            & (parcelas_contrato["responsavel_pagamento"] == "Compradores"),
            "valor_pago",
        ].sum()

        total_pago_corretora = parcelas_contrato.loc[
            (parcelas_contrato["status"] == "pago")
            & (parcelas_contrato["responsavel_pagamento"] == "Corretora"),
            "valor_pago",
        ].sum()

        total_restante = parcelas_contrato.loc[
            parcelas_contrato["status"] != "pago", "valor_total"
        ].sum()

        total_geral = parcelas_contrato["valor_total"].sum()

        total_pago_qtd = (parcelas_contrato["status"] == "pago").sum()
        total_pendente_qtd = (parcelas_contrato["status_exibicao"] == "pendente").sum()
        total_atrasado_qtd = (parcelas_contrato["status_exibicao"] == "atrasado").sum()

        progresso_pct = (total_pago_geral / total_geral * 100) if total_geral else 0

        juros_futuros = (
            parcelas_contrato.loc[parcelas_contrato["status"] != "pago", "valor_total"]
            - parcelas_contrato.loc[parcelas_contrato["status"] != "pago", "valor_principal"]
        ).sum()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total pago geral", brl(total_pago_geral))
        k2.metric("Total pago compradores", brl(total_pago_compradores))
        k3.metric("Total pago corretora", brl(total_pago_corretora))
        k4.metric("Total geral", brl(total_geral))

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Progresso", f"{progresso_pct:.1f}%")
        k6.metric("Parcelas pagas", int(total_pago_qtd))
        k7.metric("Pendentes", int(total_pendente_qtd))
        k8.metric("Atrasadas", int(total_atrasado_qtd))

        k9, k10 = st.columns(2)
        k9.metric("Total restante", brl(total_restante))
        k10.metric("Juros futuros embutidos", brl(juros_futuros))

        st.progress(min(max(progresso_pct / 100, 0), 1.0))

        st.markdown("### Próxima parcela a pagar")

        proxima_parcela = (
            parcelas_contrato[parcelas_contrato["status"] != "pago"]
            .sort_values(["data_vencimento", "numero_parcela"])
            .head(1)
            .copy()
        )

        if proxima_parcela.empty:
            st.success("✅ Não há parcelas em aberto.")
        else:
            prox = proxima_parcela.iloc[0]

            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Parcela", f'{int(prox["numero_parcela"])}/{int(prox["total_parcelas"])}')
            p2.metric("Descrição", prox["descricao_parcela"])
            p3.metric(
                "Vencimento",
                prox["data_vencimento"].strftime("%d/%m/%Y")
                if pd.notnull(prox["data_vencimento"])
                else "-",
            )
            p4.metric("Valor", brl(prox["valor_total"]))

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Situação das parcelas")
            situacao_df = parcelas_contrato.copy()
            situacao_df["situacao_grafico"] = situacao_df["status"].apply(
                lambda x: "Pago" if x == "pago" else "Pendente"
            )

            status_df = (
                situacao_df.groupby("situacao_grafico", as_index=False)
                .size()
                .rename(columns={"size": "quantidade"})
            )

            if not status_df.empty:
                fig_status = px.bar(status_df, x="situacao_grafico", y="quantidade")
                st.plotly_chart(fig_status, use_container_width=True)

        with c2:
            st.markdown("### Total pago por responsável")
            resp_df = (
                parcelas_contrato[parcelas_contrato["status"] == "pago"]
                .groupby("responsavel_pagamento", as_index=False)["valor_pago"]
                .sum()
                .sort_values("valor_pago", ascending=False)
            )

            if not resp_df.empty:
                fig_resp = px.pie(resp_df, names="responsavel_pagamento", values="valor_pago")
                st.plotly_chart(fig_resp, use_container_width=True)

        c3, c4 = st.columns(2)

        with c3:
            st.markdown("### Pago por responsável")
            pago_resp = (
                parcelas_contrato[parcelas_contrato["status"] == "pago"]
                .groupby("responsavel_pagamento", as_index=False)["valor_pago"]
                .sum()
                .sort_values("valor_pago", ascending=False)
            )
            if not pago_resp.empty:
                fig_pago_resp = px.bar(pago_resp, x="responsavel_pagamento", y="valor_pago")
                st.plotly_chart(fig_pago_resp, use_container_width=True)

        with c4:
            st.markdown("### Saldo em aberto por categoria")
            aberto_cat = (
                parcelas_contrato[parcelas_contrato["status"] != "pago"]
                .groupby("categoria", as_index=False)["valor_total"]
                .sum()
                .sort_values("valor_total", ascending=False)
            )
            if not aberto_cat.empty:
                fig_aberto = px.bar(aberto_cat, x="categoria", y="valor_total")
                st.plotly_chart(fig_aberto, use_container_width=True)

        st.markdown("### Próximas parcelas")
        proximas = (
            parcelas_contrato[parcelas_contrato["status"] != "pago"]
            .sort_values(["data_vencimento", "numero_parcela"])
            .head(10)
            .copy()
        )

        if proximas.empty:
            st.success("✅ Não há parcelas em aberto.")
        else:
            proximas_show = proximas[
                [
                    "categoria",
                    "descricao_parcela",
                    "numero_parcela",
                    "total_parcelas",
                    "data_vencimento",
                    "valor_principal",
                    "valor_total",
                    "status_exibicao",
                    "responsavel_pagamento",
                ]
            ].copy()

            proximas_show["data_vencimento"] = pd.to_datetime(
                proximas_show["data_vencimento"]
            ).dt.date
            proximas_show["valor_principal"] = proximas_show["valor_principal"].apply(brl)
            proximas_show["valor_total"] = proximas_show["valor_total"].apply(brl)

            st.dataframe(proximas_show, use_container_width=True, hide_index=True)

# =========================================================
# TAB 2 — PARCELAS
# =========================================================

with tab2:
    st.subheader(f"Parcelas — {contrato_selecionado}")

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
    else:
        f1, f2, f3 = st.columns(3)

        with f1:
            categorias_disp = ["Todas"] + sorted(
                parcelas_contrato["categoria"].dropna().unique().tolist()
            )
            categoria_filtro = st.selectbox("Categoria", categorias_disp)

        with f2:
            status_disp = ["Todos", "pendente", "atrasado", "pago"]
            status_filtro = st.selectbox("Status", status_disp)

        with f3:
            resp_disp = ["Todos"] + sorted(
                parcelas_contrato["responsavel_pagamento"].dropna().unique().tolist()
            )
            resp_filtro = st.selectbox("Responsável", resp_disp)

        parc_f = parcelas_contrato.copy()

        if categoria_filtro != "Todas":
            parc_f = parc_f[parc_f["categoria"] == categoria_filtro]

        if status_filtro != "Todos":
            parc_f = parc_f[parc_f["status_exibicao"] == status_filtro]

        if resp_filtro != "Todos":
            parc_f = parc_f[parc_f["responsavel_pagamento"] == resp_filtro]

        parc_f = parc_f.sort_values(
            ["status_ordem", "data_vencimento", "numero_parcela"]
        ).copy()

        parc_show = parc_f[
            [
                "origem",
                "categoria",
                "descricao_parcela",
                "numero_parcela",
                "total_parcelas",
                "data_vencimento",
                "data_pagamento",
                "valor_principal",
                "valor_total",
                "valor_pago",
                "status_exibicao",
                "responsavel_pagamento",
            ]
        ].copy()

        parc_show["data_vencimento"] = pd.to_datetime(parc_show["data_vencimento"]).dt.date
        parc_show["data_pagamento"] = pd.to_datetime(
            parc_show["data_pagamento"], errors="coerce"
        ).dt.date
        parc_show["valor_principal"] = parc_show["valor_principal"].apply(brl)
        parc_show["valor_total"] = parc_show["valor_total"].apply(brl)
        parc_show["valor_pago"] = parc_show["valor_pago"].apply(brl)

        st.dataframe(parc_show, use_container_width=True, hide_index=True)

        st.markdown("### Resumo por status")
        resumo_status = (
            parc_f.groupby("status_exibicao", as_index=False)
            .agg(
                quantidade=("id", "count"),
                total=("valor_total", "sum"),
            )
            .sort_values("status_exibicao")
        )
        if not resumo_status.empty:
            resumo_status["total"] = resumo_status["total"].apply(brl)
            st.dataframe(resumo_status, use_container_width=True, hide_index=True)

# =========================================================
# TAB 3 — REGISTRAR / EDITAR PAGAMENTO
# =========================================================

with tab3:
    st.subheader(f"Registrar / Editar Pagamento — {contrato_selecionado}")

    if not pode_editar:
        st.info("Somente Matheus Moreira pode editar pagamentos.")
    elif parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
    else:
        pendentes = parcelas_contrato[parcelas_contrato["status"] != "pago"].copy()

        st.markdown("### Marcar parcela como paga")

        if pendentes.empty:
            st.success("✅ Todas as parcelas desse contrato já estão pagas.")
        else:
            pendentes = pendentes.sort_values(["data_vencimento", "numero_parcela"]).copy()

            pendentes["label"] = (
                pendentes["descricao_parcela"]
                + " | "
                + pendentes["numero_parcela"].astype(str)
                + "/"
                + pendentes["total_parcelas"].astype(str)
                + " | vence "
                + pendentes["data_vencimento"].dt.strftime("%d/%m/%Y")
                + " | total "
                + pendentes["valor_total"].apply(brl)
            )

            parcela_label = st.selectbox("Selecione a parcela", pendentes["label"].tolist())
            parcela_sel = pendentes[pendentes["label"] == parcela_label].iloc[0]

            c1, c2, c3 = st.columns(3)
            with c1:
                data_pagamento = st.date_input(
                    "Data do pagamento",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    key="novo_pagamento_data",
                )
            with c2:
                valor_pago = st.number_input(
                    "Valor pago",
                    min_value=0.0,
                    value=float(parcela_sel["valor_total"]),
                    step=0.01,
                    format="%.2f",
                    key="novo_pagamento_valor",
                )
            with c3:
                responsavel_pagamento = st.selectbox(
                    "Responsável pelo pagamento",
                    options=["Compradores", "Corretora"],
                    index=0 if parcela_sel["responsavel_pagamento"] != "Corretora" else 1,
                    key="novo_pagamento_resp",
                )

            if st.button("Registrar pagamento", type="primary"):
                try:
                    supabase.table("parcelas").update(
                        {
                            "status": "pago",
                            "data_pagamento": str(data_pagamento),
                            "valor_pago": float(valor_pago),
                            "responsavel_pagamento": responsavel_pagamento,
                        }
                    ).eq("id", int(parcela_sel["id"])).execute()

                    st.success("✅ Pagamento registrado com sucesso!")
                    time.sleep(0.8)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao registrar pagamento: {e}")

        st.markdown("---")
        st.markdown("### Editar parcela já paga")

        pagas = parcelas_contrato[parcelas_contrato["status"] == "pago"].copy()

        if pagas.empty:
            st.info("Nenhuma parcela paga para editar.")
        else:
            pagas = pagas.sort_values(["data_pagamento", "numero_parcela"], ascending=[False, True]).copy()

            pagas["label"] = (
                pagas["descricao_parcela"]
                + " | "
                + pagas["numero_parcela"].astype(str)
                + "/"
                + pagas["total_parcelas"].astype(str)
                + " | pago em "
                + pagas["data_pagamento"].dt.strftime("%d/%m/%Y")
                + " | "
                + pagas["valor_pago"].apply(brl)
            )

            parcela_paga_label = st.selectbox(
                "Selecione a parcela paga",
                pagas["label"].tolist(),
                key="edit_pago",
            )
            parcela_paga = pagas[pagas["label"] == parcela_paga_label].iloc[0]

            e1, e2, e3 = st.columns(3)
            with e1:
                nova_data_pagamento = st.date_input(
                    "Nova data do pagamento",
                    value=parcela_paga["data_pagamento"].date()
                    if pd.notnull(parcela_paga["data_pagamento"])
                    else date.today(),
                    format="DD/MM/YYYY",
                    key="edit_data_pagamento",
                )
            with e2:
                novo_valor_pago = st.number_input(
                    "Novo valor pago",
                    min_value=0.0,
                    value=float(parcela_paga["valor_pago"]),
                    step=0.01,
                    format="%.2f",
                    key="edit_valor_pago",
                )
            with e3:
                novo_responsavel = st.selectbox(
                    "Responsável",
                    options=["Compradores", "Corretora"],
                    index=0 if parcela_paga["responsavel_pagamento"] != "Corretora" else 1,
                    key="edit_responsavel",
                )

            b1, b2 = st.columns(2)

            with b1:
                if st.button("Salvar edição do pagamento"):
                    try:
                        supabase.table("parcelas").update(
                            {
                                "data_pagamento": str(nova_data_pagamento),
                                "valor_pago": float(novo_valor_pago),
                                "responsavel_pagamento": novo_responsavel,
                            }
                        ).eq("id", int(parcela_paga["id"])).execute()

                        st.success("✅ Pagamento atualizado com sucesso!")
                        time.sleep(0.8)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar pagamento: {e}")

            with b2:
                if st.button("Desfazer pagamento"):
                    try:
                        supabase.table("parcelas").update(
                            {
                                "status": "pendente",
                                "data_pagamento": None,
                                "valor_pago": None,
                            }
                        ).eq("id", int(parcela_paga["id"])).execute()

                        st.success("✅ Pagamento desfeito com sucesso!")
                        time.sleep(0.8)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao desfazer pagamento: {e}")

# =========================================================
# TAB 4 — ATUALIZAR PARCELAS
# =========================================================

with tab4:
    st.subheader(f"Atualizar Parcelas — {contrato_selecionado}")

    if not pode_editar:
        st.info("Somente Matheus Moreira pode atualizar parcelas.")
    elif parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
    else:
        edit_cols = [
            "id",
            "categoria",
            "origem",
            "descricao_parcela",
            "numero_parcela",
            "total_parcelas",
            "data_vencimento",
            "valor_principal",
            "valor_total",
            "status",
            "responsavel_pagamento",
        ]

        edit_df = parcelas_contrato[edit_cols].copy()
        edit_df["data_vencimento"] = pd.to_datetime(edit_df["data_vencimento"]).dt.date
        edit_df["valor_principal"] = edit_df["valor_principal"].round(2)
        edit_df["valor_total"] = edit_df["valor_total"].round(2)

        st.markdown("### Edite os campos abaixo e clique em salvar")
        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            disabled=["id"],
            column_config={
                "id": st.column_config.NumberColumn("ID"),
                "categoria": st.column_config.TextColumn("Categoria"),
                "origem": st.column_config.TextColumn("Origem"),
                "descricao_parcela": st.column_config.TextColumn("Descrição"),
                "numero_parcela": st.column_config.NumberColumn("Nº parcela"),
                "total_parcelas": st.column_config.NumberColumn("Total parcelas"),
                "data_vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                "valor_principal": st.column_config.NumberColumn("Valor principal", format="%.2f"),
                "valor_total": st.column_config.NumberColumn("Valor total", format="%.2f"),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["pendente", "pago", "atrasado"],
                ),
                "responsavel_pagamento": st.column_config.SelectboxColumn(
                    "Responsável",
                    options=["Compradores", "Corretora"],
                ),
            },
            key="editor_parcelas_novo",
        )

        if st.button("Salvar alterações das parcelas", type="primary"):
            try:
                original = edit_df.set_index("id")
                novo = edited.set_index("id")

                alteradas = 0

                for parcela_id in novo.index:
                    row_old = original.loc[parcela_id]
                    row_new = novo.loc[parcela_id]

                    venc_old = pd.to_datetime(row_old["data_vencimento"]).date()
                    venc_new = pd.to_datetime(row_new["data_vencimento"]).date()

                    payload = {}

                    campos = [
                        "categoria",
                        "origem",
                        "descricao_parcela",
                        "numero_parcela",
                        "total_parcelas",
                        "valor_principal",
                        "valor_total",
                        "status",
                        "responsavel_pagamento",
                    ]

                    for campo in campos:
                        old_val = row_old[campo]
                        new_val = row_new[campo]

                        if pd.isna(old_val) and pd.isna(new_val):
                            continue

                        if old_val != new_val:
                            payload[campo] = new_val

                    if venc_old != venc_new:
                        payload["data_vencimento"] = str(venc_new)

                    if payload:
                        supabase.table("parcelas").update(payload).eq("id", int(parcela_id)).execute()
                        alteradas += 1

                if alteradas == 0:
                    st.info("Nenhuma alteração detectada.")
                else:
                    st.success(f"✅ {alteradas} parcela(s) atualizada(s) com sucesso!")
                    time.sleep(0.8)
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao salvar alterações: {e}")