# dashboard.py
from datetime import date
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

CORES_TAXAS_CARTORIO_PIZZA = {
    "Valor Pago - Compradores": "#56c718",
    "Valor Pendente - Compradores": "#db8181",
    "Valor Pago - Corretora": "#d4c300",
    "Valor Pendente - Corretora": "#eadf8a",
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
        contrato in ["sinal ato", "ato", "sinal"]
        or "sinal" in contrato
        or contrato.startswith("ato")
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


def _formatar_mes_pt(coluna_mes_ordem):
    datas_mes = pd.to_datetime(coluna_mes_ordem, format="%Y-%m", errors="coerce")
    return datas_mes.dt.month.map(MAPA_MESES) + "/" + datas_mes.dt.year.astype(str)


def _mes_nome_atual_pt():
    hoje = date.today()
    return MAPA_MESES.get(hoje.month, "")


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


def _configurar_eixo_y_valor(fig, faixa_max, passo=500):
    faixa_max = max(float(faixa_max or 0), float(passo))
    topo = ((int(faixa_max) + passo - 1) // passo) * passo

    tickvals = list(range(0, topo + passo, passo))
    ticktext = [brl(v) for v in tickvals]

    fig.update_layout(
        yaxis=dict(
            range=[0, topo],
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
        )
    )


def _configurar_eixo_y_quantidade(fig, max_qtd):
    fig.update_layout(
        yaxis=dict(
            range=[0, max(1, max_qtd + 1)],
            dtick=1,
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
    contrato_sel = str(contrato_selecionado).strip().lower()
    contrato_direcional = str(CONTRATO_DIRECIONAL).strip().lower()
    contrato_todos = str(CONTRATO_TODOS).strip().lower()

    eh_entrada_direcional = _is_entrada_direcional(contrato_selecionado)
    eh_direcional = _is_direcional(contrato_selecionado)
    eh_sinal_ato = _is_sinal_ato(contrato_selecionado)
    eh_financiamento_caixa = _is_financiamento_caixa(contrato_selecionado)
    eh_taxas_cartorio = _is_taxas_cartorio(contrato_selecionado)

    eh_taxas = eh_sinal_ato or eh_financiamento_caixa or eh_taxas_cartorio
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
    if eh_sinal_ato:
        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
            card_html("Progresso", f"{progresso_pct:.2f}%"),
        ], cols=2)

        render_cards_grid([
            card_html("Valor Pendente", brl(total_restante), small=True),
            card_html("Total Geral", brl(total_geral), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_financiamento_caixa:
        total_desconto_obtido = (
            _to_numeric_brl(parcelas_base.loc[parcelas_base["pago_calc"], "valor_total"]).sum()
            - _to_numeric_brl(parcelas_base.loc[parcelas_base["pago_calc"], "valor_pago"]).sum()
        )

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
            card_html("Progresso", f"{progresso_pct:.2f}%"),
        ], cols=2)

        render_cards_grid([
            card_html("Valor Pendente Previsto", brl(total_restante), small=True),
            card_html("Total Previsto", brl(total_geral), small=True),
            card_html("Desconto Obtido", brl(total_desconto_obtido), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_taxas_cartorio:
        total_desconto_obtido = _calcular_desconto_taxas_cartorio(base_taxas_todas)

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
            card_html("Progresso", f"{progresso_pct:.2f}%"),
        ], cols=2)

        render_cards_grid([
            card_html("Valor Pendente Previsto", brl(total_restante), small=True),
            card_html("Total Previsto", brl(total_geral), small=True),
            card_html("Desconto Obtido", brl(total_desconto_obtido), small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Valor Pago - Compradores", brl(total_pago_compradores), small=True),
            card_html("Valor Pago - Corretora", brl(total_pago_corretora), small=True),
        ], cols=2)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_entrada_direcional:
        total_desconto_obtido = _calcular_desconto_entrada_direcional(parcelas_base)

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
            card_html("Progresso", f"{progresso_pct:.2f}%"),
        ], cols=2)

        render_cards_grid([
            card_html("Valor Pendente Previsto", brl(total_restante), small=True),
            card_html("Total Previsto", brl(total_geral), small=True),
            card_html("Desconto Obtido", brl(total_desconto_obtido), small=True),
        ], cols=3)

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
            card_html("Total Geral", brl(total_geral), small=True),
            card_html("Progresso", f"{progresso_pct:.2f}%", small=True),
        ], cols=3)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Quant. Parcelas Pendentes", str(total_pendente_qtd), small=True),
            card_html("Quant. Parcelas Atrasadas", str(total_atrasado_qtd), small=True),
        ], cols=3)

    elif eh_evolucao_obra:
        hoje = pd.Timestamp.today()
        data_venc_ref = _to_datetime_br(contagem_base["data_vencimento"]) if "data_vencimento" in contagem_base.columns else pd.Series(dtype="datetime64[ns]")

        pendente_mes_vigente = contagem_base[
            (contagem_base["status"] != "pago")
            & (data_venc_ref.dt.month == hoje.month)
            & (data_venc_ref.dt.year == hoje.year)
        ].shape[0]

        proxima_parcela_pendente_mes = "-"
        abertas_evolucao = contagem_base[contagem_base["status"] != "pago"].copy()
        if not abertas_evolucao.empty:
            abertas_evolucao["data_venc_ref"] = _to_datetime_br(abertas_evolucao["data_vencimento"])
            abertas_evolucao = abertas_evolucao.sort_values(["data_venc_ref", "numero_parcela"], na_position="last")
            if not abertas_evolucao.empty:
                proxima_parcela_pendente_mes = _nome_mes_por_data(abertas_evolucao.iloc[0].get("data_vencimento"))

        render_cards_grid([
            card_html("Pagamento Total", brl(total_pago_geral)),
            card_html("Progresso", f"{progresso_pct:.2f}%"),
        ], cols=2)

        render_cards_grid([
            card_html("Quant. Parcelas Pagas", str(total_pago_qtd), small=True),
            card_html("Parcela Pendente", proxima_parcela_pendente_mes, small=True),
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
            card_html("Progresso", f"{progresso_pct:.2f}%", small=True),
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
        if eh_financiamento_caixa:
            if "regime_iniciado" in contagem_base.columns and not bool(contagem_base["regime_iniciado"].any()):
                st.info("Aguardando o início do Financiamento Caixa. A contagem das 420 parcelas começará no mês do primeiro pagamento.")
                abertas = pd.DataFrame()
            else:
                abertas = contagem_base[contagem_base["aberta_calc"]].copy()
        elif eh_entrada_direcional or eh_direcional or eh_taxas_cartorio:
            abertas = contagem_base[contagem_base["pendente_calc"]].copy()
        else:
            abertas = contagem_base[contagem_base["status"] != "pago"].copy()

        if abertas.empty:
            if not eh_financiamento_caixa:
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
                    data_venc = _to_datetime_br(pd.Series([row["data_vencimento"]])).iloc[0]

                    _render_quatro_cards_em_linha([
                        card_html("Contrato", CONTRATO_TAXAS, small=True),
                        card_html("Parcela", _texto_parcela(row), small=True),
                        card_html("Valor", brl(_to_numeric_brl(row["valor_total"])), small=True),
                        card_html(
                            "Vencimento",
                            data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-",
                            small=True,
                        ),
                    ])

                if not prox_direcional.empty:
                    row = prox_direcional.iloc[0]
                    data_venc = _to_datetime_br(pd.Series([row["data_vencimento"]])).iloc[0]

                    _render_quatro_cards_em_linha([
                        card_html("Contrato", CONTRATO_DIRECIONAL, small=True),
                        card_html("Parcela", _texto_parcela(row), small=True),
                        card_html("Valor", brl(_to_numeric_brl(row["valor_total"])), small=True),
                        card_html(
                            "Vencimento",
                            data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-",
                            small=True,
                        ),
                    ])

            else:
                if eh_financiamento_caixa and "data_vencimento_calc" in abertas.columns:
                    proxima_parcela = (
                        abertas.sort_values(["data_vencimento_calc", "numero_parcela"])
                        .head(1)
                        .copy()
                    )
                else:
                    proxima_parcela = (
                        abertas.sort_values(["data_vencimento", "numero_parcela"])
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
                        card_html("Referência", _referencia_mes_ano(prox["data_vencimento"]), small=True),
                        card_html("Parcela", _texto_parcela(prox, somente_numero=True), small=True),
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
    st.markdown("### Evolução por Mês")

    evolucao_df = parcelas_contrato.copy()

    if "data_pagamento" not in evolucao_df.columns:
        st.warning("A coluna 'data_pagamento' não foi encontrada para montar a evolução mensal.")
        return

    if eh_todos:
        evolucao_df = evolucao_df[
            evolucao_df["contrato"].isin([CONTRATO_TAXAS, CONTRATO_DIRECIONAL])
        ].copy()

        if "serie" in evolucao_df.columns:
            evolucao_df["serie"] = evolucao_df["serie"].astype(str).str.strip()

        evolucao_df["pago_calc"] = evolucao_df["status"].astype(str).str.lower().eq("pago")
        mask_direcional = evolucao_df["contrato"].astype(str).str.strip().str.lower() == contrato_direcional
        if mask_direcional.any():
            evolucao_df.loc[mask_direcional, "pago_calc"] = evolucao_df.loc[mask_direcional].apply(
                _eh_parcela_direcional_paga, axis=1
            )

        evolucao_df["data_pagamento_ref"] = _to_datetime_br(evolucao_df["data_pagamento"])

        evolucao_df = evolucao_df[
            (evolucao_df["pago_calc"])
            & (evolucao_df["data_pagamento_ref"].notna())
        ].copy()

        if evolucao_df.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_df["serie_grafico"] = evolucao_df["contrato"].map({
                CONTRATO_TAXAS: "Registro",
                CONTRATO_DIRECIONAL: "Entrada",
            })

            evolucao_df["mes_ref"] = evolucao_df["data_pagamento_ref"].dt.to_period("M")
            evolucao_df["mes_ordem"] = evolucao_df["mes_ref"].astype(str)
            evolucao_df["valor_pago_num"] = _to_numeric_brl(evolucao_df["valor_pago"])

            mensal_df = (
                evolucao_df.groupby(["mes_ordem", "serie_grafico"], as_index=False)
                .agg(
                    total_pago=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
                )
                .sort_values(["mes_ordem", "serie_grafico"])
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

            ordem_meses = (
                mensal_df[["mes_ordem", "Mes"]]
                .drop_duplicates()
                .sort_values("mes_ordem")
            )

            fig_mensal = go.Figure()

            for serie in ["Registro", "Entrada"]:
                df_serie = mensal_df[mensal_df["serie_grafico"] == serie].copy()

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
                        f"Faturas Pagas: {int(qtd)}<br>"
                        f"Valor Pago no Mês: {brl(valor)}"
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
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["total_pago"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

    elif eh_entrada_direcional:
        evolucao_pago = _filtrar_base_entrada_direcional(evolucao_df)
        evolucao_pago = _aplicar_regra_direcional(evolucao_pago)
        evolucao_pago["data_pagamento_ref"] = _to_datetime_br(evolucao_pago["data_pagamento"])
        evolucao_pago["valor_pago_num"] = _to_numeric_brl(evolucao_pago["valor_pago"])

        evolucao_pago = evolucao_pago[
            (evolucao_pago["pago_calc"])
            & (evolucao_pago["data_pagamento_ref"].notna())
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby("mes_ordem", as_index=False)
                .agg(
                    valor_pago_mes=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
                )
                .sort_values("mes_ordem")
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

            hover_textos = [
                (
                    f"<b>{mes}</b><br>"
                    f"Quantidade de Parcelas Pagas: {int(qtd)}<br>"
                    f"Valor Pago no Mês: {brl(valor)}"
                )
                for mes, valor, qtd in zip(
                    mensal_df["Mes"],
                    mensal_df["valor_pago_mes"],
                    mensal_df["qtd_parcelas"],
                )
            ]

            textos = [str(int(qtd)) for qtd in mensal_df["qtd_parcelas"]]

            fig_mensal = go.Figure()

            fig_mensal.add_trace(
                go.Scatter(
                    x=mensal_df["Mes"],
                    y=mensal_df["valor_pago_mes"],
                    mode="lines+markers+text",
                    name="Valor Pago",
                    text=textos,
                    textposition="top center",
                    textfont={"size": 12},
                    line={"color": CORES_CONTRATO["Entrada"], "width": 3},
                    marker={
                        "color": CORES_CONTRATO["Entrada"],
                        "size": 9,
                    },
                    customdata=hover_textos,
                    hovertemplate="%{customdata}<extra></extra>",
                )
            )

            fig_mensal.update_layout(
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )

            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["valor_pago_mes"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

    elif eh_direcional:
        evolucao_pago = _aplicar_regra_direcional(evolucao_df)
        evolucao_pago["data_pagamento_ref"] = _to_datetime_br(evolucao_pago["data_pagamento"])
        evolucao_pago["valor_pago_num"] = _to_numeric_brl(evolucao_pago["valor_pago"])

        evolucao_pago = evolucao_pago[
            (evolucao_pago["pago_calc"])
            & (evolucao_pago["data_pagamento_ref"].notna())
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby("mes_ordem", as_index=False)
                .agg(
                    valor_pago_mes=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "count"),
                )
                .sort_values("mes_ordem")
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

            hover_textos = [
                (
                    f"<b>{mes}</b><br>"
                    f"Quantidade de Parcelas Pagas: {int(qtd)}<br>"
                    f"Valor Pago no Mês: {brl(valor)}"
                )
                for mes, valor, qtd in zip(
                    mensal_df["Mes"],
                    mensal_df["valor_pago_mes"],
                    mensal_df["qtd_parcelas"],
                )
            ]

            textos = [str(int(qtd)) for qtd in mensal_df["qtd_parcelas"]]

            fig_mensal = go.Figure()

            fig_mensal.add_trace(
                go.Scatter(
                    x=mensal_df["Mes"],
                    y=mensal_df["valor_pago_mes"],
                    mode="lines+markers+text",
                    name="Valor Pago",
                    text=textos,
                    textposition="top center",
                    textfont={"size": 12},
                    line={"color": CORES_RESPONSAVEL["Pago"], "width": 3},
                    marker={
                        "color": CORES_RESPONSAVEL["Pago"],
                        "size": 9,
                    },
                    customdata=hover_textos,
                    hovertemplate="%{customdata}<extra></extra>",
                )
            )

            fig_mensal.update_layout(
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )

            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["valor_pago_mes"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

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
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby("mes_ordem", as_index=False)
                .agg(
                    valor_pago_mes=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
                )
                .sort_values("mes_ordem")
            )

            mensal_df["Mes"] = _formatar_mes_pt(mensal_df["mes_ordem"])

            hover_textos = [
                (
                    f"<b>{mes}</b><br>"
                    f"Quantidade de Parcelas Pagas: {int(qtd)}<br>"
                    f"Valor Pago no Mês: {brl(valor)}"
                )
                for mes, valor, qtd in zip(
                    mensal_df["Mes"],
                    mensal_df["valor_pago_mes"],
                    mensal_df["qtd_parcelas"],
                )
            ]

            textos = [str(int(qtd)) for qtd in mensal_df["qtd_parcelas"]]

            fig_mensal = go.Figure()

            fig_mensal.add_trace(
                go.Scatter(
                    x=mensal_df["Mes"],
                    y=mensal_df["valor_pago_mes"],
                    mode="lines+markers+text",
                    name="Valor Pago",
                    text=textos,
                    textposition="top center",
                    textfont={"size": 12},
                    line={"color": CORES_RESPONSAVEL["Pago"], "width": 3},
                    marker={
                        "color": CORES_RESPONSAVEL["Pago"],
                        "size": 9,
                    },
                    customdata=hover_textos,
                    hovertemplate="%{customdata}<extra></extra>",
                )
            )

            fig_mensal.update_layout(
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )

            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["valor_pago_mes"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

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

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby(["mes_ordem", "responsavel_calc"], as_index=False)
                .agg(
                    total_pago=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
                )
                .sort_values(["mes_ordem", "responsavel_calc"])
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
                    mensal_df["responsavel_calc"] == responsavel
                ].copy()

                if df_resp.empty:
                    continue

                if responsavel == "Compradores":
                    df_resp = ordem_meses.merge(
                        df_resp,
                        on=["mes_ordem", "Mes"],
                        how="left"
                    )
                    df_resp["total_pago"] = df_resp["total_pago"].fillna(0)
                    df_resp["qtd_parcelas"] = df_resp["qtd_parcelas"].fillna(0)
                else:
                    ultimo_mes_corretora = df_resp["mes_ordem"].max()

                    ordem_meses_corretora = ordem_meses[
                        ordem_meses["mes_ordem"] <= ultimo_mes_corretora
                    ].copy()

                    df_resp = ordem_meses_corretora.merge(
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
                        f"Faturas Pagas: {int(qtd)}<br>"
                        f"Valor Pago no Mês: {brl(valor)}"
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
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["total_pago"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

    elif eh_evolucao_obra:
        evolucao_pago = evolucao_df.copy()
        evolucao_pago["data_pagamento_ref"] = _to_datetime_br(evolucao_pago["data_pagamento"])
        evolucao_pago["valor_pago_num"] = _to_numeric_brl(evolucao_pago["valor_pago"])

        evolucao_pago = evolucao_pago[
            (evolucao_pago["status"] == "pago")
            & (evolucao_pago["data_pagamento_ref"].notna())
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby(["mes_ordem"], as_index=False)
                .agg(
                    total_pago=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
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
                    f"Faturas Pagas: {int(qtd)}<br>"
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
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["total_pago"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
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

        evolucao_df["data_pagamento_ref"] = _to_datetime_br(evolucao_df["data_pagamento"])
        evolucao_df["valor_pago_num"] = _to_numeric_brl(evolucao_df["valor_pago"])

        evolucao_pago = evolucao_df[
            (evolucao_df["status"] == "pago")
            & (evolucao_df["data_pagamento_ref"].notna())
            & (evolucao_df["responsavel_pagamento"].isin(["Compradores", "Corretora"]))
        ].copy()

        if evolucao_pago.empty:
            st.info("Ainda não há pagamentos com data para mostrar a evolução mensal.")
        else:
            evolucao_pago["mes_ref"] = evolucao_pago["data_pagamento_ref"].dt.to_period("M")
            evolucao_pago["mes_ordem"] = evolucao_pago["mes_ref"].astype(str)

            mensal_df = (
                evolucao_pago.groupby(["mes_ordem", "responsavel_pagamento"], as_index=False)
                .agg(
                    total_pago=("valor_pago_num", "sum"),
                    qtd_parcelas=("valor_pago_num", "size"),
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

                hover_textos = [
                    (
                        f"<b>{mes}</b><br>"
                        f"Faturas Pagas: {int(qtd)}<br>"
                        f"Valor Pago no Mês: {brl(valor)}"
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
                xaxis_title="Mês do Pagamento",
                yaxis_title="Valor Pago",
                legend_title_text="",
                hovermode="x unified",
                xaxis=dict(tickangle=320),
            )
            _configurar_eixo_y_valor(
                fig_mensal,
                float(mensal_df["total_pago"].max()) * 1.2 if not mensal_df.empty else 500,
                500,
            )

            st.plotly_chart(fig_mensal, use_container_width=True)

    # =========================================================
    # GRÁFICO DE PIZZA
    # =========================================================
    if not eh_evolucao_obra:
        st.markdown("### Distribuição dos Valores")

        if eh_todos:
            base_pizza = parcelas_contrato.copy()
            if "serie" in base_pizza.columns:
                base_pizza["serie"] = base_pizza["serie"].astype(str).str.strip()

            base_pizza["pago_calc"] = base_pizza["status"].astype(str).str.lower().eq("pago")
            mask_direcional = base_pizza["contrato"].astype(str).str.strip().str.lower() == contrato_direcional
            if mask_direcional.any():
                base_pizza.loc[mask_direcional, "pago_calc"] = base_pizza.loc[mask_direcional].apply(
                    _eh_parcela_direcional_paga, axis=1
                )

            base_pizza["pendente_calc"] = ~base_pizza["pago_calc"]

            pago_registro = _to_numeric_brl(base_pizza.loc[
                (base_pizza["contrato"] == CONTRATO_TAXAS)
                & (base_pizza["pago_calc"]),
                "valor_pago",
            ]).sum()

            pendente_registro = _to_numeric_brl(base_pizza.loc[
                (base_pizza["contrato"] == CONTRATO_TAXAS)
                & (base_pizza["pendente_calc"]),
                "valor_total",
            ]).sum()

            pago_entrada = _to_numeric_brl(base_pizza.loc[
                (base_pizza["contrato"] == CONTRATO_DIRECIONAL)
                & (base_pizza["pago_calc"]),
                "valor_pago",
            ]).sum()

            pendente_entrada = _to_numeric_brl(base_pizza.loc[
                (base_pizza["contrato"] == CONTRATO_DIRECIONAL)
                & (base_pizza["pendente_calc"]),
                "valor_total",
            ]).sum()

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

                fig_resp.update_traces(
                    hovertemplate="%{label}<br>Valor: %{customdata}<extra></extra>",
                    customdata=[[brl(v)] for v in resp_df["valor"]]
                )
                st.plotly_chart(fig_resp, use_container_width=True)

        elif eh_taxas_cartorio:
            base_pizza = _filtrar_base_taxas_cartorio(parcelas_contrato, somente_compradores=False)
            base_pizza = _aplicar_regra_taxas_cartorio(base_pizza)

            grupos = []

            valor_pendente_compradores = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Compradores")
                & (base_pizza["pendente_calc"]),
                "valor_total",
            ]).sum()

            valor_pago_compradores = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Compradores")
                & (base_pizza["pago_calc"]),
                "valor_pago",
            ]).sum()

            valor_pendente_corretora = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Corretora")
                & (base_pizza["pendente_calc"]),
                "valor_total",
            ]).sum()

            valor_pago_corretora = _to_numeric_brl(base_pizza.loc[
                (base_pizza["responsavel_calc"] == "Corretora")
                & (base_pizza["pago_calc"]),
                "valor_pago",
            ]).sum()

            if valor_pendente_compradores > 0:
                grupos.append({"grupo": "Valor Pendente - Compradores", "valor": valor_pendente_compradores})

            if valor_pago_compradores > 0:
                grupos.append({"grupo": "Valor Pago - Compradores", "valor": valor_pago_compradores})

            if valor_pendente_corretora > 0:
                grupos.append({"grupo": "Valor Pendente - Corretora", "valor": valor_pendente_corretora})

            if valor_pago_corretora > 0:
                grupos.append({"grupo": "Valor Pago - Corretora", "valor": valor_pago_corretora})

            resp_df = pd.DataFrame(grupos)

            if not resp_df.empty:
                fig_resp = px.pie(
                    resp_df,
                    names="grupo",
                    values="valor",
                    color="grupo",
                    color_discrete_map=CORES_TAXAS_CARTORIO_PIZZA,
                )

                fig_resp.update_traces(
                    hovertemplate="%{label}<br>Valor: %{customdata}<extra></extra>",
                    customdata=[[brl(v)] for v in resp_df["valor"]]
                )
                st.plotly_chart(fig_resp, use_container_width=True)

        else:
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

                fig_resp.update_traces(
                    hovertemplate="%{label}<br>Valor: %{customdata}<extra></extra>",
                    customdata=[[brl(v)] for v in resp_df["valor"]]
                )
                st.plotly_chart(fig_resp, use_container_width=True)