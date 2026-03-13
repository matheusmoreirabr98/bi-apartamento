# dashboard_todos.py

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import brl, card_html, render_cards_grid, CONTRATO_TODOS
from dashboard import (
    CORES_CONTRATO,
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
    _formatar_mes_pt,
    _render_barra_progresso_custom,
    _configurar_eixo_y_valor,
    _calcular_desconto_entrada_direcional,
    _calcular_desconto_taxas_cartorio,
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

ORDEM_PROXIMAS = [
    "Evolução de Obra",
    "Taxas Cartoriais",
    "Entrada Direcional",
    "Financiamento Caixa",
]

COR_TODOS = "#f40ae4"

def _titulo_centralizado(texto):
    st.markdown(
        f"""
        <div style="
            text-align: center;
            font-size: 20px;
            font-weight: 700;
            margin: 30px 0 20px 0;
            width: 100%;
            display: block;
        ">
            {texto}
        </div>
        """,
        unsafe_allow_html=True,
    )

def inject_styles():
    st.markdown("""
    <style>
    .cards-row-3 {
        display: flex;
        gap: 6px;
        width: 100%;
        max-width: 100%;
        overflow: hidden;
        box-sizing: border-box;
        margin-bottom: 0.5rem;
    }

    .cards-row-3 > div {
        flex: 1 1 0;
        min-width: 0;
        max-width: calc((100% - 12px) / 3);
        box-sizing: border-box;
    }

    .cards-row-3 .metric-card {
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 8px !important;
        box-sizing: border-box !important;
    }

    .cards-row-3 .metric-card h3,
    .cards-row-3 .metric-card p,
    .cards-row-3 .metric-card div {
        word-break: break-word !important;
        overflow-wrap: break-word !important;
    }

    /* centraliza a barra de ícones */
    .js-plotly-plot .plotly .modebar {
        left: 50% !important;
        transform: translateX(-50%) !important;
        right: auto !important;
        top: -8px !important; /* sobe os ícones */
    }

    /* reduz espaço entre ícones e gráfico */
    .js-plotly-plot {
        padding-top: 0 !important;
    }

    .stPlotlyChart {
        margin-top: -10px !important;
        margin-bottom: 0 !important;
    }

    @media (max-width: 768px) {
        .cards-row-3 {
            gap: 6px;
        }

        .cards-row-3 > div {
            flex: 1 1 0;
            min-width: 0;
            max-width: calc((100% - 12px) / 3);
        }

        .cards-row-3 .metric-card {
            padding: 6px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def _label_pizza(nome):
    mapa = {
        "Sinal": "Sinal",
        "Sinal Ato": "Sinal Ato",
        "Diferença": "Diferença",
        "Evolução de Obra": "Evol. Obra",
        "Taxas Cartoriais": "Taxas Cart.",
        "Entrada Direcional": "Entrada Dir.",
        "Financiamento Caixa": "Financ. Caixa",
    }
    return mapa.get(nome, nome)

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

def _render_tres_cards_linha(card1, card2, card3):
    st.markdown(
        f"""
        <div class="cards-row-3">
            <div>{card1}</div>
            <div>{card2}</div>
            <div>{card3}</div>
        </div>
        """,
        unsafe_allow_html=True,
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

        if _is_entrada_direcional(nome):
            desconto_total_contrato = _calcular_desconto_entrada_direcional(parte)
        elif _is_taxas_cartorio(nome):
            desconto_total_contrato = _calcular_desconto_taxas_cartorio(parte)
        elif _is_financiamento_caixa(nome):
            desconto_total_contrato = (
                (parte.loc[parte["pago_calc"], "valor_total_calc"].sum())
                - (parte.loc[parte["pago_calc"], "valor_pago_calc"].sum())
            )
        else:
            desconto_total_contrato = 0.0

        parte["desconto_obtido_calc"] = 0.0
        if len(parte) > 0:
            parte.iloc[0, parte.columns.get_loc("desconto_obtido_calc")] = float(desconto_total_contrato)

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

        elif nome == "Evolução de Obra":
            valor_total = float(grupo["valor_total_calc"].sum())

            if valor_pendente <= 0:
                valor_pendente = max(valor_total - valor_pago, 0.0)

        else:
            valor_total = float(grupo["valor_total_calc"].sum())

        parcelas_pagas = int(grupo["pago_calc"].sum())
        parcelas_atrasadas = int(grupo["atrasado_calc"].sum()) if "atrasado_calc" in grupo.columns else 0

        total_parcelas = _calcular_total_parcelas_df(grupo)

        if _is_taxas_cartorio(nome):
            grupo_qtd = grupo[grupo["responsavel_calc"] == "Compradores"].copy() if "responsavel_calc" in grupo.columns else grupo.copy()

            parcelas_pagas = int(grupo_qtd["pago_calc"].sum())
            parcelas_atrasadas = int(grupo_qtd["atrasado_calc"].sum()) if "atrasado_calc" in grupo_qtd.columns else 0
            total_parcelas = _calcular_total_parcelas_df(grupo_qtd)
            parcelas_pendentes = int(grupo_qtd["pendente_calc"].sum())

        else:
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

    abertas = abertas.sort_values(
        ["vencimento_ordem", "numero_parcela_calc", "contrato"],
        na_position="last",
    )

    proximas_linhas = []

    for contrato, grupo in abertas.groupby("contrato", sort=False):
        grupo = grupo.copy()

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

    valores_exibicao = []
    for _, row in proximas.iterrows():
        if str(row.get("contrato", "")).strip() == "Evolução de Obra" and float(row.get("valor_total_calc", 0) or 0) == 0:
            valores_exibicao.append("A definir")
        else:
            valores_exibicao.append(brl(row.get("valor_total_calc", 0)))

    vencimentos_exibicao = []
    for _, row in proximas.iterrows():
        contrato_nome = str(row.get("contrato", "")).strip()
        data_venc = pd.to_datetime(row.get("vencimento_ordem"), errors="coerce")

        if contrato_nome == "Financiamento Caixa" and pd.isna(data_venc):
            vencimentos_exibicao.append("A definir")
        else:
            vencimentos_exibicao.append(data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-")

    resultado = pd.DataFrame({
        "Contrato": proximas["contrato"].astype(str),
        "Parcela": parcela_txt,
        "Valor": valores_exibicao,
        "Vencimento": vencimentos_exibicao,
        "vencimento_ordem": venc,
    })

    return resultado.sort_values(
        ["vencimento_ordem", "Contrato"],
        na_position="last"
    ).drop(columns="vencimento_ordem").reset_index(drop=True)


def render_dashboard_todos(parcelas):
    inject_styles()

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
    valor_total_pendente = max(valor_total_geral - pagamento_total, 0.0)
    desconto_total = float(base_regras["desconto_obtido_calc"].sum()) if "desconto_obtido_calc" in base_regras.columns else 0.0

    parcelas_pagas_total = int(resumo["parcelas_pagas"].sum())
    parcelas_pendentes_total = int(resumo["parcelas_pendentes"].sum())
    parcelas_atrasadas_total = int(resumo["parcelas_atrasadas"].sum())

    total_referencia = parcelas_pagas_total + parcelas_pendentes_total + parcelas_atrasadas_total
    conclusao_total = (parcelas_pagas_total / total_referencia * 100) if total_referencia > 0 else 0.0

    # =========================================================
    # CARDS GERAIS
    # =========================================================
    _render_barra_progresso_custom(conclusao_total, cor=COR_TODOS)

    render_cards_grid([
        card_html("Pagamento Total", brl(pagamento_total), small=True),
        card_html("Pendente Estimado", brl(valor_total_pendente), small=True),
        card_html("Total Estimado", brl(valor_total_geral), small=True),
    ], cols=3)

    render_cards_grid([
        card_html("Desconto Obtido", brl(desconto_total), small=True),
    ], cols=1)

    render_cards_grid([
        card_html("Parcelas Pagas", str(parcelas_pagas_total), small=True),
        card_html("Parcelas Pendentes", str(parcelas_pendentes_total), small=True),
        card_html("Parcelas Atrasadas", str(parcelas_atrasadas_total), small=True),
    ], cols=3)

    # =========================================================
    # RESUMO POR CONTRATO
    # =========================================================
    _titulo_centralizado("Resumo por Contrato")

    for _, row in resumo.iterrows():
        if row["contrato"] == "Evolução de Obra":
            valor_exibicao = "A definir"
        else:
            valor_exibicao = brl(row["valor_pago"])

        _render_tres_cards_linha(
            card_html(row["contrato"], valor_exibicao, small=True),
            card_html("Parcelas", f'{int(row["parcelas_pagas"])}/{int(row["total_parcelas"])}', small=True),
            card_html("Conclusão", f'{row["percentual_qtd"]:.2f}%', small=True),
        )

    # =========================================================
    # PRÓXIMAS PARCELAS
    # =========================================================
    _titulo_centralizado("Próximas Parcelas")

    proximas = _proximas_parcelas(base_regras)

    if proximas.empty:
        st.success("✅ Não há parcelas em aberto.")
    else:
        for _, row in proximas.iterrows():
            if row["Contrato"] == "Evolução de Obra" and row["Valor"] == brl(0):
                valor_exibicao = "A definir"
            else:
                valor_exibicao = row["Valor"]

            if row["Contrato"] == "Financiamento Caixa" and str(row["Vencimento"]).strip() in ["-", "", "NaT"]:
                vencimento_exibicao = "A definir"
            else:
                vencimento_exibicao = row["Vencimento"]

            _render_tres_cards_linha(
                card_html(row["Contrato"], row["Parcela"], small=True),
                card_html("Valor", valor_exibicao, small=True),
                card_html("Vencimento", vencimento_exibicao, small=True),
            )

    # =========================================================
    # EVOLUÇÃO POR MÊS - POR CONTRATO
    # =========================================================
    _titulo_centralizado("Evolução por Mês")

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

            ordem_meses = ordem_meses.reset_index(drop=True)
            ordem_meses["x_pos"] = range(len(ordem_meses))
            mapa_x = dict(zip(ordem_meses["Mes"], ordem_meses["x_pos"]))

            fig_mensal = go.Figure()

            for contrato in ORDEM_CONTRATOS:
                df_contrato = mensal_df[mensal_df["contrato"] == contrato].copy()

                if df_contrato.empty:
                    continue

                primeiro_mes = df_contrato["mes_ordem"].min()
                ultimo_mes = df_contrato["mes_ordem"].max()

                ordem_meses_contrato = ordem_meses[
                    (ordem_meses["mes_ordem"] >= primeiro_mes)
                    & (ordem_meses["mes_ordem"] <= ultimo_mes)
                ].copy()

                df_contrato = ordem_meses_contrato.merge(
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

                cor = CORES_CONTRATO.get(contrato, None)

                df_contrato["x_pos"] = df_contrato["Mes"].map(mapa_x)

                fig_mensal.add_trace(
                    go.Scatter(
                        x=df_contrato["x_pos"],
                        y=df_contrato["total_pago"],
                        mode="lines+markers+text",
                        name=contrato,
                        text=textos,
                        textposition="top center",
                        textfont={"size": 16},
                        cliponaxis=False,
                        line={"width": 3, **({"color": cor} if cor else {})},
                        marker={"size": 9, **({"color": cor} if cor else {})},
                        hovertemplate="%{customdata}<extra></extra>",
                        customdata=hover_textos,
                    )
                )

                valor_max_dados = float(mensal_df["total_pago"].max()) if not mensal_df.empty else 1000
                valor_max_grafico = max(valor_max_dados * 1.15, 3300)

                fig_mensal.update_yaxes(
                    range=[0, valor_max_grafico],
                    tickmode="array",
                    tickvals=[0, 1000, 2000, 3000],
                    ticktext=["0", "1k", "2k", "3k"],
                )

            fig_mensal.update_layout(
                dragmode="pan",
                xaxis=dict(
                    tickangle=320,
                    tickmode="array",
                    tickvals=ordem_meses["x_pos"].tolist(),
                    ticktext=ordem_meses["Mes"].tolist(),
                    range=[-0.5, min(11.5, len(ordem_meses) - 0.5)],
                    fixedrange=False,
                ),
                yaxis=dict(
                    fixedrange=True,
                ),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.20,
                    xanchor="center",
                    x=0.5,
                    traceorder="normal",
                    font=dict(size=15),
                ),
                margin=dict(t=20, b=80, l=10, r=10)
            )

            st.plotly_chart(
                fig_mensal,
                use_container_width=True,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "scrollZoom": False,
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
                        "autoScale2d",
                        "resetScale2d",
                    ],
                    "modeBarButtonsToAdd": [
                        "fullscreen",
                        "toImage"
                    ],
                },
            )

            _titulo_centralizado("Valor Pago por Mês")

            valor_mes_df = (
                evolucao.groupby("mes_ordem", as_index=False)
                .agg(valor_pago_mes=("valor_pago_num", "sum"))
                .sort_values("mes_ordem")
            )

            valor_mes_df["Mes"] = _formatar_mes_pt(valor_mes_df["mes_ordem"])

            valor_mes_df = valor_mes_df.reset_index(drop=True)
            valor_mes_df["x_pos"] = range(len(valor_mes_df))

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
            valor_mes_df["valor_pago_fmt"] = valor_mes_df["valor_pago_mes"].apply(brl)

            fig_valor_mes = go.Figure()

            fig_valor_mes.add_trace(
                go.Bar(
                    x=valor_mes_df["x_pos"],
                    y=valor_mes_df["valor_pago_mes"],
                    customdata=list(
                        zip(
                            valor_mes_df["Mes"],
                            valor_mes_df["hover_resumo"],
                            valor_mes_df["valor_pago_fmt"],
                        )
                    ),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "%{customdata[1]}<br>"
                        "<b>Total do Mês:</b> %{customdata[2]}"
                        "<extra></extra>"
                    ),
                    name="Valor Pago",
                    marker=dict(color=COR_TODOS),
                )
            )

            fig_valor_mes.update_layout(
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                showlegend=False,
                hovermode="x unified",
                dragmode="pan",
                xaxis=dict(
                    tickmode="array",
                    tickvals=valor_mes_df["x_pos"].tolist(),
                    ticktext=valor_mes_df["Mes"].tolist(),
                    range=[-0.5, min(11.5, len(valor_mes_df) - 0.5)],
                    fixedrange=False,
                    tickangle=320,
                ),
                yaxis=dict(
                    fixedrange=True,
                ),
                margin=dict(t=20, b=10, l=10, r=10)
            )

            st.plotly_chart(
                fig_valor_mes,
                use_container_width=True,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "scrollZoom": False,
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
                        "autoScale2d",
                        "resetScale2d",
                    ],
                    "modeBarButtonsToAdd": [
                        "fullscreen",
                        "toImage",
                    ],
                },
            )

    # =========================================================
    # GRÁFICOS DE PIZZA
    # =========================================================
    _titulo_centralizado("Distribuição dos Valores Pagos")

    pizza_pago_rows = []
    pizza_pendente_rows = []

    for contrato in ORDEM_CONTRATOS:
        linha = resumo[resumo["contrato"] == contrato]
        if linha.empty:
            continue

        valor_pago = float(linha["valor_pago"].iloc[0])
        valor_pendente = float(linha["valor_pendente"].iloc[0])

        label_curto = _label_pizza(contrato)
        cor_contrato = CORES_CONTRATO.get(contrato, COR_TODOS)

        if valor_pago > 0:
            pizza_pago_rows.append({
                "grupo": label_curto,
                "valor": valor_pago,
                "ordem": _ordem_contrato(contrato),
                "cor": cor_contrato,
            })

        if valor_pendente > 0:
            pizza_pendente_rows.append({
                "grupo": label_curto,
                "valor": valor_pendente,
                "ordem": _ordem_contrato(contrato),
                "cor": cor_contrato,
            })

    pizza_pago_df = pd.DataFrame(pizza_pago_rows)
    pizza_pendente_df = pd.DataFrame(pizza_pendente_rows)

    if pizza_pago_df.empty:
        st.info("Não há valores pagos suficientes para montar o gráfico de pizza.")
    else:
        pizza_pago_df = pizza_pago_df.sort_values("ordem").reset_index(drop=True)

        fig_pizza_pago = go.Figure(
            data=[
                go.Pie(
                    labels=pizza_pago_df["grupo"],
                    values=pizza_pago_df["valor"],
                    marker=dict(colors=pizza_pago_df["cor"]),
                    sort=False,
                    direction="clockwise",
                    customdata=[brl(v) for v in pizza_pago_df["valor"]],
                    hovertemplate="%{label}<br>Valor Pago: %{customdata}<extra></extra>",
                )
            ]
        )

        fig_pizza_pago.update_layout(
            height=320,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.10,
                xanchor="center",
                x=0.5,
                traceorder="normal",
                font=dict(size=15),
                itemwidth=30,
            ),
            margin=dict(t=20, b=80, l=10, r=10)
        )

        st.plotly_chart(fig_pizza_pago, use_container_width=True)

    _titulo_centralizado("Distribuição dos Valores Pendentes")

    if pizza_pendente_df.empty:
        st.info("Não há valores pendentes suficientes para montar o gráfico de pizza.")
    else:
        pizza_pendente_df = pizza_pendente_df.sort_values("ordem").reset_index(drop=True)

        fig_pizza_pendente = go.Figure(
            data=[
                go.Pie(
                    labels=pizza_pendente_df["grupo"],
                    values=pizza_pendente_df["valor"],
                    marker=dict(colors=pizza_pendente_df["cor"]),
                    sort=False,
                    direction="clockwise",
                    customdata=[brl(v) for v in pizza_pendente_df["valor"]],
                    hovertemplate="%{label}<br>Valor Pendente: %{customdata}<extra></extra>",
                )
            ]
        )

        fig_pizza_pendente.update_layout(
            height=320,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.10,
                xanchor="center",
                x=0.5,
                traceorder="normal",
                font=dict(size=15),
                itemwidth=30,
            ),
            margin=dict(t=20, b=80, l=10, r=10)
        )

        st.plotly_chart(fig_pizza_pendente, use_container_width=True)