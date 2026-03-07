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
        st.markdown("### Evolução por Mês")

        evolucao_df = parcelas_contrato.copy()

        if "data_pagamento" in evolucao_df.columns:
            evolucao_df = evolucao_df[
                (evolucao_df["status"] == "pago") & (evolucao_df["data_pagamento"].notna())
            ].copy()

            if not evolucao_df.empty:
                evolucao_df["mes_ref"] = pd.to_datetime(evolucao_df["data_pagamento"]).dt.to_period("M")
                evolucao_df["mes_ordem"] = evolucao_df["mes_ref"].astype(str)

                mensal_df = (
                    evolucao_df.groupby("mes_ordem", as_index=False)["valor_pago"]
                    .sum()
                    .rename(columns={"valor_pago": "Total Pago"})
                )

                mensal_df = mensal_df.sort_values("mes_ordem")
                mensal_df["Mes"] = pd.to_datetime(mensal_df["mes_ordem"]).dt.strftime("%m/%Y")

                fig_mensal = px.line(
                    mensal_df,
                    x="Mes",
                    y="Total Pago",
                    markers=True,
                    labels={
                        "Mes": "Mês",
                        "Total Pago": "Total Pago",
                    },
                )

                fig_mensal.update_layout(
                    showlegend=False,
                    xaxis_title="Mês",
                    yaxis_title="Valor Pago",
                )

                st.plotly_chart(fig_mensal, use_container_width=True)
            else:
                st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")

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