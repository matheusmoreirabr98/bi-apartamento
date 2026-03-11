#parcelas_view.py

import pandas as pd
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TODOS,
    STATUS_MAP_FILTRO,
    brl,
)


def render_parcelas_tab(parcelas_contrato, contrato_selecionado):
    eh_direcional = contrato_selecionado == CONTRATO_DIRECIONAL
    eh_todos = contrato_selecionado == CONTRATO_TODOS

    st.subheader(f"Parcelas — {contrato_selecionado}")

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

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