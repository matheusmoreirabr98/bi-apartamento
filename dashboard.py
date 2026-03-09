from datetime import date
import pandas as pd
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

MAPA_MESES = {
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


def _is_evolucao_obra(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return contrato in ["evolução de obra", "evolucao de obra"]


def _formatar_mes_pt(coluna_mes_ordem):
    datas_mes = pd.to_datetime(coluna_mes_ordem, format="%Y-%m", errors="coerce")
    return datas_mes.dt.month.map(MAPA_MESES) + "/" + datas_mes.dt.year.astype(str)


def _mes_nome_atual_pt():
    hoje = date.today()
    return MAPA_MESES.get(hoje.month, "")


def _referencia_mes_ano(valor_data):
    data_ref = pd.to_datetime(valor_data, errors="coerce")
    if pd.isnull(data_ref):
        return "-"
    return f"{MAPA_MESES[data_ref.month]}/{data_ref.year}"


def _texto_parcela(row, somente_numero=False):
    num = int(row["numero_parcela"]) if pd.notnull(row.get("numero_parcela")) else 0

    if somente_numero:
        return f"{num}"

    total = int(row["total_parcelas"]) if pd.notnull(row.get("total_parcelas")) else 0
    return f"{num}/{total}"


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


def _configurar_eixo_y(fig, faixa_max, passo):
    fig.update_layout(
        yaxis=dict(
            range=[0, faixa_max],
            dtick=passo,
            tickprefix="R$ ",
            separatethousands=True,
            tickformat=",",
        )
    )


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

    eh_taxas = (
        contrato_sel == contrato_taxas
        or contrato_sel == "sinal"
        or contrato_sel == "ato"
        or contrato_sel == "sinal ato"
        or "sinal" in contrato_sel
        or contrato_sel.startswith("ato")
    )

    eh_evolucao_obra = _is_evolucao_obra(contrato_selecionado)

    eh_todos = (
        contrato_sel == contrato_todos
        or "todos" in contrato_sel
    )

    if parcelas_contrato.empty:
        st.info("Sem dados para exibir.")
        return

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

    total_geral = parcelas_base["valor_total"].fillna(0).sum()
    progresso_base = total_pago_geral

    total_pago_qtd = int((contagem_base["status"] == "pago").sum())
    total_pendente_qtd = int((contagem_base["status_exibicao"] == "pendente").sum()) if "status_exibicao" in contagem_base.columns else 0
    total_atrasado_qtd = int((contagem_base["status_exibicao"] == "atrasado").sum()) if "status_exibicao" in contagem_base.columns else 0

    progresso_pct = (progresso_base / total_geral * 100) if total_geral else 0

    contrato_encerrado = False
    if eh_evolucao_obra and "contrato_encerrado" in parcelas_contrato.columns:
        contrato_encerrado = parcelas_contrato["contrato_encerrado"].fillna(False).astype(bool).any()

    # =========================================================
    # CARDS
    # =========================================================
    if eh_taxas:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral))
        ], cols=1)

        render_cards_grid([
            card_html("Valor Pendente", brl(total_restante), small=True),
            card_html("Progresso", f"{progresso_pct:.1f}%", small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_direcional:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
        ], cols=1)

        render_cards_grid([
            card_html("Valor Pendente", brl(total_restante), small=True),
            card_html("Progresso", f"{progresso_pct:.1f}%", small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_evolucao_obra:
        hoje = pd.Timestamp.today()
        pendente_mes_vigente = contagem_base[
            (contagem_base["status"] != "pago")
            & (pd.to_datetime(contagem_base["data_vencimento"], errors="coerce").dt.month == hoje.month)
            & (pd.to_datetime(contagem_base["data_vencimento"], errors="coerce").dt.year == hoje.year)
        ].shape[0]

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
        ], cols=1)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html(f'Quant. Parcelas Pendentes - {_mes_nome_atual_pt()}', str(int(pendente_mes_vigente)), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
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
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Total Restante", brl(total_restante), small=True),
        ], cols=1)

    if not eh_evolucao_obra:
        st.progress(min(max(progresso_pct / 100, 0), 1.0))

    # =========================================================
    # PRÓXIMA PARCELA
    # =========================================================
    st.markdown("### Próxima Parcela")

    if eh_evolucao_obra and contrato_encerrado:
        st.success("✅ Evolução de Obra concluída.")
    else:
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
                        card_html("Parcela", _texto_parcela(row), small=True),
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
                        card_html("Parcela", _texto_parcela(row), small=True),
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

                if eh_evolucao_obra:
                    render_cards_grid([
                        card_html("Referência", _referencia_mes_ano(prox["data_vencimento"]), small=True),
                        card_html("Parcela", _texto_parcela(prox, somente_numero=True), small=True),
                        card_html(
                            "Vencimento",
                            prox["data_vencimento"].strftime("%d/%m/%Y")
                            if pd.notnull(prox["data_vencimento"])
                            else "-",
                            small=True,
                        ),
                    ], cols=3)
                else:
                    render_cards_grid([
                        card_html("Parcela", _texto_parcela(prox), small=True),
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
    # GRÁFICO
    # =========================================================
    st.markdown("### Evolução por Mês")

    evolucao_df = parcelas_contrato.copy()

    if "data_pagamento" not in evolucao_df.columns:
        st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")
        return

    evolucao_df["data_pagamento"] = pd.to_datetime(
        evolucao_df["data_pagamento"], errors="coerce"
    )

    if eh_todos:
        evolucao_df = evolucao_df[
            evolucao_df["contrato"].isin([CONTRATO_TAXAS, CONTRATO_DIRECIONAL])
        ].copy()

        evolucao_df = evolucao_df[
            (evolucao_df["status"] == "pago")
            & (evolucao_df["data_pagamento"].notna())
        ].copy()

        if evolucao_df.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_df["serie"] = evolucao_df["contrato"].map({
                CONTRATO_TAXAS: "Registro",
                CONTRATO_DIRECIONAL: "Entrada",
            })

            evolucao_df["mes_ref"] = evolucao_df["data_pagamento"].dt.to_period("M")
            evolucao_df["mes_ordem"] = evolucao_df["mes_ref"].astype(str)

            mensal_df = (
                evolucao_df.groupby(["mes_ordem", "serie"], as_index=False)
                .agg(
                    total_pago=("valor_pago", "sum"),
                    qtd_parcelas=("valor_pago", "size"),
                )
                .sort_values(["mes_ordem", "serie"])
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

            ordem_meses = (
                mensal_df[["mes_ordem", "Mes"]]
                .drop_duplicates()
                .sort_values("mes_ordem")
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
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y(fig_mensal, 3000, 500)

            st.plotly_chart(fig_mensal, use_container_width=True)

    elif eh_direcional:
        evolucao_pago = evolucao_df[
            (evolucao_df["status"] == "pago")
            & (evolucao_df["data_pagamento"].notna())
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby(["mes_ordem"], as_index=False)
                .agg(
                    total_pago=("valor_pago", "sum"),
                    qtd_parcelas=("valor_pago", "size"),
                )
                .sort_values(["mes_ordem"])
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

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
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y(fig_mensal, 3000, 500)

            st.plotly_chart(fig_mensal, use_container_width=True)

    elif eh_evolucao_obra:
        evolucao_pago = evolucao_df[
            (evolucao_df["status"] == "pago")
            & (evolucao_df["data_pagamento"].notna())
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby(["mes_ordem"], as_index=False)
                .agg(
                    total_pago=("valor_pago", "sum"),
                    qtd_parcelas=("valor_pago", "size"),
                )
                .sort_values(["mes_ordem"])
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

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
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y(fig_mensal, 3000, 500)

            st.plotly_chart(fig_mensal, use_container_width=True)

    else:
        if "responsavel_pagamento" in evolucao_df.columns:
            evolucao_df["responsavel_pagamento"] = (
                evolucao_df["responsavel_pagamento"]
                .astype(str)
                .str.strip()
                .str.title()
            )

        evolucao_pago = evolucao_df[
            (evolucao_df["status"] == "pago")
            & (evolucao_df["data_pagamento"].notna())
            & (evolucao_df["responsavel_pagamento"].isin(["Compradores", "Corretora"]))
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby(["mes_ordem", "responsavel_pagamento"], as_index=False)
                .agg(
                    total_pago=("valor_pago", "sum"),
                    qtd_parcelas=("valor_pago", "size"),
                )
                .sort_values(["mes_ordem", "responsavel_pagamento"])
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

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

                if eh_taxas:
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
                else:
                    hover_textos = [
                        (
                            f"<b>{mes}</b><br>"
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
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y(fig_mensal, 2000, 500)

            st.plotly_chart(fig_mensal, use_container_width=True)