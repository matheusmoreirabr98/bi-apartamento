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
SUPABASE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

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

STATUS_MAP_FILTRO = {
    "Todos": None,
    "Pendente": "pendente",
    "Atrasado": "atrasado",
    "Pago": "pago",
}

CONTRATO_TODOS = "Todos os contratos"
CONTRATO_TAXAS = "Taxas Cartoriais"
CONTRATO_DIRECIONAL = "Entrada Direcional"

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


def normalizar_categoria(valor):
    if pd.isna(valor):
        return valor

    valor_str = str(valor).strip().lower()

    if valor_str == "registro":
        return "Taxas Cartoriais"

    return valor


def normalizar_status_banco(valor):
    if pd.isna(valor):
        return None
    return str(valor).strip().lower()


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
                df[col] = pd.to_numeric(df[col], errors="coerce")

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

        df["status"] = df["status"].apply(normalizar_status_banco)
        df["categoria"] = df["categoria"].apply(normalizar_categoria)

        df["valor_principal"] = df["valor_principal"].fillna(0.0)
        df["valor_total"] = df["valor_total"].fillna(0.0)

        if "valor_pago" in df.columns:
            df["valor_pago"] = pd.to_numeric(df["valor_pago"], errors="coerce")

        df["eh_linha_resumo"] = (
            df["categoria"].fillna("").astype(str).str.lower().eq("taxas banco")
            | df["descricao_parcela"].fillna("").astype(str).str.lower().str.contains("corretora", na=False)
        )

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
    if contrato == CONTRATO_TODOS:
        return df.copy()
    return df[df["contrato"] == contrato].copy()


def contrato_tem_corretora(df_contrato):
    if df_contrato.empty:
        return False
    return df_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any()


def registrar_pagamento(parcela_id, data_pagamento, valor_pago, responsavel_pagamento):
    supabase.table("parcelas").update(
        {
            "status": "pago",
            "data_pagamento": str(data_pagamento),
            "valor_pago": float(valor_pago),
            "responsavel_pagamento": responsavel_pagamento,
        }
    ).eq("id", int(parcela_id)).execute()

    res_check = (
        supabase.table("parcelas")
        .select("id,status,data_pagamento,valor_pago,responsavel_pagamento")
        .eq("id", int(parcela_id))
        .execute()
    )

    return res_check.data


def atualizar_pagamento_existente(parcela_id, data_pagamento, valor_pago, responsavel_pagamento):
    supabase.table("parcelas").update(
        {
            "data_pagamento": str(data_pagamento),
            "valor_pago": float(valor_pago),
            "responsavel_pagamento": responsavel_pagamento,
        }
    ).eq("id", int(parcela_id)).execute()

    res_check = (
        supabase.table("parcelas")
        .select("id,status,data_pagamento,valor_pago,responsavel_pagamento")
        .eq("id", int(parcela_id))
        .execute()
    )

    return res_check.data


def desfazer_pagamento(parcela_id):
    supabase.table("parcelas").update(
        {
            "status": "pendente",
            "data_pagamento": None,
            "valor_pago": None,
        }
    ).eq("id", int(parcela_id)).execute()

    res_check = (
        supabase.table("parcelas")
        .select("id,status,data_pagamento,valor_pago")
        .eq("id", int(parcela_id))
        .execute()
    )

    return res_check.data


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

opcoes_contrato = [CONTRATO_TODOS] + contratos_disponiveis if contratos_disponiveis else ["Sem dados"]

contrato_padrao = CONTRATO_TAXAS if CONTRATO_TAXAS in contratos_disponiveis else (
    contratos_disponiveis[0] if contratos_disponiveis else None
)

indice_padrao = 0
if contrato_padrao and contrato_padrao in opcoes_contrato:
    indice_padrao = opcoes_contrato.index(contrato_padrao)

contrato_selecionado = st.selectbox(
    "Selecione o contrato",
    options=opcoes_contrato,
    index=indice_padrao if opcoes_contrato and opcoes_contrato[0] != "Sem dados" else 0,
)

if contrato_selecionado == "Sem dados":
    st.stop()

parcelas_contrato = filtrar_contrato(parcelas, contrato_selecionado)
parcelas_contagem = parcelas_contrato[~parcelas_contrato["eh_linha_resumo"]].copy()

eh_direcional = contrato_selecionado == CONTRATO_DIRECIONAL
eh_taxas = contrato_selecionado == CONTRATO_TAXAS
eh_todos = contrato_selecionado == CONTRATO_TODOS

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
        ].fillna(0).sum()

        total_pago_compradores = parcelas_contrato.loc[
            (parcelas_contrato["status"] == "pago")
            & (parcelas_contrato["responsavel_pagamento"] == "Compradores"),
            "valor_pago",
        ].fillna(0).sum()

        total_pago_corretora = parcelas_contrato.loc[
            (parcelas_contrato["status"] == "pago")
            & (parcelas_contrato["responsavel_pagamento"] == "Corretora"),
            "valor_pago",
        ].fillna(0).sum()

        total_restante = parcelas_contrato.loc[
            parcelas_contrato["status"] != "pago", "valor_total"
        ].fillna(0).sum()

        total_geral = parcelas_contrato["valor_total"].fillna(0).sum()

        total_pago_qtd = (parcelas_contagem["status"] == "pago").sum()
        total_pendente_qtd = (parcelas_contagem["status_exibicao"] == "pendente").sum()
        total_atrasado_qtd = (parcelas_contagem["status_exibicao"] == "atrasado").sum()

        progresso_pct = (total_pago_geral / total_geral * 100) if total_geral else 0

        juros_futuros = (
            parcelas_contrato.loc[parcelas_contrato["status"] != "pago", "valor_total"].fillna(0)
            - parcelas_contrato.loc[parcelas_contrato["status"] != "pago", "valor_principal"].fillna(0)
        ).sum()

        if eh_direcional:
            k1, k2, k3 = st.columns(3)
            k1.metric("Pagamento Total", brl(total_pago_geral))
            k2.metric("Total Geral", brl(total_geral))
            k3.metric("Total Restante", brl(total_restante))
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Pagamento Total", brl(total_pago_geral))
            k2.metric("Pagamento - Compradores", brl(total_pago_compradores))
            k3.metric("Pagamento - Corretora", brl(total_pago_corretora))
            k4.metric("Total Geral", brl(total_geral))

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Progresso", f"{progresso_pct:.1f}%")
        k6.metric("Quant. Parcelas Pagas", int(total_pago_qtd))
        k7.metric("Quant. Parcelas Pendentes", int(total_pendente_qtd))
        k8.metric("Quant. Parcelas Atrasadas", int(total_atrasado_qtd))

        if eh_direcional:
            k9 = st.columns(1)[0]
            k9.metric("Juros Futuros Embutidos", brl(juros_futuros))
        else:
            k9, k10 = st.columns(2)
            k9.metric("Total Restante", brl(total_restante))
            k10.metric("Juros Futuros Embutidos", brl(juros_futuros))

        st.progress(min(max(progresso_pct / 100, 0), 1.0))

        st.markdown("### Próxima Parcela")

        proxima_parcela = (
            parcelas_contagem[parcelas_contagem["status"] != "pago"]
            .sort_values(["data_vencimento", "numero_parcela"])
            .head(1)
            .copy()
        )

        if proxima_parcela.empty:
            st.success("✅ Não há parcelas em aberto.")
        else:
            prox = proxima_parcela.iloc[0]

            if eh_todos:
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Contrato", prox["contrato"])
                p2.metric("Parcela", f'{int(prox["numero_parcela"])}/{int(prox["total_parcelas"])}')
                p3.metric(
                    "Vencimento",
                    prox["data_vencimento"].strftime("%d/%m/%Y")
                    if pd.notnull(prox["data_vencimento"])
                    else "-",
                )
                p4.metric("Valor", brl(prox["valor_total"]))
            else:
                p1, p2, p3 = st.columns(3)
                p1.metric("Parcela", f'{int(prox["numero_parcela"])}/{int(prox["total_parcelas"])}')
                p2.metric(
                    "Vencimento",
                    prox["data_vencimento"].strftime("%d/%m/%Y")
                    if pd.notnull(prox["data_vencimento"])
                    else "-",
                )
                p3.metric("Valor", brl(prox["valor_total"]))

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Situação das Parcelas")

            situacao_df = parcelas_contagem.copy()
            situacao_df["situacao_grafico"] = situacao_df["status"].apply(
                lambda x: "Pago" if x == "pago" else "Pendente"
            )

            status_df = (
                situacao_df.groupby("situacao_grafico", as_index=False)
                .size()
                .rename(columns={"size": "Quantidade"})
            )

            if not status_df.empty:
                fig_status = px.bar(
                    status_df,
                    x="situacao_grafico",
                    y="Quantidade",
                    color="situacao_grafico",
                    labels={
                        "situacao_grafico": "Quant. de Parcelas",
                        "Quantidade": "Quantidade",
                    },
                    color_discrete_map={
                        "Pago": "green",
                        "Pendente": "red",
                    },
                )
                fig_status.update_layout(showlegend=False)
                st.plotly_chart(fig_status, use_container_width=True)

        with c2:
            st.markdown("### Total Pago")

            grupos = []

            if total_pago_compradores > 0:
                grupos.append({"grupo": "Compradores", "valor": total_pago_compradores})

            if total_pago_corretora > 0:
                grupos.append({"grupo": "Corretora", "valor": total_pago_corretora})

            if total_restante > 0:
                grupos.append({"grupo": "Pendente", "valor": total_restante})

            resp_df = pd.DataFrame(grupos)

            if not resp_df.empty:
                fig_resp = px.pie(
                    resp_df,
                    names="grupo",
                    values="valor",
                    color="grupo",
                    color_discrete_map={
                        "Compradores": "#56c718c9",
                        "Corretora": "#61df74",
                        "Pendente": "red",
                    },
                )
                st.plotly_chart(fig_resp, use_container_width=True)

# =========================================================
# TAB 2 — PARCELAS
# =========================================================

with tab2:
    st.subheader(f"Parcelas — {contrato_selecionado}")

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
    else:
        status_disp = ["Todos", "Pendente", "Atrasado", "Pago"]

        if eh_direcional:
            f1, f2, f3 = st.columns(3)

            with f1:
                st.selectbox("Categoria", ["Entrada Direcional"], index=0, disabled=True, key="dir_cat_fixa")
                categoria_filtro = "Entrada Direcional"

            with f2:
                status_filtro = st.selectbox("Status", status_disp, key="dir_status")

            with f3:
                st.selectbox("Responsável", ["Compradores"], index=0, disabled=True, key="dir_resp_fixo")
                resp_filtro = "Compradores"

        else:
            f1, f2, f3 = st.columns(3)

            with f1:
                categorias_disp = ["Todas"] + sorted(
                    parcelas_contrato["categoria"].dropna().unique().tolist()
                )
                categoria_filtro = st.selectbox("Categoria", categorias_disp)

            with f2:
                status_filtro = st.selectbox("Status", status_disp)

            with f3:
                resp_disp = ["Todos"] + sorted(
                    parcelas_contrato["responsavel_pagamento"].dropna().unique().tolist()
                )
                resp_filtro = st.selectbox("Responsável", resp_disp)

        parc_f = parcelas_contrato.copy()

        if eh_direcional:
            parc_f = parc_f[parc_f["categoria"] == "Entrada Direcional"]
            parc_f = parc_f[parc_f["responsavel_pagamento"] == "Compradores"]
        else:
            if categoria_filtro != "Todas":
                parc_f = parc_f[parc_f["categoria"] == categoria_filtro]

            if resp_filtro != "Todos":
                parc_f = parc_f[parc_f["responsavel_pagamento"] == resp_filtro]

        status_filtro_real = STATUS_MAP_FILTRO.get(status_filtro)
        if status_filtro_real:
            parc_f = parc_f[parc_f["status_exibicao"] == status_filtro_real]

        parc_f = parc_f.sort_values(
            ["status_ordem", "data_vencimento", "numero_parcela"]
        ).copy()

        colunas_show = [
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

        if eh_todos:
            colunas_show = ["contrato"] + colunas_show

        parc_show = parc_f[colunas_show].copy()

        parc_show["data_vencimento"] = pd.to_datetime(parc_show["data_vencimento"]).dt.date
        parc_show["data_pagamento"] = pd.to_datetime(
            parc_show["data_pagamento"], errors="coerce"
        ).dt.date
        parc_show["valor_principal"] = parc_show["valor_principal"].apply(brl)
        parc_show["valor_total"] = parc_show["valor_total"].apply(brl)
        parc_show["valor_pago"] = parc_show["valor_pago"].apply(lambda x: brl(x) if pd.notnull(x) else "-")

        st.dataframe(parc_show, use_container_width=True, hide_index=True)

        if eh_direcional:
            resumo_base = parc_f.copy()
        else:
            if categoria_filtro == "Taxas Banco" or resp_filtro == "Corretora":
                resumo_base = parc_f[parc_f["categoria"] == "Taxas Banco"].copy()
            else:
                resumo_base = parc_f[~parc_f["eh_linha_resumo"]].copy()

        if not resumo_base.empty:
            st.markdown("### Resumo Por Status")

            resumo_status = (
                resumo_base.groupby("status_exibicao", as_index=False)
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
        pendentes = parcelas_contrato[
            (parcelas_contrato["status"] != "pago") & (~parcelas_contrato["eh_linha_resumo"])
        ].copy()

        st.markdown("### Marcar parcela como paga")

        if pendentes.empty:
            st.success("✅ Todas as parcelas desse contrato já estão pagas.")
        else:
            pendentes = pendentes.sort_values(["data_vencimento", "numero_parcela"]).copy()

            if eh_todos:
                pendentes["label"] = (
                    pendentes["contrato"]
                    + " | "
                    + pendentes["descricao_parcela"]
                    + " | "
                    + pendentes["numero_parcela"].astype(str)
                    + "/"
                    + pendentes["total_parcelas"].astype(str)
                    + " | vence "
                    + pendentes["data_vencimento"].dt.strftime("%d/%m/%Y")
                    + " | total "
                    + pendentes["valor_total"].apply(brl)
                )
            else:
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

            parcela_label = st.selectbox(
                "Selecione a parcela",
                pendentes["label"].tolist(),
                key="tab3_selecao_pendente",
            )
            parcela_sel = pendentes[pendentes["label"] == parcela_label].iloc[0]

            if parcela_sel["contrato"] == CONTRATO_DIRECIONAL:
                responsaveis_opcoes = ["Compradores"]
            else:
                responsaveis_opcoes = ["Compradores"]
                if parcelas_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any():
                    responsaveis_opcoes.append("Corretora")

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
                if parcela_sel["contrato"] == CONTRATO_DIRECIONAL:
                    st.selectbox(
                        "Responsável pelo pagamento",
                        options=["Compradores"],
                        index=0,
                        disabled=True,
                        key="novo_pagamento_resp_dir",
                    )
                    responsavel_pagamento = "Compradores"
                else:
                    idx_resp = 0
                    if parcela_sel["responsavel_pagamento"] in responsaveis_opcoes:
                        idx_resp = responsaveis_opcoes.index(parcela_sel["responsavel_pagamento"])

                    responsavel_pagamento = st.selectbox(
                        "Responsável pelo pagamento",
                        options=responsaveis_opcoes,
                        index=idx_resp,
                        key="novo_pagamento_resp",
                    )

            if st.button("Registrar pagamento", type="primary", key="btn_registrar_pagamento"):
                try:
                    dados_atualizados = registrar_pagamento(
                        parcela_id=parcela_sel["id"],
                        data_pagamento=data_pagamento,
                        valor_pago=valor_pago,
                        responsavel_pagamento=responsavel_pagamento,
                    )

                    if not dados_atualizados:
                        st.error("O banco não retornou a parcela atualizada.")
                    else:
                        linha = dados_atualizados[0]
                        if linha.get("status") != "pago":
                            st.error("A parcela não foi marcada como paga no banco.")
                        else:
                            st.success("✅ Pagamento registrado com sucesso!")
                            time.sleep(0.8)
                            st.rerun()

                except Exception as e:
                    st.error(f"Erro ao registrar pagamento: {e}")

        st.markdown("---")
        st.markdown("### Editar parcela já paga")

        pagas = parcelas_contrato[
            (parcelas_contrato["status"] == "pago") & (~parcelas_contrato["eh_linha_resumo"])
        ].copy()

        if pagas.empty:
            st.info("Nenhuma parcela paga para editar.")
        else:
            pagas = pagas.sort_values(["data_pagamento", "numero_parcela"], ascending=[False, True]).copy()

            if eh_todos:
                pagas["label"] = (
                    pagas["contrato"]
                    + " | "
                    + pagas["descricao_parcela"]
                    + " | "
                    + pagas["numero_parcela"].astype(str)
                    + "/"
                    + pagas["total_parcelas"].astype(str)
                    + " | pago em "
                    + pagas["data_pagamento"].dt.strftime("%d/%m/%Y")
                    + " | "
                    + pagas["valor_pago"].fillna(0).apply(brl)
                )
            else:
                pagas["label"] = (
                    pagas["descricao_parcela"]
                    + " | "
                    + pagas["numero_parcela"].astype(str)
                    + "/"
                    + pagas["total_parcelas"].astype(str)
                    + " | pago em "
                    + pagas["data_pagamento"].dt.strftime("%d/%m/%Y")
                    + " | "
                    + pagas["valor_pago"].fillna(0).apply(brl)
                )

            parcela_paga_label = st.selectbox(
                "Selecione a parcela paga",
                pagas["label"].tolist(),
                key="edit_pago",
            )
            parcela_paga = pagas[pagas["label"] == parcela_paga_label].iloc[0]

            if parcela_paga["contrato"] == CONTRATO_DIRECIONAL:
                responsaveis_opcoes_edit = ["Compradores"]
            else:
                responsaveis_opcoes_edit = ["Compradores"]
                if parcelas_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any():
                    responsaveis_opcoes_edit.append("Corretora")

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
                    value=float(parcela_paga["valor_pago"]) if pd.notnull(parcela_paga["valor_pago"]) else 0.0,
                    step=0.01,
                    format="%.2f",
                    key="edit_valor_pago",
                )
            with e3:
                if parcela_paga["contrato"] == CONTRATO_DIRECIONAL:
                    st.selectbox(
                        "Responsável",
                        options=["Compradores"],
                        index=0,
                        disabled=True,
                        key="edit_responsavel_dir",
                    )
                    novo_responsavel = "Compradores"
                else:
                    idx_edit = 0
                    if parcela_paga["responsavel_pagamento"] in responsaveis_opcoes_edit:
                        idx_edit = responsaveis_opcoes_edit.index(parcela_paga["responsavel_pagamento"])

                    novo_responsavel = st.selectbox(
                        "Responsável",
                        options=responsaveis_opcoes_edit,
                        index=idx_edit,
                        key="edit_responsavel",
                    )

            b1, b2 = st.columns(2)

            with b1:
                if st.button("Salvar edição do pagamento", key="btn_salvar_edicao_pagamento"):
                    try:
                        dados_atualizados = atualizar_pagamento_existente(
                            parcela_id=parcela_paga["id"],
                            data_pagamento=nova_data_pagamento,
                            valor_pago=novo_valor_pago,
                            responsavel_pagamento=novo_responsavel,
                        )

                        if not dados_atualizados:
                            st.error("O banco não retornou a parcela atualizada.")
                        else:
                            st.success("✅ Pagamento atualizado com sucesso!")
                            time.sleep(0.8)
                            st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao atualizar pagamento: {e}")

            with b2:
                if st.button("Desfazer pagamento", key="btn_desfazer_pagamento"):
                    try:
                        dados_atualizados = desfazer_pagamento(parcela_paga["id"])

                        if not dados_atualizados:
                            st.error("O banco não retornou a parcela atualizada.")
                        else:
                            linha = dados_atualizados[0]
                            if linha.get("status") != "pendente":
                                st.error("A parcela não voltou para pendente no banco.")
                            else:
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

        edit_df = parcelas_contrato[edit_cols + ["eh_linha_resumo", "contrato"]].copy()
        edit_df["data_vencimento"] = pd.to_datetime(edit_df["data_vencimento"]).dt.date
        edit_df["valor_principal"] = edit_df["valor_principal"].round(2)
        edit_df["valor_total"] = edit_df["valor_total"].round(2)

        responsaveis_editor = ["Compradores"]
        if parcelas_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any():
            responsaveis_editor.append("Corretora")

        st.markdown("### Edite os campos abaixo e clique em salvar")
        edited = st.data_editor(
            edit_df.drop(columns=["eh_linha_resumo"]),
            use_container_width=True,
            hide_index=True,
            disabled=["id", "contrato"] if eh_todos else ["id"],
            column_config={
                "id": st.column_config.NumberColumn("ID"),
                "contrato": st.column_config.TextColumn("Contrato"),
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
                    options=responsaveis_editor,
                ),
            },
            key="editor_parcelas_novo",
        )

        if st.button("Salvar alterações das parcelas", type="primary"):
            try:
                original = edit_df.drop(columns=["eh_linha_resumo"]).set_index("id")
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
                        if "categoria" in payload:
                            payload["categoria"] = (
                                "registro" if str(payload["categoria"]).strip().lower() == "taxas cartoriais"
                                else payload["categoria"]
                            )

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