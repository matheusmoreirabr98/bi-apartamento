import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TAXAS,
    CONTRATO_TODOS,
    brl,
    card_html,
    render_cards_grid,
)


CORES_RESPONSAVEL = {
    "Compradores": "#56c718",
    "Corretora": "#d4c300",
    "Pendente": "#db8181",
    "Pago": "#56c718",
}

CORES_CONTRATO = {
    "Registro": "#56c718",
    "Entrada": "#d4c300",
    "Pago Registro": "#56c718",
    "Pendente Registro": "#a8d99a",
    "Pago Entrada": "#d4c300",
    "Pendente Entrada": "#eadf8a",
}


def _render_quatro_cards_em_linha(cards_html):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(cards_html[0], unsafe_allow_html=True)
    with c2:
        st.markdown(cards_html[1], unsafe_allow_html=True)
    with c3:
        st.markdown(cards_html[2], unsafe_allow_html=True)
    with c4:
        st.markdown(cards_html[3], unsafe_allow_html=True)


def render_dashboard(parcelas_contrato, parcelas_contagem, contrato_selecionado):
    contrato_sel = str(contrato_selecionado).strip().lower()
    contrato_direcional = str(CONTRATO_DIRECIONAL).strip().lower()
    contrato_taxas = str(CONTRATO_TAXAS).strip().lower()
    contrato_todos = str(CONTRATO_TODOS).strip().lower()

    eh_direcional = (
        contrato_sel == contrato_direcional
        or contrato_sel == "diferença"
        or contrato_sel == "diferenca"
        or "diferen" in contrato_sel
        or "direcional" in contrato_sel
    )
    eh_taxas = contrato_sel == contrato_taxas
    eh_todos = contrato_sel == contrato_todos

    if parcelas_contrato.empty:
        st.info("Sem dados para exibir.")
        return

    # =========================================================
    # NORMALIZAÇÃO
    # =========================================================
    parcelas_contrato = parcelas_contrato.copy()
    parcelas_contagem = parcelas_contagem.copy()

    if "responsavel_pagamento" in parcelas_contrato.columns:
        parcelas_contrato["responsavel_pagamento"] = (
            parcelas_contrato["responsavel_pagamento"]
            .astype(str)
            .str.strip()
            .str.title()
        )

    if "responsavel_pagamento" in parcelas_contagem.columns:
        parcelas_contagem["responsavel_pagamento"] = (
            parcelas_contagem["responsavel_pagamento"]
            .astype(str)
            .str.strip()
            .str.title()
        )

    if "contrato" in parcelas_contrato.columns:
        parcelas_contrato["contrato"] = (
            parcelas_contrato["contrato"]
            .astype(str)
            .str.strip()
        )

    if "contrato" in parcelas_contagem.columns:
        parcelas_contagem["contrato"] = (
            parcelas_contagem["contrato"]
            .astype(str)
            .str.strip()
        )

    # =========================================================
    # BASES DE CÁLCULO
    # =========================================================
    if eh_taxas:
        parcelas_base = parcelas_contrato[
            parcelas_contrato["responsavel_pagamento"] == "Compradores"
        ].copy()

        contagem_base = parcelas_contagem[
            parcelas_contagem["responsavel_pagamento"] == "Compradores"
        ].copy()
    else:
        parcelas_base = parcelas_contrato.copy()
        contagem_base = parcelas_contagem.copy()

    # =========================================================
    # TOTAIS PRINCIPAIS
    # =========================================================
    total_pago_geral = parcelas_base.loc[
        parcelas_base["status"] == "pago", "valor_pago"
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

    total_restante = parcelas_base.loc[
        parcelas_base["status"] != "pago", "valor_total"
    ].fillna(0).sum()

    if eh_taxas:
        total_geral = parcelas_contrato["valor_total"].fillna(0).sum()
        progresso_base = total_pago_compradores + total_pago_corretora
    else:
        total_geral = parcelas_base["valor_total"].fillna(0).sum()
        progresso_base = total_pago_geral

    total_pago_qtd = (contagem_base["status"] == "pago").sum()
    total_pendente_qtd = (contagem_base["status_exibicao"] == "pendente").sum()
    total_atrasado_qtd = (contagem_base["status_exibicao"] == "atrasado").sum()

    progresso_pct = (progresso_base / total_geral * 100) if total_geral else 0

    # =========================================================
    # CARDS
    # =========================================================
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
            card_html("Quant. Parcelas Pagas", str(int(total_pago_qtd)), small=True),
            card_html("Quant. Parcelas Pendentes", str(int(total_pendente_qtd)), small=True),
            card_html("Quant. Parcelas Atrasadas", str(int(total_atrasado_qtd)), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Total Restante", brl(total_restante), small=True),
        ], cols=1)

    elif eh_direcional:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
        ], cols=1)

        render_cards_grid([
            card_html("Valor Pendente", brl(total_restante), small=True),
            card_html("Progresso", f"{progresso_pct:.1f}%", small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(int(total_pago_qtd)), small=True),
            card_html("Quant. Parcelas Pendentes", str(int(total_pendente_qtd)), small=True),
            card_html("Quant. Parcelas Atrasadas", str(int(total_atrasado_qtd)), small=True),
        ], cols=3)

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
            card_html("Quant. Parcelas Pagas", str(int(total_pago_qtd)), small=True),
            card_html("Quant. Parcelas Pendentes", str(int(total_pendente_qtd)), small=True),
            card_html("Quant. Parcelas Atrasadas", str(int(total_atrasado_qtd)), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Total Restante", brl(total_restante), small=True),
        ], cols=1)

    st.progress(min(max(progresso_pct / 100, 0), 1.0))

    # =========================================================
    # PRÓXIMA PARCELA
    # =========================================================
    st.markdown("### Próxima Parcela")

    abertas = contagem_base[contagem_base["status"] != "pago"].copy()

    if abertas.empty:
        st.success("✅ Não há parcelas em aberto.")
    else:
        if eh_todos:
            prox_taxas = (
                abertas[abertas["contrato"] == CONTRATO_TAXAS]
                .sort_values(["data_vencimento", "numero_parcela"])
                .head(1)
                .copy()
            )

            prox_direcional = (
                abertas[abertas["contrato"] == CONTRATO_DIRECIONAL]
                .sort_values(["data_vencimento", "numero_parcela"])
                .head(1)
                .copy()
            )

            if not prox_taxas.empty:
                row = prox_taxas.iloc[0]

                _render_quatro_cards_em_linha([
                    card_html("Contrato", CONTRATO_TAXAS, small=True),
                    card_html(
                        "Parcela",
                        f'{int(row["numero_parcela"])}/{int(row["total_parcelas"])}',
                        small=True,
                    ),
                    card_html(
                        "Vencimento",
                        row["data_vencimento"].strftime("%d/%m/%Y")
                        if pd.notnull(row["data_vencimento"])
                        else "-",
                        small=True,
                    ),
                    card_html("Valor", brl(row["valor_total"]), small=True),
                ])

            if not prox_direcional.empty:
                row = prox_direcional.iloc[0]

                _render_quatro_cards_em_linha([
                    card_html("Contrato", CONTRATO_DIRECIONAL, small=True),
                    card_html(
                        "Parcela",
                        f'{int(row["numero_parcela"])}/{int(row["total_parcelas"])}',
                        small=True,
                    ),
                    card_html(
                        "Vencimento",
                        row["data_vencimento"].strftime("%d/%m/%Y")
                        if pd.notnull(row["data_vencimento"])
                        else "-",
                        small=True,
                    ),
                    card_html("Valor", brl(row["valor_total"]), small=True),
                ])

        else:
            proxima_parcela = (
                abertas.sort_values(["data_vencimento", "numero_parcela"])
                .head(1)
                .copy()
            )

            prox = proxima_parcela.iloc[0]

            render_cards_grid([
                card_html(
                    "Parcela",
                    f'{int(prox["numero_parcela"])}/{int(prox["total_parcelas"])}',
                    small=True,
                ),
                card_html(
                    "Vencimento",
                    prox["data_vencimento"].strftime("%d/%m/%Y")
                    if pd.notnull(prox["data_vencimento"])
                    else "-",
                    small=True,
                ),
                card_html("Valor", brl(prox["valor_total"]), small=True),
            ], cols=3)

    # =========================================================
    # GRÁFICOS
    # =========================================================
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Evolução por Mês")

        evolucao_df = parcelas_contrato.copy()

        if "data_pagamento" not in evolucao_df.columns:
            st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")
        else:
            evolucao_df = evolucao_df[
                (evolucao_df["status"] == "pago")
                & (evolucao_df["data_pagamento"].notna())
            ].copy()

            if evolucao_df.empty:
                st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
            else:
                evolucao_df["data_pagamento"] = pd.to_datetime(
                    evolucao_df["data_pagamento"], errors="coerce"
                )
                evolucao_df = evolucao_df[evolucao_df["data_pagamento"].notna()].copy()

                if eh_todos:
                    evolucao_df = evolucao_df[
                        evolucao_df["contrato"].isin([CONTRATO_TAXAS, CONTRATO_DIRECIONAL])
                    ].copy()

                    evolucao_df["serie"] = evolucao_df["contrato"].map({
                        CONTRATO_TAXAS: "Registro",
                        CONTRATO_DIRECIONAL: "Entrada",
                    })

                    evolucao_df["mes_ref"] = evolucao_df["data_pagamento"].dt.to_period("M")
                    evolucao_df["mes_ordem"] = evolucao_df["mes_ref"].astype(str)

                    mensal_df = (
                        evolucao_df.groupby(["mes_ordem"], as_index=False)
                        .agg(
                            total_pago=("valor_pago", "sum"),
                            qtd_parcelas=("valor_pago", "size"),
                        )
                        .sort_values(["mes_ordem"])
                    )

                    mapa_meses = {
                        1: "Jan",
                        2: "Fev",
                        3: "Mar",
                        4: "Abr",
                        5: "Mai",
                        6: "Jun",
                        7: "Jul",
                        8: "Ago",
                        9: "Set",
                        10: "Out",
                        11: "Nov",
                        12: "Dez",
                    }

                    datas_mes = pd.to_datetime(
                        mensal_df["mes_ordem"], format="%Y-%m", errors="coerce"
                    )

                    mensal_df["Mes"] = (
                        datas_mes.dt.month.map(mapa_meses)
                        + "/"
                        + datas_mes.dt.year.astype(str)
                    )

                    fig_mensal = go.Figure()

                    for serie in ["Registro", "Entrada"]:
                        df_serie = mensal_df[mensal_df["serie"] == serie].copy()

                        if df_serie.empty:
                            continue

                        df_serie = ordem_meses.merge(
                            df_serie,
                            on=["mes_ordem", "Mes"],
                            how="left"
                        )

                        df_serie["total_pago"] = df_serie["total_pago"].fillna(0)
                        df_serie["qtd_parcelas"] = df_serie["qtd_parcelas"].fillna(0)

                        textos = [
                            str(int(qtd)) if qtd > 0 else ""
                            for qtd in df_serie["qtd_parcelas"]
                        ]

                        hover_textos = [
                            (
                                f"<b>{mes}</b><br>"
                                f"Tipo: {serie}<br>"
                                f"Valor Pago: {brl(valor)}<br>"
                                f"Parcelas Pagas: {int(qtd)}"
                            )
                            for mes, valor, qtd in zip(
                                df_serie["Mes"],
                                df_serie["total_pago"],
                                df_serie["qtd_parcelas"],
                            )
                        ]

                        fig_mensal.add_trace(
                            go.Scatter(
                                x=df_serie["Mes"],
                                y=df_serie["total_pago"],
                                mode="lines+markers+text",
                                name=serie,
                                text=textos,
                                textposition="top center",
                                textfont={"size": 12},
                                line={"color": CORES_CONTRATO.get(serie, "#999999"), "width": 3},
                                marker={
                                    "color": CORES_CONTRATO.get(serie, "#999999"),
                                    "size": 9,
                                },
                                hovertemplate="%{customdata}<extra></extra>",
                                customdata=hover_textos,
                            )
                        )

                    fig_mensal.update_layout(
                        xaxis_title="Mês",
                        yaxis_title="Valor Pago",
                        legend_title_text="",
                        hovermode="x unified",
                        xaxis=dict(tickangle=90),
                    )

                    st.plotly_chart(fig_mensal, use_container_width=True)

                else:
                    if eh_direcional:
                        evolucao_df = evolucao_df.copy()
                        evolucao_df["mes_ref"] = evolucao_df["data_pagamento"].dt.to_period("M")
                        evolucao_df["mes_ordem"] = evolucao_df["mes_ref"].astype(str)

                        mensal_df = (
                            evolucao_df.groupby(["mes_ordem"], as_index=False)
                            .agg(
                                total_pago=("valor_pago", "sum"),
                                qtd_parcelas=("valor_pago", "size"),
                            )
                            .sort_values(["mes_ordem"])
                        )

                        mensal_df["Mes"] = pd.to_datetime(
                            mensal_df["mes_ordem"], format="%Y-%m", errors="coerce"
                        ).dt.strftime("%m/%Y")

                        textos = [
                            str(int(qtd)) if qtd > 0 else ""
                            for qtd in mensal_df["qtd_parcelas"]
                        ]

                        hover_textos = [
                            (
                                f"<b>{mes}</b><br>"
                                f"Valor Pago: {brl(valor)}<br>"
                                f"Parcelas Pagas: {int(qtd)}"
                            )
                            for mes, valor, qtd in zip(
                                mensal_df["Mes"],
                                mensal_df["total_pago"],
                                mensal_df["qtd_parcelas"],
                            )
                        ]

                        fig_mensal = go.Figure()

                        fig_mensal.add_trace(
                            go.Scatter(
                                x=mensal_df["Mes"],
                                y=mensal_df["total_pago"],
                                mode="lines+markers+text",
                                name="Pago",
                                text=textos,
                                textposition="top center",
                                textfont={"size": 12},
                                line={"color": CORES_RESPONSAVEL["Pago"], "width": 3},
                                marker={
                                    "color": CORES_RESPONSAVEL["Pago"],
                                    "size": 9,
                                },
                                hovertemplate="%{customdata}<extra></extra>",
                                customdata=hover_textos,
                            )
                        )

                        fig_mensal.update_layout(
                            xaxis_title="Mês",
                            yaxis_title="Valor Pago",
                            legend_title_text="",
                            hovermode="x unified",
                            xaxis=dict(tickangle=90),
                        )

                        st.plotly_chart(fig_mensal, use_container_width=True)

                    else:
                        if "responsavel_pagamento" in evolucao_df.columns:
                            evolucao_df["responsavel_pagamento"] = (
                                evolucao_df["responsavel_pagamento"]
                                .astype(str)
                                .str.strip()
                                .str.title()
                            )

                        evolucao_df = evolucao_df[
                            evolucao_df["responsavel_pagamento"].isin(["Compradores", "Corretora"])
                        ].copy()

                        if evolucao_df.empty:
                            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
                        else:
                            evolucao_df["mes_ref"] = evolucao_df["data_pagamento"].dt.to_period("M")
                            evolucao_df["mes_ordem"] = evolucao_df["mes_ref"].astype(str)

                            mensal_df = (
                                evolucao_df.groupby(["mes_ordem", "responsavel_pagamento"], as_index=False)
                                .agg(
                                    total_pago=("valor_pago", "sum"),
                                    qtd_parcelas=("valor_pago", "size"),
                                )
                                .sort_values(["mes_ordem", "responsavel_pagamento"])
                            )

                            mensal_df["Mes"] = pd.to_datetime(
                                mensal_df["mes_ordem"], format="%Y-%m", errors="coerce"
                            ).dt.strftime("%m/%Y")

                            ordem_meses = (
                                mensal_df[["mes_ordem", "Mes"]]
                                .drop_duplicates()
                                .sort_values("mes_ordem")
                            )

                            fig_mensal = go.Figure()

                            for responsavel in ["Compradores", "Corretora"]:
                                df_resp = mensal_df[
                                    mensal_df["responsavel_pagamento"] == responsavel
                                ].copy()

                                if df_resp.empty:
                                    continue

                                df_resp = ordem_meses.merge(
                                    df_resp,
                                    on=["mes_ordem", "Mes"],
                                    how="left"
                                )

                                df_resp["total_pago"] = df_resp["total_pago"].fillna(0)
                                df_resp["qtd_parcelas"] = df_resp["qtd_parcelas"].fillna(0)

                                textos = [
                                    str(int(qtd)) if qtd > 0 else ""
                                    for qtd in df_resp["qtd_parcelas"]
                                ]

                                hover_textos = [
                                    (
                                        f"<b>{mes}</b><br>"
                                        f"Responsável: {responsavel}<br>"
                                        f"Valor Pago: {brl(valor)}<br>"
                                        f"Parcelas Pagas: {int(qtd)}"
                                    )
                                    for mes, valor, qtd in zip(
                                        df_resp["Mes"],
                                        df_resp["total_pago"],
                                        df_resp["qtd_parcelas"],
                                    )
                                ]

                                fig_mensal.add_trace(
                                    go.Scatter(
                                        x=df_resp["Mes"],
                                        y=df_resp["total_pago"],
                                        mode="lines+markers+text",
                                        name=responsavel,
                                        text=textos,
                                        textposition="top center",
                                        textfont={"size": 12},
                                        line={"color": CORES_RESPONSAVEL.get(responsavel, "#999999"), "width": 3},
                                        marker={
                                            "color": CORES_RESPONSAVEL.get(responsavel, "#999999"),
                                            "size": 9,
                                        },
                                        hovertemplate="%{customdata}<extra></extra>",
                                        customdata=hover_textos,
                                    )
                                )

                            fig_mensal.update_layout(
                                xaxis_title="Mês",
                                yaxis_title="Valor Pago",
                                legend_title_text="",
                                hovermode="x unified",
                                xaxis=dict(tickangle=90),
                            )

                            st.plotly_chart(fig_mensal, use_container_width=True)

    with c2:
        st.markdown("### Distribuição dos Valores")

        if eh_todos:
            pago_registro = parcelas_contrato.loc[
                (parcelas_contrato["contrato"] == CONTRATO_TAXAS)
                & (parcelas_contrato["status"] == "pago"),
                "valor_pago",
            ].fillna(0).sum()

            pendente_registro = parcelas_contrato.loc[
                (parcelas_contrato["contrato"] == CONTRATO_TAXAS)
                & (parcelas_contrato["status"] != "pago"),
                "valor_total",
            ].fillna(0).sum()

            pago_entrada = parcelas_contrato.loc[
                (parcelas_contrato["contrato"] == CONTRATO_DIRECIONAL)
                & (parcelas_contrato["status"] == "pago"),
                "valor_pago",
            ].fillna(0).sum()

            pendente_entrada = parcelas_contrato.loc[
                (parcelas_contrato["contrato"] == CONTRATO_DIRECIONAL)
                & (parcelas_contrato["status"] != "pago"),
                "valor_total",
            ].fillna(0).sum()

            grupos = []

            if pago_registro > 0:
                grupos.append({"grupo": "Pago Registro", "valor": pago_registro})

            if pendente_registro > 0:
                grupos.append({"grupo": "Pendente Registro", "valor": pendente_registro})

            if pago_entrada > 0:
                grupos.append({"grupo": "Pago Entrada", "valor": pago_entrada})

            if pendente_entrada > 0:
                grupos.append({"grupo": "Pendente Entrada", "valor": pendente_entrada})

            resp_df = pd.DataFrame(grupos)

            if not resp_df.empty:
                fig_resp = px.pie(
                    resp_df,
                    names="grupo",
                    values="valor",
                    color="grupo",
                    color_discrete_map={
                        "Pago Registro": CORES_CONTRATO["Pago Registro"],
                        "Pendente Registro": CORES_CONTRATO["Pendente Registro"],
                        "Pago Entrada": CORES_CONTRATO["Pago Entrada"],
                        "Pendente Entrada": CORES_CONTRATO["Pendente Entrada"],
                    },
                )
                st.plotly_chart(fig_resp, use_container_width=True)

        elif eh_direcional:
            grupos = []

            if total_pago_geral > 0:
                grupos.append({"grupo": "Pago", "valor": total_pago_geral})

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
                        "Pago": CORES_RESPONSAVEL["Pago"],
                        "Pendente": CORES_RESPONSAVEL["Pendente"],
                    },
                )
                st.plotly_chart(fig_resp, use_container_width=True)

        else:
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
                        "Compradores": CORES_RESPONSAVEL["Compradores"],
                        "Corretora": CORES_RESPONSAVEL["Corretora"],
                        "Pendente": CORES_RESPONSAVEL["Pendente"],
                    },
                )
                st.plotly_chart(fig_resp, use_container_width=True)