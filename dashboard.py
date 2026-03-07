import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TAXAS,
    CONTRATO_TODOS,
    brl,
    card_html,
    render_cards_grid,
)


def render_dashboard(parcelas_contrato, parcelas_contagem, contrato_selecionado):
    eh_direcional = contrato_selecionado == CONTRATO_DIRECIONAL
    eh_taxas = contrato_selecionado == CONTRATO_TAXAS
    eh_todos = contrato_selecionado == CONTRATO_TODOS

    if parcelas_contrato.empty:
        st.info("Sem dados para exibir.")
        return

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

    if eh_taxas:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral))
        ], cols=1)

        render_cards_grid([
            card_html("Pagamento Compradores", brl(total_pago_compradores), small=True),
            card_html("Pagamento Corretora", brl(total_pago_corretora), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Total Geral", brl(total_geral), small=True),
            card_html("Progresso", f"{progresso_pct:.1f}%", small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Pagas", str(int(total_pago_qtd)), small=True),
            card_html("Pendentes", str(int(total_pendente_qtd)), small=True),
            card_html("Atrasadas", str(int(total_atrasado_qtd)), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Total Restante", brl(total_restante), small=True),
            card_html("Juros Embutidos", brl(juros_futuros), small=True),
        ], cols=2)

    elif eh_direcional:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
        ], cols=1)

        render_cards_grid([
            card_html("Total Geral", brl(total_geral), small=True),
            card_html("Total Restante", brl(total_restante), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Progresso", f"{progresso_pct:.1f}%", small=True),
            card_html("Pagas", str(int(total_pago_qtd)), small=True),
            card_html("Pendentes", str(int(total_pendente_qtd)), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Atrasadas", str(int(total_atrasado_qtd)), small=True),
            card_html("Juros Embutidos", brl(juros_futuros), small=True),
        ], cols=2)

    else:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
        ], cols=1)

        render_cards_grid([
            card_html("Pagamento Compradores", brl(total_pago_compradores), small=True),
            card_html("Pagamento Corretora", brl(total_pago_corretora), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Total Geral", brl(total_geral), small=True),
            card_html("Progresso", f"{progresso_pct:.1f}%", small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Pagas", str(int(total_pago_qtd)), small=True),
            card_html("Pendentes", str(int(total_pendente_qtd)), small=True),
            card_html("Atrasadas", str(int(total_atrasado_qtd)), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Total Restante", brl(total_restante), small=True),
            card_html("Juros Embutidos", brl(juros_futuros), small=True),
        ], cols=2)

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
            render_cards_grid([
                card_html("Contrato", str(prox["contrato"]), small=True),
                card_html("Parcela", f'{int(prox["numero_parcela"])}/{int(prox["total_parcelas"])}', small=True),
                card_html(
                    "Vencimento",
                    prox["data_vencimento"].strftime("%d/%m/%Y") if pd.notnull(prox["data_vencimento"]) else "-",
                    small=True,
                ),
                card_html("Valor", brl(prox["valor_total"]), small=True),
            ], cols=2)
        else:
            render_cards_grid([
                card_html("Parcela", f'{int(prox["numero_parcela"])}/{int(prox["total_parcelas"])}', small=True),
                card_html(
                    "Vencimento",
                    prox["data_vencimento"].strftime("%d/%m/%Y") if pd.notnull(prox["data_vencimento"]) else "-",
                    small=True,
                ),
                card_html("Valor", brl(prox["valor_total"]), small=True),
            ], cols=3)

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