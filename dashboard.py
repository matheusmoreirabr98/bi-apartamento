# dashboard.py

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TAXAS,
    brl,
    card_html,
    render_cards_grid,
)

CORES_CONTRATO = {
    "Sinal": "#6600c5",
    "Sinal Ato": "#c084fc",
    "Diferença": "#f59e0b",
    "Evolução de Obra": "#06b6d4",
    "Taxas Cartoriais": "#d4c300",
    "Entrada Direcional": "#56c718",
    "Financiamento Caixa": "#ef4444",
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

def inject_styles():
    st.markdown("""
    <style>
    /* centraliza a barra de ícones do plotly */
    .js-plotly-plot .plotly .modebar {
        left: 50% !important;
        transform: translateX(-50%) !important;
        right: auto !important;
        top: -8px !important;
    }

    /* reduz espaço entre ícones e gráfico */
    .js-plotly-plot {
        padding-top: 0 !important;
    }

    .stPlotlyChart {
        margin-top: -10px !important;
        margin-bottom: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# ESTILO LEGENDAS E PROGRESSO
# =========================================================

def _titulo_centralizado(texto):
    st.markdown(
        f"""
        <div style="
            text-align: center;
            font-size: 20px;
            font-weight: 700;
            margin: 25px 0 12px 0;
            width: 100%;
            display: block;
        ">
            {texto}
        </div>
        """,
        unsafe_allow_html=True,
    )

def _aplicar_estilo_legenda_abaixo(fig, tipo="linha"):
    if tipo == "pizza":
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.10,
                xanchor="center",
                x=0.5,
                traceorder="normal",
                font=dict(size=15),
                itemwidth=30,
                title_text="",
            ),
            margin=dict(t=20, b=80, l=10, r=10),
        )
    else:
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.20,
                xanchor="center",
                x=0.5,
                traceorder="normal",
                font=dict(size=15),
                title_text="",
            ),
            margin=dict(t=5, b=140, l=10, r=10),
        )


def _render_barra_progresso_custom(progresso_pct, cor="#23d400"):
    progresso_pct = max(0.0, min(float(progresso_pct or 0), 100.0))

    texto_interno = f"{progresso_pct:.2f}%"

    html = f"""
    <div style="margin:6px 0 14px 0;">
        <div style="
            width:100%;
            height:22px;
            background:#e9ecef;
            border-radius:999px;
            overflow:hidden;
            position:relative;
        ">
            <div style="
                width:{progresso_pct:.2f}%;
                min-width:52px;
                height:100%;
                background:{cor};
                border-radius:999px;
                display:flex;
                align-items:center;
                justify-content:center;
                color:white;
                font-size:12px;
                font-weight:700;
                white-space:nowrap;
                padding:0 8px;
                box-sizing:border-box;
            ">{texto_interno}</div>
        </div>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


def _is_evolucao_obra(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return contrato in ["evolução de obra", "evolucao de obra"]


def _is_entrada_direcional(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return (
        contrato == str(CONTRATO_DIRECIONAL).strip().lower()
        or contrato == "entrada direcional"
    )


def _is_direcional(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return (
        contrato == "diferença"
        or contrato == "diferenca"
        or "diferen" in contrato
    )


def _is_sinal_ato(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return (
        contrato == "sinal ato"
        or contrato == "ato"
        or contrato.startswith("ato ")
        or contrato.startswith("sinal ato")
    )


def _is_financiamento_caixa(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return "financiamento caixa" in contrato


def _is_taxas_cartorio(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    contrato_taxas = str(CONTRATO_TAXAS).strip().lower()
    return (
        contrato == contrato_taxas
        and not _is_sinal_ato(valor_contrato)
        and not _is_financiamento_caixa(valor_contrato)
    )

def _cor_por_contrato(valor_contrato):
    contrato = str(valor_contrato).strip().lower()

    if contrato == "sinal":
        return CORES_CONTRATO["Sinal"]

    if _is_sinal_ato(valor_contrato):
        return CORES_CONTRATO["Sinal Ato"]

    if _is_direcional(valor_contrato):
        return CORES_CONTRATO["Diferença"]

    if _is_evolucao_obra(valor_contrato):
        return CORES_CONTRATO["Evolução de Obra"]

    if _is_entrada_direcional(valor_contrato):
        return CORES_CONTRATO["Entrada Direcional"]

    if _is_financiamento_caixa(valor_contrato):
        return CORES_CONTRATO["Financiamento Caixa"]

    if _is_taxas_cartorio(valor_contrato):
        return CORES_CONTRATO["Taxas Cartoriais"]

    return "#185bc7"

CORES_RESPONSAVEL = {
    "Pendente": "#d4d4d4",
}

COR_PENDENTE_GRAFICO = CORES_RESPONSAVEL["Pendente"]
COR_PAGO_CORRETORA = "#ef4444"

def _render_mensagem_contrato_encerrado(texto, cor):
    st.markdown(
        f"""
        <div style="
            background: {cor}20;
            border: 1px solid {cor};
            color: {cor};
            padding: 12px 16px;
            border-radius: 10px;
            font-weight: 700;
            text-align: center;
            margin: 6px 0 14px 0;
        ">
            ✅ {texto}
        </div>
        """,
        unsafe_allow_html=True,
    )

def _formatar_mes_pt(coluna_mes_ordem):
    datas_mes = pd.to_datetime(coluna_mes_ordem, format="%Y-%m", errors="coerce")
    return datas_mes.dt.month.map(MAPA_MESES) + "/" + datas_mes.dt.year.astype(str)

def _nome_mes_por_data(valor_data):
    data_ref = pd.to_datetime(valor_data, errors="coerce", dayfirst=True)
    if pd.isnull(data_ref):
        return "-"
    nomes = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    return nomes.get(data_ref.month, "-")


def _referencia_mes_ano(valor_data):
    data_ref = pd.to_datetime(valor_data, errors="coerce", dayfirst=True)
    if pd.isnull(data_ref):
        return "-"
    return f"{MAPA_MESES[data_ref.month]}/{data_ref.year}"


def _texto_parcela(row, somente_numero=False):
    num = int(row["numero_parcela"]) if pd.notnull(row.get("numero_parcela")) else 0

    if somente_numero:
        return f"{num}"

    total = int(row["total_parcelas"]) if pd.notnull(row.get("total_parcelas")) else 0
    return f"{num}/{total}"

def _configurar_eixo_y_valor(fig, faixa_max, passo=1000):
    faixa_max = max(float(faixa_max or 0), float(passo))
    topo = ((int(faixa_max) + passo - 1) // passo) * passo

    tickvals = list(range(0, topo + passo, passo))
    ticktext = ["0"] + [f"{int(v/1000)}k" for v in tickvals[1:]]

    fig.update_layout(
        yaxis=dict(
            range=[0, topo],
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            fixedrange=True,
        )
    )

def _normalizar_texto_serie(valor):
    if pd.isnull(valor):
        return ""
    return str(valor).strip().lower()


def _to_datetime_br(coluna):
    return pd.to_datetime(coluna, errors="coerce", dayfirst=True)


def _to_numeric_brl(coluna):
    if isinstance(coluna, pd.Series):
        if pd.api.types.is_numeric_dtype(coluna):
            return coluna.fillna(0)

        return (
            coluna.astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .replace(["", "nan", "None"], pd.NA)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    if pd.isna(coluna):
        return 0.0

    if isinstance(coluna, (int, float)):
        return float(coluna)

    texto = str(coluna).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except Exception:
        return 0.0


def _calcular_total_parcelas_base(df):
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


def _calcular_progresso_percentual_qtd(qtd_pagas, total_parcelas):
    total = int(total_parcelas or 0)
    pagas = int(qtd_pagas or 0)

    if total <= 0:
        return 0.0

    return (pagas / total) * 100


def _eh_parcela_direcional_paga(row):
    serie = _normalizar_texto_serie(row.get("serie"))
    num = pd.to_numeric(row.get("numero_parcela"), errors="coerce")
    total = pd.to_numeric(row.get("total_parcelas"), errors="coerce")

    if pd.isna(num):
        return False

    num = int(num)
    total = int(total) if pd.notnull(total) else None

    if "conf.div" not in serie and "carnê" not in serie and "carne" not in serie:
        return str(row.get("status", "")).strip().lower() == "pago"

    if total == 14 and 1 <= num <= 10:
        return True

    if total == 43 and num in [42, 43]:
        return True

    return False


def _aplicar_regra_direcional(df):
    if df.empty:
        df = df.copy()
        df["pago_calc"] = False
        df["pendente_calc"] = False
        return df

    df = df.copy()
    df["pago_calc"] = df.apply(_eh_parcela_direcional_paga, axis=1)
    df["pendente_calc"] = ~df["pago_calc"]
    return df


def _filtrar_base_entrada_direcional(df):
    if df.empty:
        return df.copy()

    base = df.copy()

    if "serie" in base.columns:
        serie_norm = base["serie"].apply(_normalizar_texto_serie)
        mask = serie_norm.str.contains("conf.div", na=False) & (
            serie_norm.str.contains("carnê", na=False) | serie_norm.str.contains("carne", na=False)
        )
        filtrado = base[mask].copy()
        if not filtrado.empty:
            return filtrado

    return base.copy()


def _calcular_desconto_entrada_direcional(df):
    if df.empty:
        return 0.0

    base = df.copy()

    if "pago_calc" not in base.columns:
        base = _aplicar_regra_direcional(base)

    base = base[base["pago_calc"]].copy()
    if base.empty:
        return 0.0

    principal = _to_numeric_brl(base["valor_principal"]) if "valor_principal" in base.columns else pd.Series(0, index=base.index)
    pago = _to_numeric_brl(base["valor_pago"]) if "valor_pago" in base.columns else pd.Series(0, index=base.index)

    desconto = (principal - pago).clip(lower=0).sum()
    return float(desconto)


def _eh_taxas_banco(row) -> bool:
    serie = _normalizar_texto_serie(row.get("serie"))
    descricao = _normalizar_texto_serie(row.get("descricao_parcela"))

    return (
        "taxas banco" in serie
        or "taxas banco" in descricao
    )


def _eh_taxas_c(row) -> bool:
    serie = _normalizar_texto_serie(row.get("serie"))
    descricao = _normalizar_texto_serie(row.get("descricao_parcela"))

    return (
        ("taxas c" in serie and "taxas banco" not in serie)
        or ("taxas c" in descricao and "taxas banco" not in descricao)
    )


def _responsavel_taxas_cartorio(row) -> str:
    if _eh_taxas_banco(row):
        return "Corretora"
    if _eh_taxas_c(row):
        return "Compradores"

    valor_resp = str(row.get("responsavel_pagamento", "")).strip().title()
    if valor_resp in ["Compradores", "Corretora"]:
        return valor_resp

    return ""


def _eh_parcela_taxas_cartorio_paga(row) -> bool:
    num = pd.to_numeric(row.get("numero_parcela"), errors="coerce")
    total = pd.to_numeric(row.get("total_parcelas"), errors="coerce")

    if pd.isna(num):
        return False

    num = int(num)
    total = int(total) if pd.notnull(total) else None

    if _eh_taxas_banco(row):
        if total == 8 and 1 <= num <= 8:
            return True
        return False

    if _eh_taxas_c(row):
        if total == 40 and ((1 <= num <= 16) or num in [39, 40]):
            return True
        return False

    return str(row.get("status", "")).strip().lower() == "pago"


def _aplicar_regra_taxas_cartorio(df):
    if df.empty:
        df = df.copy()
        df["responsavel_calc"] = ""
        df["pago_calc"] = False
        df["pendente_calc"] = False
        return df

    df = df.copy()
    df["responsavel_calc"] = df.apply(_responsavel_taxas_cartorio, axis=1)
    df["pago_calc"] = df.apply(_eh_parcela_taxas_cartorio_paga, axis=1)
    df["pendente_calc"] = ~df["pago_calc"]
    return df


def _filtrar_base_taxas_cartorio(df, somente_compradores=False):
    if df.empty:
        return df.copy()

    base = df.copy()

    if "serie" in base.columns:
        mask_taxas_banco = base.apply(_eh_taxas_banco, axis=1)
        mask_taxas_c = base.apply(_eh_taxas_c, axis=1)

        if somente_compradores:
            filtrado = base[mask_taxas_c].copy()
        else:
            filtrado = base[mask_taxas_banco | mask_taxas_c].copy()

        if not filtrado.empty:
            return filtrado

    if "responsavel_pagamento" in base.columns:
        resp = (
            base["responsavel_pagamento"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        if somente_compradores:
            filtrado = base[resp == "Compradores"].copy()
        else:
            filtrado = base[resp.isin(["Compradores", "Corretora"])].copy()

        if not filtrado.empty:
            return filtrado

    return base.copy()


def _calcular_desconto_taxas_cartorio(df):
    if df.empty:
        return 0.0

    base = df.copy()

    if "pago_calc" not in base.columns:
        base = _aplicar_regra_taxas_cartorio(base)

    base = base[base["pago_calc"]].copy()
    if base.empty:
        return 0.0

    principal = _to_numeric_brl(base["valor_principal"]) if "valor_principal" in base.columns else pd.Series(0, index=base.index)
    pago = _to_numeric_brl(base["valor_pago"]) if "valor_pago" in base.columns else pd.Series(0, index=base.index)

    desconto = (principal - pago).clip(lower=0).sum()
    return float(desconto)


def _aplicar_regra_financiamento_caixa(df):
    if df.empty:
        df = df.copy()
        df["pago_calc"] = False
        df["pendente_calc"] = False
        df["atrasado_calc"] = False
        df["aberta_calc"] = False
        df["regime_iniciado"] = False
        df["data_vencimento_calc"] = pd.NaT
        return df

    base = df.copy()

    status_norm = (
        base["status"].astype(str).str.strip().str.lower()
        if "status" in base.columns
        else pd.Series("", index=base.index)
    )

    base["data_pagamento_ref"] = _to_datetime_br(base["data_pagamento"]) if "data_pagamento" in base.columns else pd.NaT
    base["data_vencimento_ref"] = _to_datetime_br(base["data_vencimento"]) if "data_vencimento" in base.columns else pd.NaT
    base["numero_parcela_num"] = pd.to_numeric(base.get("numero_parcela"), errors="coerce")

    base["pago_calc"] = status_norm.eq("pago") | base["data_pagamento_ref"].notna()

    pagas_validas = base[
        base["pago_calc"]
        & base["data_pagamento_ref"].notna()
        & base["numero_parcela_num"].notna()
    ].copy()

    if pagas_validas.empty:
        base["regime_iniciado"] = False
        base["data_vencimento_calc"] = pd.NaT
        base["aberta_calc"] = False
        base["pendente_calc"] = False
        base["atrasado_calc"] = False
        return base

    primeira_paga = (
        pagas_validas
        .sort_values(["data_pagamento_ref", "numero_parcela_num"])
        .iloc[0]
    )

    numero_base = int(primeira_paga["numero_parcela_num"])
    data_base_pagamento = primeira_paga["data_pagamento_ref"]
    data_base_mes = pd.Timestamp(year=data_base_pagamento.year, month=data_base_pagamento.month, day=1)

    dia_venc = 10
    if pd.notnull(primeira_paga.get("data_vencimento_ref")):
        dia_venc = max(1, min(int(primeira_paga["data_vencimento_ref"].day), 28))
    elif base["data_vencimento_ref"].notna().any():
        dia_venc = max(1, min(int(base.loc[base["data_vencimento_ref"].notna(), "data_vencimento_ref"].iloc[0].day), 28))

    def _calc_data_venc(row):
        num = pd.to_numeric(row.get("numero_parcela"), errors="coerce")
        if pd.isna(num):
            return pd.NaT
        offset = int(num) - numero_base
        data_calc = data_base_mes + pd.DateOffset(months=offset)
        return data_calc.replace(day=dia_venc)

    base["data_vencimento_calc"] = base.apply(_calc_data_venc, axis=1)
    base["regime_iniciado"] = True

    hoje = pd.Timestamp.today().normalize()

    base["aberta_calc"] = ~base["pago_calc"]
    base["atrasado_calc"] = (
        base["aberta_calc"]
        & base["data_vencimento_calc"].notna()
        & (base["data_vencimento_calc"] < hoje)
    )
    base["pendente_calc"] = base["aberta_calc"] & ~base["atrasado_calc"]

    return base

def render_dashboard(parcelas_contrato, parcelas_contagem, contrato_selecionado):
    inject_styles()
    contrato_direcional = str(CONTRATO_DIRECIONAL).strip().lower()

    eh_entrada_direcional = _is_entrada_direcional(contrato_selecionado)
    eh_direcional = _is_direcional(contrato_selecionado)
    eh_sinal_ato = _is_sinal_ato(contrato_selecionado)
    eh_financiamento_caixa = _is_financiamento_caixa(contrato_selecionado)
    eh_taxas_cartorio = _is_taxas_cartorio(contrato_selecionado)
    eh_taxas = eh_sinal_ato or eh_financiamento_caixa or eh_taxas_cartorio
    eh_evolucao_obra = _is_evolucao_obra(contrato_selecionado)

    cor_contrato_atual = _cor_por_contrato(contrato_selecionado)

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

    if "serie" in parcelas_contrato.columns:
        parcelas_contrato["serie"] = parcelas_contrato["serie"].astype(str).str.strip()

    if "serie" in parcelas_contagem.columns:
        parcelas_contagem["serie"] = parcelas_contagem["serie"].astype(str).str.strip()

    if eh_entrada_direcional:
        parcelas_base = _filtrar_base_entrada_direcional(parcelas_contrato)
        contagem_base = _filtrar_base_entrada_direcional(parcelas_contagem)

    elif eh_financiamento_caixa:
        parcelas_base = parcelas_contrato.copy()
        contagem_base = parcelas_contagem.copy()

    elif eh_taxas_cartorio:
        parcelas_base = _filtrar_base_taxas_cartorio(parcelas_contrato, somente_compradores=True)
        contagem_base = _filtrar_base_taxas_cartorio(parcelas_contagem, somente_compradores=True)

    elif eh_taxas:
        if "responsavel_pagamento" in parcelas_contrato.columns:
            parcelas_base = parcelas_contrato[
                parcelas_contrato["responsavel_pagamento"] == "Compradores"
            ].copy()
        else:
            parcelas_base = parcelas_contrato.copy()

        if "responsavel_pagamento" in parcelas_contagem.columns:
            contagem_base = parcelas_contagem[
                parcelas_contagem["responsavel_pagamento"] == "Compradores"
            ].copy()
        else:
            contagem_base = parcelas_contagem.copy()

    else:
        parcelas_base = parcelas_contrato.copy()
        contagem_base = parcelas_contagem.copy()

    # =========================================================
    # CÁLCULOS
    # =========================================================
    if eh_entrada_direcional:
        parcelas_base = _aplicar_regra_direcional(parcelas_base)
        contagem_base = _aplicar_regra_direcional(contagem_base)

        valor_pago_col = _to_numeric_brl(parcelas_base["valor_pago"])
        valor_total_col = _to_numeric_brl(parcelas_base["valor_total"])

        total_pago_geral = valor_pago_col[parcelas_base["pago_calc"]].sum()
        total_restante = valor_total_col[parcelas_base["pendente_calc"]].sum()
        total_geral = valor_total_col.sum()

        total_pago_qtd = int(parcelas_base["pago_calc"].sum())
        total_pendente_qtd = int(parcelas_base["pendente_calc"].sum())
        total_atrasado_qtd = 0

        total_pago_compradores = 0
        total_pago_corretora = 0
        total_restante_compradores = 0
        total_restante_corretora = 0

    elif eh_direcional:
        parcelas_base = _aplicar_regra_direcional(parcelas_base)
        contagem_base = _aplicar_regra_direcional(contagem_base)

        total_pago_geral = _to_numeric_brl(parcelas_base.loc[
            parcelas_base["pago_calc"], "valor_pago"
        ]).sum()

        total_restante = _to_numeric_brl(parcelas_base.loc[
            parcelas_base["pendente_calc"], "valor_total"
        ]).sum()

        total_geral = _to_numeric_brl(parcelas_base["valor_total"]).sum()

        total_pago_qtd = int(parcelas_base["pago_calc"].sum())
        total_pendente_qtd = int(parcelas_base["pendente_calc"].sum())
        total_atrasado_qtd = 0

        total_pago_compradores = 0
        total_pago_corretora = 0
        total_restante_compradores = 0
        total_restante_corretora = 0

    elif eh_financiamento_caixa:
        parcelas_base = _aplicar_regra_financiamento_caixa(parcelas_base)
        contagem_base = _aplicar_regra_financiamento_caixa(contagem_base)

        valor_pago_col = _to_numeric_brl(parcelas_base["valor_pago"]) if "valor_pago" in parcelas_base.columns else pd.Series(0, index=parcelas_base.index)
        valor_total_col = _to_numeric_brl(parcelas_base["valor_total"]) if "valor_total" in parcelas_base.columns else pd.Series(0, index=parcelas_base.index)

        regime_iniciado = bool(parcelas_base["regime_iniciado"].any()) if "regime_iniciado" in parcelas_base.columns else False

        total_pago_geral = valor_pago_col[parcelas_base["pago_calc"]].sum()
        total_geral = valor_total_col.sum()

        if regime_iniciado:
            total_restante = valor_total_col[parcelas_base["aberta_calc"]].sum()
            total_pago_qtd = int(parcelas_base["pago_calc"].sum())
            total_pendente_qtd = int(parcelas_base["pendente_calc"].sum())
            total_atrasado_qtd = int(parcelas_base["atrasado_calc"].sum())
        else:
            total_restante = 0.0
            total_pago_qtd = 0
            total_pendente_qtd = 0
            total_atrasado_qtd = 0

        total_pago_compradores = total_pago_geral
        total_pago_corretora = 0
        total_restante_compradores = total_restante
        total_restante_corretora = 0

    elif eh_taxas_cartorio:
        base_taxas_todas = _filtrar_base_taxas_cartorio(parcelas_contrato, somente_compradores=False)
        base_taxas_todas = _aplicar_regra_taxas_cartorio(base_taxas_todas)

        contagem_base = _aplicar_regra_taxas_cartorio(contagem_base)

        valor_pago_col = _to_numeric_brl(base_taxas_todas["valor_pago"])
        valor_total_col = _to_numeric_brl(base_taxas_todas["valor_total"])

        total_pago_compradores = valor_pago_col[
            base_taxas_todas["pago_calc"] & (base_taxas_todas["responsavel_calc"] == "Compradores")
        ].sum()

        total_pago_corretora = valor_pago_col[
            base_taxas_todas["pago_calc"] & (base_taxas_todas["responsavel_calc"] == "Corretora")
        ].sum()

        total_restante_compradores = valor_total_col[
            base_taxas_todas["pendente_calc"] & (base_taxas_todas["responsavel_calc"] == "Compradores")
        ].sum()

        total_restante_corretora = valor_total_col[
            base_taxas_todas["pendente_calc"] & (base_taxas_todas["responsavel_calc"] == "Corretora")
        ].sum()

        total_pago_geral = total_pago_compradores + total_pago_corretora
        total_restante = total_restante_compradores + total_restante_corretora
        total_geral = valor_total_col.sum()

        total_pago_qtd = int(contagem_base["pago_calc"].sum())
        total_pendente_qtd = int(contagem_base["pendente_calc"].sum())
        total_atrasado_qtd = 0

    else:
        total_pago_geral = _to_numeric_brl(parcelas_base.loc[
            parcelas_base["status"] == "pago", "valor_pago"
        ]).sum()

        if "responsavel_pagamento" in parcelas_contrato.columns:
            total_pago_compradores = _to_numeric_brl(parcelas_contrato.loc[
                (parcelas_contrato["status"] == "pago")
                & (parcelas_contrato["responsavel_pagamento"] == "Compradores"),
                "valor_pago",
            ]).sum()

            total_pago_corretora = _to_numeric_brl(parcelas_contrato.loc[
                (parcelas_contrato["status"] == "pago")
                & (parcelas_contrato["responsavel_pagamento"] == "Corretora"),
                "valor_pago",
            ]).sum()
        else:
            total_pago_compradores = 0
            total_pago_corretora = 0

        total_restante = _to_numeric_brl(parcelas_base.loc[
            parcelas_base["status"] != "pago", "valor_total"
        ]).sum()

        total_geral = _to_numeric_brl(parcelas_base["valor_total"]).sum()

        total_pago_qtd = int((contagem_base["status"] == "pago").sum())
        total_pendente_qtd = int((contagem_base["status_exibicao"] == "pendente").sum()) if "status_exibicao" in contagem_base.columns else 0
        total_atrasado_qtd = int((contagem_base["status_exibicao"] == "atrasado").sum()) if "status_exibicao" in contagem_base.columns else 0

        total_restante_compradores = 0
        total_restante_corretora = 0

    total_parcelas_calc = _calcular_total_parcelas_base(contagem_base)

    progresso_pct = _calcular_progresso_percentual_qtd(
        total_pago_qtd,
        total_parcelas_calc,
    )

    contrato_encerrado = False
    if eh_evolucao_obra and "contrato_encerrado" in parcelas_contrato.columns:
        contrato_encerrado = parcelas_contrato["contrato_encerrado"].fillna(False).astype(bool).any()

    # =========================================================
    # CARDS
    # =========================================================

    _render_barra_progresso_custom(progresso_pct, cor=cor_contrato_atual)

    if eh_sinal_ato:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
            card_html("Valor Pendente", brl(total_restante), small=True),
            card_html("Total Geral", brl(total_geral), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_financiamento_caixa:
        total_desconto_obtido = (
            _to_numeric_brl(parcelas_base.loc[parcelas_base["pago_calc"], "valor_total"]).sum()
            - _to_numeric_brl(parcelas_base.loc[parcelas_base["pago_calc"], "valor_pago"]).sum()
        )

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
            card_html("Pendente Estimado", brl(total_restante), small=True),
            card_html("Total Estimado", brl(total_geral), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Desconto Obtido", brl(total_desconto_obtido), small=True),
        ], cols=1)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_taxas_cartorio:
        total_desconto_obtido = _calcular_desconto_taxas_cartorio(base_taxas_todas)

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
            card_html("Pendente Estimado", brl(total_restante), small=True),
            card_html("Total Estimado", brl(total_geral), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Valor Pago - Compradores", brl(total_pago_compradores), small=True),
            card_html("Valor Pago - Corretora", brl(total_pago_corretora), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Desconto Obtido", brl(total_desconto_obtido), small=True),
        ], cols=1)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_entrada_direcional:
        total_desconto_obtido = _calcular_desconto_entrada_direcional(parcelas_base)

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
            card_html("Pendente Estimado", brl(total_restante), small=True),
            card_html("Total Estimado", brl(total_geral), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Desconto Obtido", brl(total_desconto_obtido), small=True),
        ], cols=1)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_direcional:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
            card_html("Valor Pendente", brl(total_restante), small=True),
            card_html("Total Geral", brl(total_geral), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_evolucao_obra:
        proxima_parcela_pendente_mes = "-"
        abertas_evolucao = contagem_base[contagem_base["status"] != "pago"].copy()
        if not abertas_evolucao.empty:
            abertas_evolucao["data_venc_ref"] = _to_datetime_br(abertas_evolucao["data_vencimento"])
            abertas_evolucao["numero_parcela_ord"] = pd.to_numeric(abertas_evolucao["numero_parcela"], errors="coerce")
            abertas_evolucao = abertas_evolucao.sort_values(["data_venc_ref", "numero_parcela_ord"], na_position="last")
            if not abertas_evolucao.empty:
                proxima_parcela_pendente_mes = _nome_mes_por_data(abertas_evolucao.iloc[0].get("data_vencimento"))

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
        ], cols=1)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcela Pendente", proxima_parcela_pendente_mes, small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    else:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral), small=True),
        ], cols=1)

        render_cards_grid([
            card_html("Pagamento Compradores", brl(total_pago_compradores), small=True),
            card_html("Pagamento Corretora", brl(total_pago_corretora), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Total Geral", brl(total_geral), small=True),
        ], cols=1)

        render_cards_grid([
            card_html("Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Total Restante", brl(total_restante), small=True),
        ], cols=1)

    # =========================================================
    # PRÓXIMA PARCELA
    # =========================================================
    _titulo_centralizado("Próxima Parcela")

    if eh_evolucao_obra and contrato_encerrado:
        _render_mensagem_contrato_encerrado(
            "Evolução de Obra concluída.",
            cor_contrato_atual
        )
    else:
        if eh_financiamento_caixa:
            if "regime_iniciado" in contagem_base.columns and not bool(contagem_base["regime_iniciado"].any()):
                st.info("Aguardando o início do Financiamento Caixa. A contagem das 420 parcelas começará no mês do primeiro pagamento.")
                abertas = pd.DataFrame()
            else:
                abertas = contagem_base[contagem_base["aberta_calc"]].copy()

        elif eh_entrada_direcional or eh_direcional or eh_taxas_cartorio:
            abertas = contagem_base[contagem_base["pendente_calc"]].copy()

        else:
            abertas = contagem_base.copy()
            abertas["pago_calc"] = abertas["status"].astype(str).str.lower().eq("pago")

            mask_direcional = (
                abertas["contrato"].astype(str).str.strip().str.lower() == contrato_direcional
            )

            if mask_direcional.any():
                abertas.loc[mask_direcional, "pago_calc"] = abertas.loc[mask_direcional].apply(
                    _eh_parcela_direcional_paga, axis=1
                )

            abertas = abertas[~abertas["pago_calc"]].copy()

        if abertas.empty:
            if not eh_financiamento_caixa:
                _render_mensagem_contrato_encerrado(
                    "Não há parcelas em aberto.",
                    cor_contrato_atual
                )
        else:
            if eh_financiamento_caixa and "data_vencimento_calc" in abertas.columns:
                proxima_parcela = (
                    abertas.sort_values(["data_vencimento_calc", "numero_parcela_num"], na_position="last")
                    .head(1)
                    .copy()
                )
            else:
                abertas = abertas.copy()
                abertas["data_venc_ref"] = _to_datetime_br(abertas["data_vencimento"])
                abertas["numero_parcela_ord"] = pd.to_numeric(abertas["numero_parcela"], errors="coerce")

                proxima_parcela = (
                    abertas.sort_values(["data_venc_ref", "numero_parcela_ord"], na_position="last")
                    .head(1)
                    .copy()
                )

            prox = proxima_parcela.iloc[0]

            if eh_financiamento_caixa and "data_vencimento_calc" in prox.index:
                data_venc = pd.to_datetime(prox["data_vencimento_calc"], errors="coerce")
            else:
                data_venc = _to_datetime_br(pd.Series([prox["data_vencimento"]])).iloc[0]

            if eh_evolucao_obra:
                render_cards_grid([
                    card_html("Parcela", _texto_parcela(prox, somente_numero=True), small=True),
                    card_html("Referência", _referencia_mes_ano(prox["data_vencimento"]), small=True),
                    card_html(
                        "Vencimento",
                        data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-",
                        small=True,
                    ),
                ], cols=3)
            else:
                render_cards_grid([
                    card_html("Parcela", _texto_parcela(prox), small=True),
                    card_html("Valor", brl(_to_numeric_brl(prox["valor_total"])), small=True),
                    card_html(
                        "Vencimento",
                        data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-",
                        small=True,
                    ),
                ], cols=3)

    # =========================================================
    # EVOLUÇÃO POR MÊS
    # =========================================================
    _titulo_centralizado("Evolução por Mês")

    evolucao_df = parcelas_contrato.copy()

    if "data_pagamento" not in evolucao_df.columns:
        st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")
        return

    # ---------------------------------------------------------
    # ENTRADA DIRECIONAL
    # ---------------------------------------------------------
    if eh_entrada_direcional:
        evolucao_pago = _filtrar_base_entrada_direcional(evolucao_df).copy()
        evolucao_pago["data_pagamento_ref"] = _to_datetime_br(evolucao_pago["data_pagamento"])
        evolucao_pago["valor_pago_num"] = _to_numeric_brl(evolucao_pago["valor_pago"])

        evolucao_pago = evolucao_pago[
            evolucao_pago["data_pagamento_ref"].notna()
            & (evolucao_pago["valor_pago_num"] > 0)
        ].copy()


    # ---------------------------------------------------------
    # DIFERENÇA
    # ---------------------------------------------------------
    elif eh_direcional:

        evolucao_pago = _aplicar_regra_direcional(evolucao_df)

        evolucao_pago["data_pagamento_ref"] = _to_datetime_br(evolucao_pago["data_pagamento"])
        evolucao_pago["valor_pago_num"] = _to_numeric_brl(evolucao_pago["valor_pago"])

        evolucao_pago = evolucao_pago[
            (evolucao_pago["pago_calc"])
            & (evolucao_pago["data_pagamento_ref"].notna())
        ].copy()


    # ---------------------------------------------------------
    # FINANCIAMENTO CAIXA
    # ---------------------------------------------------------
    elif eh_financiamento_caixa:

        evolucao_fc = _aplicar_regra_financiamento_caixa(evolucao_df)

        evolucao_fc["data_pagamento_ref"] = _to_datetime_br(evolucao_fc["data_pagamento"])
        evolucao_fc["valor_pago_num"] = _to_numeric_brl(evolucao_fc["valor_pago"])

        evolucao_pago = evolucao_fc[
            (evolucao_fc["pago_calc"])
            & (evolucao_fc["data_pagamento_ref"].notna())
        ].copy()

        if evolucao_pago.empty:
            st.info("O Financiamento Caixa ainda não foi iniciado. A evolução mensal aparecerá a partir do primeiro pagamento.")
            return


    # ---------------------------------------------------------
    # TAXAS CARTORIAIS
    # ---------------------------------------------------------
    elif eh_taxas_cartorio:

        evolucao_taxas = _filtrar_base_taxas_cartorio(evolucao_df, somente_compradores=False)
        evolucao_taxas = _aplicar_regra_taxas_cartorio(evolucao_taxas)

        evolucao_taxas["data_pagamento_ref"] = _to_datetime_br(evolucao_taxas["data_pagamento"])
        evolucao_taxas["valor_pago_num"] = _to_numeric_brl(evolucao_taxas["valor_pago"])

        evolucao_pago = evolucao_taxas[
            (evolucao_taxas["pago_calc"])
            & (evolucao_taxas["data_pagamento_ref"].notna())
            & (evolucao_taxas["responsavel_calc"].isin(["Compradores", "Corretora"]))
        ].copy()


    # ---------------------------------------------------------
    # EVOLUÇÃO DE OBRA
    # ---------------------------------------------------------
    elif eh_evolucao_obra:

        evolucao_pago = evolucao_df.copy()

        evolucao_pago["data_pagamento_ref"] = _to_datetime_br(evolucao_pago["data_pagamento"])
        evolucao_pago["valor_pago_num"] = _to_numeric_brl(evolucao_pago["valor_pago"])

        evolucao_pago = evolucao_pago[
            (evolucao_pago["status"] == "pago")
            & (evolucao_pago["data_pagamento_ref"].notna())
        ].copy()


    # ---------------------------------------------------------
    # CONTRATOS PADRÃO
    # ---------------------------------------------------------
    else:

        if "responsavel_pagamento" not in evolucao_df.columns:
            st.info("Não há informação de responsável de pagamento para mostrar a evolução mensal.")
            return

        evolucao_df["responsavel_pagamento"] = (
            evolucao_df["responsavel_pagamento"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        evolucao_df["data_pagamento_ref"] = _to_datetime_br(evolucao_df["data_pagamento"])
        evolucao_df["valor_pago_num"] = _to_numeric_brl(evolucao_df["valor_pago"])

        evolucao_pago = evolucao_df[
            (evolucao_df["status"] == "pago")
            & (evolucao_df["data_pagamento_ref"].notna())
            & (evolucao_df["responsavel_pagamento"].isin(["Compradores", "Corretora"]))
        ].copy()


    # =========================================================
    # SE NÃO HOUVER PAGAMENTOS
    # =========================================================
    if evolucao_pago.empty:
        st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        return


    # =========================================================
    # AGRUPAMENTO MENSAL
    # =========================================================
    evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
    evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

    coluna_responsavel = None

    if eh_taxas_cartorio:
        coluna_responsavel = "responsavel_calc"
    elif (
        not eh_entrada_direcional
        and not eh_direcional
        and not eh_financiamento_caixa
        and not eh_evolucao_obra
        and "responsavel_pagamento" in evolucao_pago.columns
    ):
        coluna_responsavel = "responsavel_pagamento"

    if coluna_responsavel:
        mensal_df = (
            evolucao_pago.groupby(["mes_ordem", coluna_responsavel], as_index=False)
            .agg(
                total_pago=("valor_pago_num", "sum"),
                qtd_parcelas=("valor_pago_num", "size"),
            )
            .sort_values(["mes_ordem", coluna_responsavel])
        )

        ordem_meses = (
            mensal_df[["mes_ordem"]]
            .drop_duplicates()
            .sort_values("mes_ordem")
            .reset_index(drop=True)
        )
        ordem_meses["Mes"] = _formatar_mes_pt(ordem_meses["mes_ordem"])
        ordem_meses["x_pos"] = range(len(ordem_meses))

        fig_mensal = go.Figure()

        for responsavel in ["Compradores", "Corretora"]:
            df_resp = mensal_df[mensal_df[coluna_responsavel] == responsavel].copy()

            if df_resp.empty:
                continue

            if responsavel == "Corretora":
                ultimo_mes_resp = df_resp["mes_ordem"].max()
                ordem_meses_resp = ordem_meses[ordem_meses["mes_ordem"] <= ultimo_mes_resp].copy()
            else:
                ordem_meses_resp = ordem_meses.copy()

            df_resp = ordem_meses_resp.merge(df_resp, on="mes_ordem", how="left")
            df_resp["Mes"] = ordem_meses_resp["Mes"].values
            df_resp["x_pos"] = ordem_meses_resp["x_pos"].values
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
                    f"Parcelas Pagas: {int(qtd)}<br>"
                    f"Valor Pago no Mês: {brl(valor)}"
                )
                for mes, valor, qtd in zip(
                    df_resp["Mes"],
                    df_resp["total_pago"],
                    df_resp["qtd_parcelas"],
                )
            ]

            cor_linha = cor_contrato_atual if responsavel == "Compradores" else COR_PAGO_CORRETORA

            fig_mensal.add_trace(
                go.Scatter(
                    x=df_resp["x_pos"],
                    y=df_resp["total_pago"],
                    mode="lines+markers+text",
                    name=responsavel,
                    text=textos,
                    textposition="top center",
                    textfont={"size": 16},
                    cliponaxis=False,
                    line={"color": cor_linha, "width": 3},
                    marker={
                        "color": cor_linha,
                        "size": 9,
                    },
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=hover_textos,
                )
            )

        faixa_max = mensal_df["total_pago"].max() if not mensal_df.empty else 1000

        _aplicar_estilo_legenda_abaixo(fig_mensal, tipo="linha")

        _configurar_eixo_y_valor(
            fig_mensal,
            float(faixa_max) * 1.2 if faixa_max else 1000,
            1000,
        )

        fig_mensal.update_layout(
            dragmode="pan",
            hovermode="x unified",
            xaxis_title="Mês do Pagamento",
            yaxis_title="Valor Pago",
            legend_title_text="",
            xaxis=dict(
                tickangle=320,
                tickmode="array",
                tickvals=ordem_meses["x_pos"].tolist(),
                ticktext=ordem_meses["Mes"].tolist(),
                range=[-0.5, min(11.5, len(ordem_meses) - 0.5)],
                fixedrange=False,
            ),
        )

    else:
        mensal_df = (
            evolucao_pago.groupby("mes_ordem", as_index=False)
            .agg(
                total_pago=("valor_pago_num", "sum"),
                qtd_parcelas=("valor_pago_num", "size"),
            )
            .sort_values("mes_ordem")
        )

        mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])
        mensal_df = mensal_df.reset_index(drop=True)
        mensal_df["x_pos"] = range(len(mensal_df))

        textos = [
            str(int(qtd)) if qtd > 0 else ""
            for qtd in mensal_df["qtd_parcelas"]
        ]

        hover_textos = [
            (
                f"<b>{mes}</b><br>"
                f"Parcelas Pagas: {int(qtd)}<br>"
                f"Valor Pago no Mês: {brl(valor)}"
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
                x=mensal_df["x_pos"],
                y=mensal_df["total_pago"],
                mode="lines+markers+text",
                name="Valor Pago",
                text=textos,
                textposition="top center",
                textfont={"size": 16},
                cliponaxis=False,
                line={"color": cor_contrato_atual, "width": 3},
                marker={
                    "color": cor_contrato_atual,
                    "size": 9,
                },
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_textos,
            )
        )

        _aplicar_estilo_legenda_abaixo(fig_mensal, tipo="linha")

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
            xaxis=dict(
                tickangle=320,
                tickmode="array",
                tickvals=mensal_df["x_pos"].tolist(),
                ticktext=mensal_df["Mes"].tolist(),
                range=[-0.5, min(11.5, len(mensal_df) - 0.5)],
                fixedrange=False,
            ),
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
                "autoScale2d",
                "toggleSpikelines",
                "zoomIn2d",
                "zoomOut2d",
                "resetScale2d",
                "hoverClosestCartesian",
                "hoverCompareCartesian",
            ],
            "modeBarButtonsToAdd": [
                "fullscreen",
                "toImage"
            ],
        }
    )

    # =========================================================
    # GRÁFICOS DE PIZZA
    # =========================================================
    if not eh_evolucao_obra:
        _titulo_centralizado("Distribuição dos Valores")

        if eh_taxas_cartorio:
            base_pizza = _filtrar_base_taxas_cartorio(parcelas_contrato, somente_compradores=False)
            base_pizza = _aplicar_regra_taxas_cartorio(base_pizza)

            grupos = []

            valor_pago_compradores = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Compradores")
                & (base_pizza["pago_calc"]),
                "valor_pago",
            ]).sum()

            valor_pendente_compradores = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Compradores")
                & (base_pizza["pendente_calc"]),
                "valor_total",
            ]).sum()

            valor_pago_corretora = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Corretora")
                & (base_pizza["pago_calc"]),
                "valor_pago",
            ]).sum()

            valor_pendente_corretora = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Corretora")
                & (base_pizza["pendente_calc"]),
                "valor_total",
            ]).sum()

            if valor_pago_compradores > 0:
                grupos.append({
                    "grupo": "Pago - Compradores",
                    "valor": valor_pago_compradores,
                    "cor": cor_contrato_atual,
                })

            if valor_pendente_compradores > 0:
                grupos.append({
                    "grupo": "Pendente - Compradores",
                    "valor": valor_pendente_compradores,
                    "cor": "#9bdc8d",
                })

            if valor_pago_corretora > 0:
                grupos.append({
                    "grupo": "Pago - Corretora",
                    "valor": valor_pago_corretora,
                    "cor": COR_PAGO_CORRETORA,
                })

            if valor_pendente_corretora > 0:
                grupos.append({
                    "grupo": "Pendente - Corretora",
                    "valor": valor_pendente_corretora,
                    "cor": "#f5a3a3",
                })

            pizza_df = pd.DataFrame(grupos)

        else:
            grupos = []

            if total_pago_geral > 0:
                grupos.append({
                    "grupo": "Pago",
                    "valor": total_pago_geral,
                    "cor": cor_contrato_atual,
                })

            if total_restante > 0:
                grupos.append({
                    "grupo": "Pendente",
                    "valor": total_restante,
                    "cor": COR_PENDENTE_GRAFICO,
                })

            pizza_df = pd.DataFrame(grupos)

        if not pizza_df.empty:
            fig_pizza = go.Figure(
                data=[
                    go.Pie(
                        labels=pizza_df["grupo"],
                        values=pizza_df["valor"],
                        marker=dict(colors=pizza_df["cor"]),
                        sort=False,
                        direction="clockwise",
                        customdata=[brl(v) for v in pizza_df["valor"]],
                        hovertemplate="%{label}<br>Valor: %{customdata}<extra></extra>",
                    )
                ]
            )

            _aplicar_estilo_legenda_abaixo(fig_pizza, tipo="pizza")
            fig_pizza.update_layout(height=320)

            st.plotly_chart(
                fig_pizza,
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
                        "autoScale2d",
                        "toggleSpikelines",
                        "zoomIn2d",
                        "zoomOut2d",
                        "resetScale2d",
                        "hoverClosestCartesian",
                        "hoverCompareCartesian",
                    ],
                    "modeBarButtonsToAdd": [
                        "fullscreen",
                        "toImage"
                    ],
                }
            )