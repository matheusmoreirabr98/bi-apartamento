# dashboard_todos.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import brl, card_html, render_cards_grid, CONTRATO_TODOS
from dashboard import (
    _is_entrada_direcional,
    _is_direcional,
    _is_financiamento_caixa,
    _is_taxas_cartorio,
    _to_numeric_brl,
    _to_datetime_br,
    _aplicar_regra_direcional,
    _aplicar_regra_taxas_cartorio,
    _aplicar_regra_financiamento_caixa,
    _filtrar_base_entrada_direcional,
    _filtrar_base_taxas_cartorio,
    _formatar_mes_pt,
    _render_barra_progresso_custom,
    _configurar_eixo_y_valor,
)

ORDEM_CONTRATOS = [
    "Sinal",
    "Sinal Ato",
    "Diferença",
    "Evolução de Obra",
    "Entrada Direcional",
    "Taxas Cartoriais",
    "Financiamento Caixa",
]

ORDEM_PROXIMAS = [
    "Evolução de Obra",
    "Taxas Cartoriais",
    "Entrada Direcional",
    "Financiamento Caixa",
]

CORES_GRAFICO = {
    "Sinal": "#a855f7",
    "Sinal Ato": "#c084fc",
    "Diferença": "#f59e0b",
    "Evolução de Obra": "#06b6d4",
    "Entrada Direcional": "#d4c300",
    "Taxas Cartoriais": "#56c718",
    "Financiamento Caixa": "#ef4444",
}


def _contrato_label(valor):
    nome = str(valor).strip()
    nome_lower = nome.lower()

    if nome_lower == "diferenca":
        return "Diferença"
    if nome_lower == "evolucao de obra":
        return "Evolução de Obra"
    if nome_lower == "financiamento da caixa":
        return "Financiamento Caixa"
    return nome


def _ordem_contrato(nome):
    nome = _contrato_label(nome)
    try:
        return ORDEM_CONTRATOS.index(nome)
    except ValueError:
        return 999


def _ordem_proxima(nome):
    nome = _contrato_label(nome)
    try:
        return ORDEM_PROXIMAS.index(nome)
    except ValueError:
        return 999


def _render_quatro_cards_linha(card1, card2, card3, card4):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(card1, unsafe_allow_html=True)
    with c2:
        st.markdown(card2, unsafe_allow_html=True)
    with c3:
        st.markdown(card3, unsafe_allow_html=True)
    with c4:
        st.markdown(card4, unsafe_allow_html=True)


def _render_tres_cards_linha(card1, card2, card3):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card1, unsafe_allow_html=True)
    with c2:
        st.markdown(card2, unsafe_allow_html=True)
    with c3:
        st.markdown(card3, unsafe_allow_html=True)


def _normalizar_contrato(df):
    base = df.copy()
    if "contrato" in base.columns:
        base["contrato"] = base["contrato"].astype(str).str.strip().map(_contrato_label)
    return base


def _status_norm(serie):
    if isinstance(serie, pd.Series):
        return serie.astype(str).str.strip().str.lower()
    return pd.Series(dtype="object")


def _calcular_total_parcelas_df(df):
    if df.empty:
        return 0

    base = df.copy()

    if "total_parcelas" in base.columns:
        base["total_parcelas_num"] = pd.to_numeric(base["total_parcelas"], errors="coerce")
        validos = base[base["total_parcelas_num"].notna()].copy()

        if not validos.empty:
            if "serie" in validos.columns:
                validos["serie_calc"] = validos["serie"].fillna("").astype(str).str.strip()
                if validos["serie_calc"].replace("", pd.NA).notna().any():
                    validos["serie_calc"] = validos["serie_calc"].replace("", "__sem_serie__")
                    total = validos.groupby("serie_calc")["total_parcelas_num"].max().sum()
                    if total > 0:
                        return int(total)

            max_total = validos["total_parcelas_num"].max()
            if pd.notnull(max_total) and max_total > 0:
                return int(max_total)

    if "numero_parcela" in base.columns:
        base["numero_parcela_num"] = pd.to_numeric(base["numero_parcela"], errors="coerce")
        validos = base[base["numero_parcela_num"].notna()].copy()

        if not validos.empty:
            if "serie" in validos.columns:
                validos["serie_calc"] = validos["serie"].fillna("").astype(str).str.strip()
                if validos["serie_calc"].replace("", pd.NA).notna().any():
                    validos["serie_calc"] = validos["serie_calc"].replace("", "__sem_serie__")
                    total = validos.groupby("serie_calc")["numero_parcela_num"].max().sum()
                    if total > 0:
                        return int(total)

            max_num = validos["numero_parcela_num"].max()
            if pd.notnull(max_num) and max_num > 0:
                return int(max_num)

    return int(len(base))


def _aplicar_regras_por_contrato(df):
    if df.empty:
        return df.copy()

    base = _normalizar_contrato(df)
    partes = []

    for contrato, grupo in base.groupby("contrato", dropna=False):
        nome = _contrato_label(contrato)

        if not nome:
            continue

        if nome.strip().lower() == str(CONTRATO_TODOS).strip().lower():
            continue

        parte = grupo.copy()

        if _is_entrada_direcional(nome):
            parte = _filtrar_base_entrada_direcional(parte)
            parte = _aplicar_regra_direcional(parte)

        elif _is_direcional(nome):
            parte = _aplicar_regra_direcional(parte)

        elif _is_taxas_cartorio(nome):
            parte = _aplicar_regra_taxas_cartorio(parte)
            if "valor_total" in parte.columns:
                parte["valor_total_calc"] = _to_numeric_brl(parte["valor_total"])

        elif _is_financiamento_caixa(nome):
            parte = _aplicar_regra_financiamento_caixa(parte)

        else:
            status = _status_norm(parte["status"]) if "status" in parte.columns else pd.Series("", index=parte.index)
            parte["pago_calc"] = status.eq("pago")
            parte["pendente_calc"] = status.ne("pago")
            parte["atrasado_calc"] = False

        if "valor_total" in parte.columns:
            parte["valor_total_calc"] = _to_numeric_brl(parte["valor_total"])
        else:
            parte["valor_total_calc"] = 0.0

        if "valor_pago" in parte.columns:
            parte["valor_pago_calc"] = _to_numeric_brl(parte["valor_pago"])
        else:
            parte["valor_pago_calc"] = 0.0

        if "numero_parcela" in parte.columns:
            parte["numero_parcela_calc"] = pd.to_numeric(parte["numero_parcela"], errors="coerce")
        else:
            parte["numero_parcela_calc"] = pd.NA

        if "total_parcelas" in parte.columns:
            parte["total_parcelas_calc"] = pd.to_numeric(parte["total_parcelas"], errors="coerce")
        else:
            parte["total_parcelas_calc"] = pd.NA

        if "atrasado_calc" not in parte.columns:
            parte["atrasado_calc"] = False

        if _is_financiamento_caixa(nome):
            aberta = parte["aberta_calc"] if "aberta_calc" in parte.columns else (~parte["pago_calc"])
            atrasada = parte["atrasado_calc"] if "atrasado_calc" in parte.columns else False
            pendente = parte["pendente_calc"] if "pendente_calc" in parte.columns else aberta

            parte["pendente_calc"] = pendente
            parte["atrasado_calc"] = atrasada
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(aberta, 0)
        else:
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(
                parte["pendente_calc"] | parte["atrasado_calc"], 0
            )

        desconto_calc = (parte["valor_total_calc"] - parte["valor_pago_calc"]).clip(lower=0)
        parte["desconto_obtido_calc"] = desconto_calc.where(parte["pago_calc"], 0)

        parte["contrato"] = nome
        partes.append(parte)

    if not partes:
        return pd.DataFrame()

    final = pd.concat(partes, ignore_index=True)
    final["ordem_contrato"] = final["contrato"].map(_ordem_contrato)
    return final


def _resumo_por_contrato(df):
    if df.empty:
        return pd.DataFrame()

    linhas = []

    for contrato, grupo in df.groupby("contrato", dropna=False):
        nome = _contrato_label(contrato)
        grupo = grupo.copy()

        valor_pago = float(grupo["valor_pago_usado"].sum())
        valor_pendente = float(grupo["valor_pendente_usado"].sum())

        if _is_taxas_cartorio(nome):
            valor_total = float(valor_pago + valor_pendente)
        else:
            valor_total = float(grupo["valor_total_calc"].sum())

        parcelas_pagas = int(grupo["pago_calc"].sum())
        parcelas_atrasadas = int(grupo["atrasado_calc"].sum()) if "atrasado_calc" in grupo.columns else 0

        total_parcelas = _calcular_total_parcelas_df(grupo)

        if _is_financiamento_caixa(nome):
            regime_iniciado = bool(grupo["regime_iniciado"].any()) if "regime_iniciado" in grupo.columns else False

            if regime_iniciado:
                parcelas_pendentes = int(grupo["pendente_calc"].sum())
            else:
                parcelas_pendentes = max(total_parcelas - parcelas_pagas, 0)
        else:
            parcelas_pendentes = int(grupo["pendente_calc"].sum())

        percentual = (parcelas_pagas / total_parcelas * 100) if total_parcelas > 0 else 0.0

        linhas.append({
            "contrato": nome,
            "valor_total": valor_total,
            "valor_pago": valor_pago,
            "valor_pendente": valor_pendente,
            "parcelas_pagas": parcelas_pagas,
            "parcelas_pendentes": parcelas_pendentes,
            "parcelas_atrasadas": parcelas_atrasadas,
            "total_parcelas": total_parcelas,
            "percentual_qtd": percentual,
            "ordem_contrato": _ordem_contrato(nome),
        })

    resumo = pd.DataFrame(linhas)
    resumo = resumo.sort_values(["ordem_contrato", "contrato"]).reset_index(drop=True)
    return resumo


def _proximas_parcelas(df):
    if df.empty:
        return pd.DataFrame()

    base = df.copy()

    base["data_vencimento_original"] = (
        _to_datetime_br(base["data_vencimento"])
        if "data_vencimento" in base.columns
        else pd.NaT
    )

    if "data_vencimento_calc" in base.columns:
        base["vencimento_ordem"] = pd.to_datetime(base["data_vencimento_calc"], errors="coerce")
        base["vencimento_ordem"] = base["vencimento_ordem"].fillna(base["data_vencimento_original"])
    else:
        base["vencimento_ordem"] = base["data_vencimento_original"]

    if "numero_parcela_calc" not in base.columns:
        if "numero_parcela" in base.columns:
            base["numero_parcela_calc"] = pd.to_numeric(base["numero_parcela"], errors="coerce")
        else:
            base["numero_parcela_calc"] = pd.NA

    if "total_parcelas_calc" not in base.columns:
        if "total_parcelas" in base.columns:
            base["total_parcelas_calc"] = pd.to_numeric(base["total_parcelas"], errors="coerce")
        else:
            base["total_parcelas_calc"] = pd.NA

    mask_abertas = (
        (base["pendente_calc"])
        | (base["atrasado_calc"])
        | (base["contrato"] == "Financiamento Caixa")
    )

    abertas = base[
        base["contrato"].isin(ORDEM_PROXIMAS) & mask_abertas
    ].copy()

    if abertas.empty:
        return pd.DataFrame()

    abertas["ordem_proxima"] = abertas["contrato"].map(_ordem_proxima)

    abertas = abertas.sort_values(
        ["ordem_proxima", "vencimento_ordem", "numero_parcela_calc"],
        na_position="last",
    )

    proximas_linhas = []

    for contrato in ORDEM_PROXIMAS:
        grupo = abertas[abertas["contrato"] == contrato].copy()
        if grupo.empty:
            continue

        if contrato == "Financiamento Caixa":
            regime_iniciado = bool(grupo["regime_iniciado"].any()) if "regime_iniciado" in grupo.columns else False

            if regime_iniciado:
                linha = grupo.iloc[0]
            else:
                grupo = grupo.sort_values(["numero_parcela_calc"], na_position="last")
                linha = grupo.iloc[0]
        else:
            linha = grupo.iloc[0]

        proximas_linhas.append(linha)

    if not proximas_linhas:
        return pd.DataFrame()

    proximas = pd.DataFrame(proximas_linhas).copy()

    venc = pd.to_datetime(proximas["vencimento_ordem"], errors="coerce")

    parcela_txt = []
    for _, row in proximas.iterrows():
        n = pd.to_numeric(row.get("numero_parcela_calc"), errors="coerce")
        t = pd.to_numeric(row.get("total_parcelas_calc"), errors="coerce")

        if pd.notnull(n) and pd.notnull(t) and t > 0:
            parcela_txt.append(f"{int(n)}/{int(t)}")
        elif pd.notnull(n):
            parcela_txt.append(str(int(n)))
        else:
            parcela_txt.append("-")

    return pd.DataFrame({
        "Contrato": proximas["contrato"].astype(str),
        "Parcela": parcela_txt,
        "Valor": proximas["valor_total_calc"].apply(brl),
        "Vencimento": venc.dt.strftime("%d/%m/%Y").fillna("-"),
        "ordem_proxima": proximas["ordem_proxima"].values,
    }).sort_values("ordem_proxima").reset_index(drop=True)


def render_dashboard_todos(parcelas):
    if parcelas.empty:
        st.info("Sem dados para exibir.")
        return

    base = parcelas.copy()

    if "eh_linha_resumo" in base.columns:
        base = base[~base["eh_linha_resumo"]].copy()

    if "contrato" not in base.columns:
        st.info("Sem dados para exibir.")
        return

    base["contrato"] = base["contrato"].astype(str).str.strip()
    base = base[
        (base["contrato"] != "")
        & (base["contrato"].str.lower() != str(CONTRATO_TODOS).strip().lower())
    ].copy()

    base = _normalizar_contrato(base)
    base_regras = _aplicar_regras_por_contrato(base)

    if base_regras.empty:
        st.info("Sem dados para exibir.")
        return

    resumo = _resumo_por_contrato(base_regras)

    if resumo.empty:
        st.info("Sem dados para exibir.")
        return

    pagamento_total = float(resumo["valor_pago"].sum())
    valor_total_geral = float(resumo["valor_total"].sum())
    valor_total_pendente = max(float(resumo["valor_pendente"].sum()), 0.0)
    desconto_total = float(base_regras["desconto_obtido_calc"].sum()) if "desconto_obtido_calc" in base_regras.columns else 0.0

    parcelas_pagas_total = int(resumo["parcelas_pagas"].sum())
    parcelas_pendentes_total = int(resumo["parcelas_pendentes"].sum())
    parcelas_atrasadas_total = int(resumo["parcelas_atrasadas"].sum())

    total_referencia = parcelas_pagas_total + parcelas_pendentes_total + parcelas_atrasadas_total
    conclusao_total = (parcelas_pagas_total / total_referencia * 100) if total_referencia > 0 else 0.0

    # =========================================================
    # CARDS GERAIS
    # =========================================================
    _render_barra_progresso_custom(conclusao_total)

    render_cards_grid([
        card_html("Pagamento Total", brl(pagamento_total), small=True),
        card_html("Pendente Estimado", brl(valor_total_pendente), small=True),
        card_html("Total Estimado", brl(valor_total_geral), small=True),
    ], cols=3)

    render_cards_grid([
        card_html("Desconto Obtido", brl(desconto_total), small=True),
    ], cols=1)

    render_cards_grid([
        card_html("Quant. Parcelas Pagas", str(parcelas_pagas_total), small=True),
        card_html("Quant. Parcelas Pendentes", str(parcelas_pendentes_total), small=True),
        card_html("Quant. Parcelas Atrasadas", str(parcelas_atrasadas_total), small=True),
    ], cols=3)

    # =========================================================
    # RESUMO POR CONTRATO
    # =========================================================
    st.markdown("### Resumo por Contrato")

    for _, row in resumo.iterrows():
        pend_atr = int(row["parcelas_pendentes"]) + int(row["parcelas_atrasadas"])

        _render_quatro_cards_linha(
            card_html(f'Valor Pendente - {row["contrato"]}', brl(row["valor_pendente"]), small=True),
            card_html("Parcelas", f'{int(row["parcelas_pagas"])}/{pend_atr}', small=True),
            card_html("Porcentagem de Conclusão", f'{row["percentual_qtd"]:.2f}%', small=True),
            card_html("Contrato", row["contrato"], small=True),
        )

    # =========================================================
    # PRÓXIMAS PARCELAS
    # =========================================================
    st.markdown("### Próximas Parcelas")

    proximas = _proximas_parcelas(base_regras)

    if proximas.empty:
        st.success("✅ Não há parcelas em aberto.")
    else:
        for _, row in proximas.iterrows():
            _render_tres_cards_linha(
                card_html(row["Contrato"], row["Parcela"], small=True),
                card_html("Valor", row["Valor"], small=True),
                card_html("Vencimento", row["Vencimento"], small=True),
            )

    # =========================================================
    # EVOLUÇÃO POR MÊS - POR CONTRATO
    # =========================================================
    st.markdown("### Evolução por Mês")

    evolucao = base_regras.copy()

    if "data_pagamento" not in evolucao.columns:
        st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")
    else:
        evolucao["data_pagamento_ref"] = _to_datetime_br(evolucao["data_pagamento"])
        evolucao = evolucao[
            (evolucao["pago_calc"])
            & (evolucao["data_pagamento_ref"].notna())
        ].copy()

        if evolucao.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao["mes_ref"] = evolucao["data_pagamento_ref"].dt.to_period("M")
            evolucao["mes_ordem"] = evolucao["mes_ref"].astype(str)
            evolucao["valor_pago_num"] = evolucao["valor_pago_usado"]

            mensal_df = (
                evolucao.groupby(["mes_ordem", "contrato"], as_index=False)
                .agg(
                    total_pago=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
                )
                .sort_values(["mes_ordem", "contrato"])
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

            ordem_meses = (
                mensal_df[["mes_ordem", "Mes"]]
                .drop_duplicates()
                .sort_values("mes_ordem")
            )

            fig_mensal = go.Figure()

            for contrato in ORDEM_CONTRATOS:
                df_contrato = mensal_df[mensal_df["contrato"] == contrato].copy()

                if df_contrato.empty:
                    continue

                df_contrato = ordem_meses.merge(
                    df_contrato,
                    on=["mes_ordem", "Mes"],
                    how="left"
                )

                df_contrato["total_pago"] = df_contrato["total_pago"].fillna(0)
                df_contrato["qtd_parcelas"] = df_contrato["qtd_parcelas"].fillna(0)

                hover_textos = [
                    (
                        f"<b>{mes}</b><br>"
                        f"Contrato: {contrato}<br>"
                        f"Parcelas Pagas: {int(qtd)}<br>"
                        f"Valor Pago no Mês: {brl(valor)}"
                    )
                    for mes, valor, qtd in zip(
                        df_contrato["Mes"],
                        df_contrato["total_pago"],
                        df_contrato["qtd_parcelas"],
                    )
                ]

                textos = [
                    str(int(qtd)) if qtd > 0 else ""
                    for qtd in df_contrato["qtd_parcelas"]
                ]

                cor = CORES_GRAFICO.get(contrato, None)

                fig_mensal.add_trace(
                    go.Scatter(
                        x=df_contrato["Mes"],
                        y=df_contrato["total_pago"],
                        mode="lines+markers+text",
                        name=contrato,
                        text=textos,
                        textposition="top center",
                        textfont={"size": 12},
                        line={"width": 3, **({"color": cor} if cor else {})},
                        marker={"size": 9, **({"color": cor} if cor else {})},
                        hovertemplate="%{customdata}<extra></extra>",
                        customdata=hover_textos,
                    )
                )

            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["total_pago"].max()) * 1.2 if not mensal_df.empty else 1000,
                1000,
            )

            fig_mensal.update_layout(
                dragmode="pan",
                hovermode="x unified",
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                xaxis=dict(tickangle=320),
            )

            st.plotly_chart(
                fig_mensal,
                use_container_width=True,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "scrollZoom": True,
                    "doubleClick": False,
                    "modeBarButtonsToRemove": [
                        "zoom2d",
                        "pan2d",
                        "select2d",
                        "lasso2d",
                        "toggleSpikelines",
                        "hoverClosestCartesian",
                        "hoverCompareCartesian",
                        "zoomIn2d",
                        "zoomOut2d",
                    ],
                    "modeBarButtonsToAdd": [
                        "resetScale2d",
                        "fullscreen",
                        "toImage",
                    ],
                },
            )

            st.markdown("### Valor Pago por Mês")

            valor_mes_df = (
                evolucao.groupby("mes_ordem", as_index=False)
                .agg(valor_pago_mes=("valor_pago_num", "sum"))
                .sort_values("mes_ordem")
            )

            valor_mes_df["Mes"] = _formatar_mes_pt(valor_mes_df["mes_ordem"])

            detalhes_mes = (
                evolucao.groupby(["mes_ordem", "contrato"], as_index=False)
                .agg(
                    valor_pago=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
                )
                .sort_values(["mes_ordem", "contrato"])
            )

            resumo_hover_mes = {}
            for mes_ordem, grupo in detalhes_mes.groupby("mes_ordem"):
                linhas = []
                for _, row in grupo.iterrows():
                    linhas.append(
                        f'{row["contrato"]}: {int(row["qtd_parcelas"])} parcela(s) - {brl(row["valor_pago"])}'
                    )
                resumo_hover_mes[mes_ordem] = "<br>".join(linhas)

            valor_mes_df["hover_resumo"] = valor_mes_df["mes_ordem"].map(resumo_hover_mes)

            fig_valor_mes = go.Figure()

            fig_valor_mes.add_trace(
                go.Bar(
                    x=valor_mes_df["Mes"],
                    y=valor_mes_df["valor_pago_mes"],
                    text=[brl(v) for v in valor_mes_df["valor_pago_mes"]],
                    textposition="outside",
                    customdata=valor_mes_df["hover_resumo"],
                    hovertemplate="<b>%{x}</b><br>%{customdata}<br><b>Total do Mês:</b> %{text}<extra></extra>",
                    name="Valor Pago",
                )
            )

            _configurar_eixo_y_valor(
                fig_valor_mes,
                float(valor_mes_df["valor_pago_mes"].max()) * 1.2 if not valor_mes_df.empty else 1000,
                1000,
            )

            fig_valor_mes.update_layout(
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                showlegend=False,
                hovermode="x unified",
            )

            st.plotly_chart(
                fig_valor_mes,
                use_container_width=True,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "scrollZoom": True,
                    "doubleClick": False,
                    "modeBarButtonsToRemove": [
                        "zoom2d",
                        "pan2d",
                        "select2d",
                        "lasso2d",
                        "toggleSpikelines",
                        "hoverClosestCartesian",
                        "hoverCompareCartesian",
                        "zoomIn2d",
                        "zoomOut2d",
                    ],
                    "modeBarButtonsToAdd": [
                        "resetScale2d",
                        "fullscreen",
                        "toImage",
                    ],
                },
            )

    # =========================================================
    # GRÁFICO DE PIZZA
    # =========================================================
    st.markdown("### Distribuição dos Valores")

    pizza_rows = []

    for contrato in ORDEM_CONTRATOS:
        linha = resumo[resumo["contrato"] == contrato]
        if linha.empty:
            continue

        valor_pago = float(linha["valor_pago"].iloc[0])
        valor_pendente = float(linha["valor_pendente"].iloc[0])

        if valor_pago > 0:
            pizza_rows.append({
                "grupo": f"{contrato} - Pago",
                "valor": valor_pago,
                "ordem": _ordem_contrato(contrato) * 2,
            })

        if valor_pendente > 0:
            pizza_rows.append({
                "grupo": f"{contrato} - Pendente",
                "valor": valor_pendente,
                "ordem": _ordem_contrato(contrato) * 2 + 1,
            })

    pizza_df = pd.DataFrame(pizza_rows)

    if pizza_df.empty:
        st.info("Não há valores suficientes para montar o gráfico de pizza.")
    else:
        pizza_df = pizza_df.sort_values("ordem").reset_index(drop=True)

        fig_pizza = px.pie(
            pizza_df,
            names="grupo",
            values="valor",
            category_orders={"grupo": pizza_df["grupo"].tolist()},
        )

        fig_pizza.update_traces(
            hovertemplate="Valor: %{customdata}<extra></extra>",
            customdata=[brl(v) for v in pizza_df["valor"]],
        )

        st.plotly_chart(fig_pizza, use_container_width=True)