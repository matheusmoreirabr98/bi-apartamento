import pandas as pd
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TAXAS,
    STATUS_MAP_FILTRO,
    brl,
)


def render_parcelas_tab(parcelas_contrato, contrato_selecionado):
    eh_direcional = contrato_selecionado == CONTRATO_DIRECIONAL
    eh_taxas = contrato_selecionado == CONTRATO_TAXAS

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

    status_disp = ["Todos", "Pendente", "Atrasado", "Pago"]

    parc_f = parcelas_contrato.copy()

    # =========================================================
    # FILTROS
    # =========================================================
    if eh_taxas:
        f1, f2 = st.columns(2)

        with f1:
            status_filtro = st.selectbox("Status", status_disp, key="taxas_status")

        with f2:
            resp_disp = ["Todos"] + sorted(
                parc_f["responsavel_pagamento"].dropna().astype(str).unique().tolist()
            )
            resp_filtro = st.selectbox("Responsável", resp_disp, key="taxas_resp")
    else:
        status_filtro = st.selectbox(
            "Status",
            status_disp,
            key=f"status_{contrato_selecionado}"
        )
        resp_filtro = "Todos"

    # =========================================================
    # FILTROS FIXOS / CONDICIONAIS
    # =========================================================
    if eh_direcional:
        if "categoria" in parc_f.columns:
            parc_f = parc_f[parc_f["categoria"] == "Entrada Direcional"]

    if eh_taxas and resp_filtro != "Todos" and "responsavel_pagamento" in parc_f.columns:
        parc_f = parc_f[parc_f["responsavel_pagamento"] == resp_filtro]

    if "status_exibicao" in parc_f.columns:
        parc_f["status_exibicao"] = (
            parc_f["status_exibicao"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

    status_filtro_real = STATUS_MAP_FILTRO.get(status_filtro)

    if status_filtro != "Todos" and status_filtro_real and "status_exibicao" in parc_f.columns:
        parc_f = parc_f[
            parc_f["status_exibicao"] == str(status_filtro_real).strip().lower()
        ]

    colunas_ordenacao = [
        c for c in ["status_ordem", "data_vencimento", "numero_parcela"]
        if c in parc_f.columns
    ]
    if colunas_ordenacao:
        parc_f = parc_f.sort_values(colunas_ordenacao).copy()
    else:
        parc_f = parc_f.copy()

    # =========================================================
    # TABELA
    # =========================================================
    colunas_show = [
        "descricao_parcela_formatada",
        "data_vencimento",
        "data_pagamento",
        "valor_principal",
        "valor_total",
        "valor_pago",
    ]

    parc_f["descricao_parcela_formatada"] = (
        parc_f["contrato"].astype(str)
        + " "
        + parc_f["numero_parcela"].astype(str)
        + "/"
        + parc_f["total_parcelas"].astype(str)
    )

    colunas_existentes = [col for col in colunas_show if col in parc_f.columns]
    parc_show = parc_f[colunas_existentes].copy()

    if parc_show.empty:
        if status_filtro == "Todos":
            st.info("Não existem parcelas para exibir.")
        else:
            st.warning(f"Não existem parcelas com status **{status_filtro}**.")
        return

    # =========================================================
    # FORMATAÇÕES
    # =========================================================
    if "data_vencimento" in parc_show.columns:
        parc_show["data_vencimento"] = pd.to_datetime(
            parc_show["data_vencimento"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")
        parc_show["data_vencimento"] = parc_show["data_vencimento"].fillna("-")

    if "data_pagamento" in parc_show.columns:
        parc_show["data_pagamento"] = pd.to_datetime(
            parc_show["data_pagamento"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")
        parc_show["data_pagamento"] = parc_show["data_pagamento"].fillna("-")

    if "valor_principal" in parc_show.columns:
        parc_show["valor_principal"] = parc_show["valor_principal"].apply(
            lambda x: brl(x) if pd.notnull(x) else "-"
        )

    if "valor_total" in parc_show.columns:
        parc_show["valor_total"] = parc_show["valor_total"].apply(
            lambda x: brl(x) if pd.notnull(x) else "-"
        )

    if "valor_pago" in parc_show.columns:
        parc_show["valor_pago"] = parc_show["valor_pago"].apply(
            lambda x: brl(x) if pd.notnull(x) else "-"
        )

    parc_show.columns = [
        "Parcela",
        "Vencimento",
        "Pagamento",
        "Valor Principal",
        "Valor Total",
        "Valor Pago",
    ]

    html_tabela = parc_show.to_html(index=False, classes="parcelas-tabela")

    st.markdown("""
    <style>
    .parcelas-tabela {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }

    .tabela-scroll {
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
    }

    .parcelas-tabela th,
    .parcelas-tabela td {
        text-align: center;
        padding: 10px 8px;
        border-bottom: 1px solid #eee;
    }

    .parcelas-tabela th {
        text-align: center;
        font-weight: 600;
        background-color: #f8f9fa;
        position: sticky;
        top: 0;
        z-index: 1;
    }

    .parcelas-tabela td:nth-child(1),
    .parcelas-tabela td:nth-child(2),
    .parcelas-tabela td:nth-child(3) {
        text-align: center;
    }

    .parcelas-tabela td:nth-child(4),
    .parcelas-tabela td:nth-child(5),
    .parcelas-tabela td:nth-child(6) {
        text-align: center;
    }

    .resumo-titulo-centralizado {
        text-align: center;
        font-size: 20px;
        font-weight: 700;
        margin: 25px 0 12px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="tabela-scroll">
            {html_tabela}
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================================================
    # RESUMO POR STATUS
    # =========================================================
    if eh_direcional:
        resumo_base = parc_f.copy()
    else:
        if eh_taxas and resp_filtro == "Corretora":
            if "categoria" in parc_f.columns:
                resumo_base = parc_f[parc_f["categoria"] == "Taxas Banco"].copy()
            else:
                resumo_base = parc_f.copy()
        else:
            if "eh_linha_resumo" in parc_f.columns:
                resumo_base = parc_f[~parc_f["eh_linha_resumo"]].copy()
            else:
                resumo_base = parc_f.copy()

    if not resumo_base.empty and {"status_exibicao", "id", "valor_total"}.issubset(resumo_base.columns):
        st.markdown(
            '<div class="resumo-titulo-centralizado">Resumo Por Status</div>',
            unsafe_allow_html=True
        )

        resumo_status = (
            resumo_base.groupby("status_exibicao", as_index=False)
            .agg(
                quantidade=("id", "count"),
                total=("valor_total", "sum"),
            )
            .sort_values("status_exibicao")
        )

        resumo_status["status_exibicao"] = resumo_status["status_exibicao"].replace({
            "pago": "Pagas",
            "pendente": "Pendentes",
            "atrasado": "Atrasadas"
        })

        if not resumo_status.empty:
            resumo_status["total"] = resumo_status["total"].apply(brl)

            resumo_status.columns = [
                "Status",
                "Quantidade",
                "Total",
            ]

            html_resumo = resumo_status.to_html(index=False, classes="parcelas-tabela")

            st.markdown(
                f"""
                <div class="tabela-scroll">
                    {html_resumo}
                </div>
                """,
                unsafe_allow_html=True
            )