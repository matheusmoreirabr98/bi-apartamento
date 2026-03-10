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
)


ORDEM_CONTRATOS = [
    "Sinal",
    "Sinal Ato",
    "Diferença",
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
    "Taxas Cartoriais": "#56c718",
    "Entrada Direcional": "#d4c300",
    "Financiamento Caixa": "#ef4444",
}


def _contrato_label(valor):
    nome = str(valor).strip()
    if nome == "Diferenca":
        return "Diferença"
    if nome == "Evolucao de Obra":
        return "Evolução de Obra"
    if nome.lower() == "financiamento da caixa":
        return "Financiamento Caixa"
    return nome


def _ordem_contrato(nome):
    nome = _contrato_label(nome)
    try:
        return ORDEM_CONTRATOS.index(nome)
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


def _render_proximas_cards(df):
    if df.empty:
        st.success("✅ Não há parcelas em aberto.")
        return

    for _, row in df.iterrows():
        _render_quatro_cards_linha(
            card_html("Contrato", row["Contrato"], small=True),
            card_html("Parcela", row["Parcela"], small=True),
            card_html("Vencimento", row["Vencimento"], small=True),
            card_html("Valor", row["Valor"], small=True),
        )


def _normalizar_contrato(df):
    base = df.copy()
    if "contrato" in base.columns:
        base["contrato"] = base["contrato"].astype(str).str.strip().map(_contrato_label)
    return base


def _status_norm(serie):
    if isinstance(serie, pd.Series):
        return serie.astype(str).str.strip().str.lower()
    return pd.Series(dtype="object")


def _aplicar_regras_por_contrato(df):
    """
    Aplica as regras já existentes no dashboard individual,
    mas somente para montar a visão "Todos os Contratos".
    """
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
            parte = _filtrar_base_taxas_cartorio(parte, somente_compradores=False)
            parte = _aplicar_regra_taxas_cartorio(parte)

        elif _is_financiamento_caixa(nome):
            parte = _aplicar_regra_financiamento_caixa(parte)

        else:
            status = _status_norm(parte["status"]) if "status" in parte.columns else pd.Series("", index=parte.index)
            parte["pago_calc"] = status.eq("pago")
            parte["pendente_calc"] = ~parte["pago_calc"]

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

        if _is_financiamento_caixa(nome):
            aberta = parte["aberta_calc"] if "aberta_calc" in parte.columns else (~parte["pago_calc"])
            parte["pendente_calc"] = aberta
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(aberta, 0)

        else:
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(parte["pendente_calc"], 0)

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

    resumo = (
        df.groupby("contrato", as_index=False)
        .agg(
            valor_total=("valor_total_calc", "sum"),
            valor_pago=("valor_pago_usado", "sum"),
            valor_pendente=("valor_pendente_usado", "sum"),
            parcelas_pagas=("pago_calc", "sum"),
            total_linhas=("contrato", "size"),
            total_parcelas_max=("total_parcelas_calc", "max"),
        )
        .reset_index(drop=True)
    )

    resumo["parcelas_pagas"] = resumo["parcelas_pagas"].fillna(0).astype(int)

    def _total_parcelas_row(row):
        total_max = row["total_parcelas_max"]
        total_linhas = row["total_linhas"]
        if pd.notnull(total_max) and total_max > 0:
            return int(total_max)
        return int(total_linhas)

    resumo["total_parcelas"] = resumo.apply(_total_parcelas_row, axis=1)
    resumo["parcelas_pendentes"] = (resumo["total_parcelas"] - resumo["parcelas_pagas"]).clip(lower=0)

    resumo["percentual_qtd"] = resumo.apply(
        lambda row: (row["parcelas_pagas"] / row["total_parcelas"] * 100) if row["total_parcelas"] > 0 else 0,
        axis=1,
    )

    resumo["ordem_contrato"] = resumo["contrato"].map(_ordem_contrato)
    resumo = resumo.sort_values(["ordem_contrato", "contrato"]).reset_index(drop=True)

    return resumo


def _proximas_parcelas(df):
    if df.empty:
        return pd.DataFrame()

    base = df.copy()

    if "data_vencimento_calc" in base.columns:
        base["vencimento_ordem"] = pd.to_datetime(base["data_vencimento_calc"], errors="coerce")
    elif "data_vencimento" in base.columns:
        base["vencimento_ordem"] = _to_datetime_br(base["data_vencimento"])
    else:
        base["vencimento_ordem"] = pd.NaT

    if "numero_parcela_calc" not in base.columns:
        if "numero_parcela" in base.columns:
            base["numero_parcela_calc"] = pd.to_numeric(base["numero_parcela"], errors="coerce")
        else:
            base["numero_parcela_calc"] = pd.NA

    abertas = base[base["pendente_calc"]].copy()

    if abertas.empty:
        return pd.DataFrame()

    abertas["ordem_contrato"] = abertas["contrato"].map(_ordem_contrato)

    abertas = abertas.sort_values(
        ["ordem_contrato", "vencimento_ordem", "numero_parcela_calc"],
        na_position="last",
    )

    proximas = abertas.groupby("contrato", as_index=False).first()
    proximas["ordem_contrato"] = proximas["contrato"].map(_ordem_contrato)
    proximas = proximas.sort_values(["ordem_contrato", "contrato"]).reset_index(drop=True)

    if "data_vencimento_calc" in proximas.columns:
        venc = pd.to_datetime(proximas["data_vencimento_calc"], errors="coerce")
    elif "data_vencimento" in proximas.columns:
        venc = _to_datetime_br(proximas["data_vencimento"])
    else:
        venc = pd.Series([pd.NaT] * len(proximas))

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
        "Contrato": proximas["contrato"],
        "Parcela": parcela_txt,
        "Vencimento": venc.dt.strftime("%d/%m/%Y").fillna("-"),
        "Valor": proximas["valor_total_calc"].apply(brl),
    })


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

    pagamento_total = resumo["valor_pago"].sum()
    total_parcelas_geral = resumo["total_parcelas"].sum()
    total_parcelas_pagas_geral = resumo["parcelas_pagas"].sum()
    conclusao_total = (total_parcelas_pagas_geral / total_parcelas_geral * 100) if total_parcelas_geral > 0 else 0
    valor_total_pendente = resumo["valor_pendente"].sum()

    # =========================================================
    # CARDS GERAIS
    # =========================================================
    render_cards_grid([
        card_html("Pagamento Total", brl(pagamento_total))
    ], cols=1)

    render_cards_grid([
        card_html("Conclusão Total", f"{conclusao_total:.1f}%", small=True),
        card_html("Valor Total Pendente", brl(valor_total_pendente), small=True),
    ], cols=2)

    # =========================================================
    # RESUMO POR CONTRATO
    # =========================================================
    st.markdown("### Resumo por Contrato")

    for _, row in resumo.iterrows():
        _render_quatro_cards_linha(
            card_html(row["contrato"], brl(row["valor_total"]), small=True),
            card_html("Valor Pago", brl(row["valor_pago"]), small=True),
            card_html(
                "Parcelas",
                f'{int(row["parcelas_pagas"])} pagas / {int(row["parcelas_pendentes"])} pendentes',
                small=True,
            ),
            card_html("Conclusão", f'{row["percentual_qtd"]:.1f}%', small=True),
        )

    render_cards_grid([
        card_html("Valor Total Pendente", brl(valor_total_pendente), small=True),
    ], cols=1)

    # =========================================================
    # PRÓXIMAS PARCELAS
    # =========================================================
    st.markdown("### Próximas Parcelas")

    proximas = _proximas_parcelas(base_regras)
    _render_proximas_cards(proximas)

    # =========================================================
    # EVOLUÇÃO POR MÊS
    # =========================================================
    st.markdown("### Evolução por Mês")

    evolucao = base_regras.copy()

    if "data_pagamento" not in evolucao.columns:
        st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")
    else:
        if "data_pagamento_ref" not in evolucao.columns:
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
            mensal_df["ordem_contrato"] = mensal_df["contrato"].map(_ordem_contrato)

            fig_mensal = go.Figure()

            for contrato in ORDEM_CONTRATOS:
                df_contrato = mensal_df[mensal_df["contrato"] == contrato].copy()

                if df_contrato.empty:
                    continue

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

            fig_mensal.update_layout(
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

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
        )

        fig_pizza.update_traces(
            hovertemplate="%{label}<br>Valor: %{customdata}<extra></extra>",
            customdata=[[brl(v)] for v in pizza_df["valor"]],
        )

        st.plotly_chart(fig_pizza, use_container_width=True)

    # =========================================================
    # TABELA FINAL
    # =========================================================
    st.markdown("### Resumo Consolidado")

    resumo_exibir = resumo.copy()
    resumo_exibir = resumo_exibir[[
        "contrato",
        "valor_total",
        "valor_pago",
        "valor_pendente",
        "parcelas_pagas",
        "parcelas_pendentes",
        "total_parcelas",
        "percentual_qtd",
    ]].copy()

    resumo_exibir["valor_total"] = resumo_exibir["valor_total"].apply(brl)
    resumo_exibir["valor_pago"] = resumo_exibir["valor_pago"].apply(brl)
    resumo_exibir["valor_pendente"] = resumo_exibir["valor_pendente"].apply(brl)
    resumo_exibir["percentual_qtd"] = resumo_exibir["percentual_qtd"].map(lambda x: f"{x:.1f}%")

    resumo_exibir = resumo_exibir.rename(columns={
        "contrato": "Contrato",
        "valor_total": "Valor Total",
        "valor_pago": "Valor Pago",
        "valor_pendente": "Valor Pendente",
        "parcelas_pagas": "Parcelas Pagas",
        "parcelas_pendentes": "Parcelas Pendentes",
        "total_parcelas": "Total Parcelas",
        "percentual_qtd": "% Conclusão",
    })

    st.dataframe(resumo_exibir, use_container_width=True, hide_index=True)