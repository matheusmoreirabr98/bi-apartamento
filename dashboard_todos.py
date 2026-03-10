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
    _is_evolucao_obra,
    _is_sinal_ato,
    _to_numeric_brl,
    _to_datetime_br,
    _aplicar_regra_direcional,
    _aplicar_regra_taxas_cartorio,
    _aplicar_regra_financiamento_caixa,
    _filtrar_base_entrada_direcional,
    _filtrar_base_taxas_cartorio,
    _eh_parcela_direcional_paga,
    _formatar_mes_pt,
)

CORES_GRAFICO = {
    "Ato": "#7c3aed",
    "Sinal": "#a855f7",
    "Sinal Ato": "#c084fc",
    "Diferença": "#f59e0b",
    "Diferenca": "#f59e0b",
    "Evolução de Obra": "#06b6d4",
    "Evolucao de Obra": "#06b6d4",
    "Entrada Direcional": "#d4c300",
    "Taxas Cartoriais": "#56c718",
    "Financiamento Caixa": "#ef4444",
}


def _contrato_label(valor):
    return str(valor).strip()


def _render_tres_cards_linha(card1, card2, card3):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card1, unsafe_allow_html=True)
    with c2:
        st.markdown(card2, unsafe_allow_html=True)
    with c3:
        st.markdown(card3, unsafe_allow_html=True)


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


def _normalizar_contrato(df):
    base = df.copy()
    if "contrato" in base.columns:
        base["contrato"] = base["contrato"].astype(str).str.strip()
    return base


def _aplicar_regras_por_contrato(df):
    """
    Aplica as mesmas regras do dashboard individual, mas contrato por contrato,
    sem mexer em nenhuma visualização individual.
    """
    if df.empty:
        return df.copy()

    base = _normalizar_contrato(df)
    partes = []

    for contrato, grupo in base.groupby("contrato", dropna=False):
        parte = grupo.copy()
        nome = str(contrato).strip()

        if not nome or nome.lower() == str(CONTRATO_TODOS).strip().lower():
            continue

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
            status_norm = parte["status"].astype(str).str.strip().str.lower() if "status" in parte.columns else ""
            parte["pago_calc"] = status_norm.eq("pago")
            parte["pendente_calc"] = ~parte["pago_calc"]

        if "valor_total" in parte.columns:
            parte["valor_total_calc"] = _to_numeric_brl(parte["valor_total"])
        else:
            parte["valor_total_calc"] = 0.0

        if "valor_pago" in parte.columns:
            parte["valor_pago_calc"] = _to_numeric_brl(parte["valor_pago"])
        else:
            parte["valor_pago_calc"] = 0.0

        if _is_taxas_cartorio(nome):
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(parte["pendente_calc"], 0)
        elif _is_financiamento_caixa(nome):
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(parte.get("aberta_calc", False), 0)
        else:
            parte["valor_pago_usado"] = parte["valor_pago_calc"].where(parte["pago_calc"], 0)
            parte["valor_pendente_usado"] = parte["valor_total_calc"].where(parte["pendente_calc"], 0)

        partes.append(parte)

    if not partes:
        return pd.DataFrame()

    return pd.concat(partes, ignore_index=True)


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
            total_parcelas=("contrato", "size"),
        )
        .sort_values("contrato")
        .reset_index(drop=True)
    )

    resumo["parcelas_pagas"] = resumo["parcelas_pagas"].astype(int)
    resumo["parcelas_restantes"] = resumo["total_parcelas"] - resumo["parcelas_pagas"]
    resumo["percentual"] = resumo.apply(
        lambda row: (row["valor_pago"] / row["valor_total"] * 100) if row["valor_total"] > 0 else 0,
        axis=1,
    )

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

    if "numero_parcela" in base.columns:
        base["numero_parcela_ordem"] = pd.to_numeric(base["numero_parcela"], errors="coerce")
    else:
        base["numero_parcela_ordem"] = pd.NA

    if "pendente_calc" not in base.columns:
        base["pendente_calc"] = ~base["pago_calc"]

    abertas = base[base["pendente_calc"]].copy()

    if abertas.empty:
        return pd.DataFrame()

    abertas = abertas.sort_values(
        ["contrato", "vencimento_ordem", "numero_parcela_ordem"],
        na_position="last",
    )

    proximas = abertas.groupby("contrato", as_index=False).first()

    if "data_vencimento_calc" in proximas.columns:
        venc = pd.to_datetime(proximas["data_vencimento_calc"], errors="coerce")
    elif "data_vencimento" in proximas.columns:
        venc = _to_datetime_br(proximas["data_vencimento"])
    else:
        venc = pd.Series([pd.NaT] * len(proximas))

    numero = pd.to_numeric(proximas.get("numero_parcela"), errors="coerce")
    total = pd.to_numeric(proximas.get("total_parcelas"), errors="coerce")

    referencia = []
    for _, row in proximas.iterrows():
        if "data_vencimento_calc" in row.index and pd.notnull(row["data_vencimento_calc"]):
            referencia.append(pd.to_datetime(row["data_vencimento_calc"]).strftime("%m/%Y"))
        elif "data_vencimento" in row.index and pd.notnull(row["data_vencimento"]):
            ref = _to_datetime_br(pd.Series([row["data_vencimento"]])).iloc[0]
            referencia.append(ref.strftime("%m/%Y") if pd.notnull(ref) else "-")
        else:
            referencia.append("-")

    parcela_txt = []
    for n, t in zip(numero, total):
        if pd.notnull(n) and pd.notnull(t):
            parcela_txt.append(f"{int(n)}/{int(t)}")
        elif pd.notnull(n):
            parcela_txt.append(str(int(n)))
        else:
            parcela_txt.append("-")

    return pd.DataFrame({
        "Contrato": proximas["contrato"],
        "Parcela": parcela_txt,
        "Referência": referencia,
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

    base_regras = _aplicar_regras_por_contrato(base)

    if base_regras.empty:
        st.info("Sem dados para exibir.")
        return

    resumo = _resumo_por_contrato(base_regras)

    if resumo.empty:
        st.info("Sem dados para exibir.")
        return

    pagamento_total = resumo["valor_pago"].sum()
    valor_total_geral = resumo["valor_total"].sum()
    valor_pendente_total = resumo["valor_pendente"].sum()
    percentual_total = (pagamento_total / valor_total_geral * 100) if valor_total_geral else 0

    # =========================================================
    # CARDS GERAIS
    # =========================================================
    render_cards_grid([
        card_html("Pagamento Total", brl(pagamento_total))
    ], cols=1)

    render_cards_grid([
        card_html("Conclusão Total", f"{percentual_total:.1f}%", small=True),
        card_html("Valor Total Pendente", brl(valor_pendente_total), small=True),
    ], cols=2)

    # =========================================================
    # CARDS POR CONTRATO
    # =========================================================
    st.markdown("### Resumo por Contrato")

    for _, row in resumo.iterrows():
        _render_tres_cards_linha(
            card_html(_contrato_label(row["contrato"]), brl(row["valor_pago"]), small=True),
            card_html(
                "Parcelas",
                f'{int(row["parcelas_pagas"])} pagas / {int(row["parcelas_restantes"])} restantes',
                small=True,
            ),
            card_html("Conclusão", f'{row["percentual"]:.1f}%', small=True),
        )

    render_cards_grid([
        card_html("Valor Total Pendente", brl(valor_pendente_total), small=True),
    ], cols=1)

    # =========================================================
    # PRÓXIMAS PARCELAS
    # =========================================================
    st.markdown("### Próximas Parcelas")

    proximas = _proximas_parcelas(base_regras)

    if proximas.empty:
        st.success("✅ Não há parcelas em aberto.")
    else:
        st.dataframe(proximas, use_container_width=True, hide_index=True)

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

            fig_mensal = go.Figure()

            contratos_ordem = resumo["contrato"].tolist()

            for contrato in contratos_ordem:
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

    for _, row in resumo.iterrows():
        if row["valor_pago"] > 0:
            pizza_rows.append({
                "grupo": f'{row["contrato"]} - Pago',
                "valor": row["valor_pago"],
            })

        if row["valor_pendente"] > 0:
            pizza_rows.append({
                "grupo": f'{row["contrato"]} - Pendente',
                "valor": row["valor_pendente"],
            })

    pizza_df = pd.DataFrame(pizza_rows)

    if pizza_df.empty:
        st.info("Não há valores suficientes para montar o gráfico de pizza.")
    else:
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
    resumo_exibir["valor_total"] = resumo_exibir["valor_total"].apply(brl)
    resumo_exibir["valor_pago"] = resumo_exibir["valor_pago"].apply(brl)
    resumo_exibir["valor_pendente"] = resumo_exibir["valor_pendente"].apply(brl)
    resumo_exibir["percentual"] = resumo_exibir["percentual"].map(lambda x: f"{x:.1f}%")

    resumo_exibir = resumo_exibir.rename(columns={
        "contrato": "Contrato",
        "valor_total": "Valor Total",
        "valor_pago": "Valor Pago",
        "valor_pendente": "Valor Pendente",
        "parcelas_pagas": "Parcelas Pagas",
        "parcelas_restantes": "Parcelas Restantes",
        "total_parcelas": "Total Parcelas",
        "percentual": "% Conclusão",
    })

    st.dataframe(resumo_exibir, use_container_width=True, hide_index=True)