from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import CONTRATO_TODOS, brl


# =========================================================
# HELPERS
# =========================================================

def _get_col(df, candidatos, obrigatoria=False):
    for col in candidatos:
        if col in df.columns:
            return col
    if obrigatoria:
        raise KeyError(f"Nenhuma das colunas esperadas foi encontrada: {candidatos}")
    return None


def _to_float(serie):
    if serie is None:
        return pd.Series(dtype="float64")

    if pd.api.types.is_numeric_dtype(serie):
        return serie.fillna(0).astype(float)

    return (
        serie.astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
        .replace(["", "nan", "None", "NaT"], "0")
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )


def _to_date(serie):
    if serie is None:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(serie, errors="coerce")


def _eh_pago(status, valor_pago):
    status_norm = (
        status.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    pago_por_status = status_norm.isin(
        [
            "pago",
            "quitado",
            "concluido",
            "concluído",
            "liquidado",
            "baixado",
        ]
    )

    pago_por_valor = valor_pago.fillna(0) > 0

    return pago_por_status | pago_por_valor


def _fmt_pct(valor):
    return f"{valor:.1f}%"


def _render_card(titulo, valor, subtitulo=None):
    html = f"""
    <div style="
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 14px;
        padding: 16px 18px;
        background: rgba(255,255,255,0.02);
        min-height: 118px;
    ">
        <div style="font-size: 0.92rem; opacity: 0.85; margin-bottom: 8px;">
            {titulo}
        </div>
        <div style="font-size: 1.35rem; font-weight: 700; line-height: 1.25;">
            {valor}
        </div>
        <div style="font-size: 0.88rem; opacity: 0.72; margin-top: 8px;">
            {subtitulo or ""}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def _preparar_base(parcelas):
    df = parcelas.copy()

    if df.empty:
        return df

    if "eh_linha_resumo" in df.columns:
        df = df[~df["eh_linha_resumo"].fillna(False)].copy()

    if "contrato" not in df.columns:
        return pd.DataFrame()

    df["contrato"] = df["contrato"].fillna("").astype(str).str.strip()
    df = df[df["contrato"] != ""].copy()

    # Remove a visão "Todos os Contratos" caso exista fisicamente na base
    df = df[df["contrato"] != CONTRATO_TODOS].copy()

    col_valor_total = _get_col(df, ["valor_total", "valor_parcela", "valor_previsto"], obrigatoria=False)
    col_valor_pago = _get_col(df, ["valor_pago"], obrigatoria=False)
    col_status = _get_col(df, ["status"], obrigatoria=False)
    col_vencimento = _get_col(df, ["data_vencimento", "vencimento", "data"], obrigatoria=False)
    col_referencia = _get_col(df, ["mes_referencia", "referencia", "competencia"], obrigatoria=False)
    col_numero = _get_col(df, ["numero_parcela", "parcela", "n_parcela"], obrigatoria=False)

    df["valor_total_calc"] = _to_float(df[col_valor_total]) if col_valor_total else 0.0
    df["valor_pago_calc"] = _to_float(df[col_valor_pago]) if col_valor_pago else 0.0
    df["status_calc"] = df[col_status].astype(str) if col_status else ""
    df["vencimento_calc"] = _to_date(df[col_vencimento]) if col_vencimento else pd.NaT
    df["referencia_calc"] = df[col_referencia].astype(str) if col_referencia else ""
    df["numero_parcela_calc"] = df[col_numero].astype(str) if col_numero else ""

    df["pago_calc"] = _eh_pago(df["status_calc"], df["valor_pago_calc"])

    # Se não tiver valor_pago preenchido, mas estiver como pago, considera o valor_total
    df.loc[
        (df["pago_calc"]) & (df["valor_pago_calc"] <= 0),
        "valor_pago_calc"
    ] = df.loc[
        (df["pago_calc"]) & (df["valor_pago_calc"] <= 0),
        "valor_total_calc"
    ]

    df["valor_pendente_calc"] = (df["valor_total_calc"] - df["valor_pago_calc"]).clip(lower=0)

    return df


# =========================================================
# DASHBOARD TODOS OS CONTRATOS
# =========================================================

def render_dashboard_todos(parcelas):
    df = _preparar_base(parcelas)

    if df.empty:
        st.info("Não há dados suficientes para exibir o dashboard de Todos os Contratos.")
        return

    # -----------------------------------------------------
    # RESUMO GERAL
    # -----------------------------------------------------
    resumo = (
        df.groupby("contrato", as_index=False)
        .agg(
            valor_total=("valor_total_calc", "sum"),
            valor_pago=("valor_pago_calc", "sum"),
            valor_pendente=("valor_pendente_calc", "sum"),
            total_parcelas=("contrato", "size"),
            parcelas_pagas=("pago_calc", "sum"),
        )
        .sort_values("contrato")
        .reset_index(drop=True)
    )

    resumo["parcelas_pagas"] = resumo["parcelas_pagas"].astype(int)
    resumo["parcelas_pendentes"] = resumo["total_parcelas"] - resumo["parcelas_pagas"]
    resumo["percentual"] = resumo.apply(
        lambda row: (row["valor_pago"] / row["valor_total"] * 100) if row["valor_total"] > 0 else 0,
        axis=1,
    )

    pagamento_total = resumo["valor_pago"].sum()
    valor_total_geral = resumo["valor_total"].sum()
    valor_pendente_geral = resumo["valor_pendente"].sum()
    percentual_total = (pagamento_total / valor_total_geral * 100) if valor_total_geral > 0 else 0

    st.subheader("📌 Visão geral")

    c1, c2 = st.columns(2)
    with c1:
        _render_card(
            "Pagamento total",
            brl(pagamento_total),
            f"Conclusão total: {_fmt_pct(percentual_total)}",
        )
    with c2:
        _render_card(
            "Valor total pendente",
            brl(valor_pendente_geral),
            f"Previsto total: {brl(valor_total_geral)}",
        )

    st.markdown("### 📂 Resumo por contrato")

    for _, row in resumo.iterrows():
        col1, col2, col3 = st.columns([1.2, 1, 1])

        with col1:
            _render_card(
                row["contrato"],
                brl(row["valor_pago"]),
                f"Pago nesse contrato",
            )

        with col2:
            _render_card(
                "Parcelas",
                f'{int(row["parcelas_pagas"])} pagas / {int(row["parcelas_pendentes"])} restantes',
                f'Total: {int(row["total_parcelas"])}',
            )

        with col3:
            _render_card(
                "Conclusão",
                _fmt_pct(row["percentual"]),
                f'Pendente: {brl(row["valor_pendente"])}',
            )

    # -----------------------------------------------------
    # PRÓXIMAS PARCELAS
    # -----------------------------------------------------
    st.markdown("### ⏭️ Próximas parcelas por contrato")

    pendentes = df[~df["pago_calc"]].copy()

    if not pendentes.empty:
        pendentes = pendentes.sort_values(["contrato", "vencimento_calc", "valor_total_calc"])

        proximas = (
            pendentes.groupby("contrato", as_index=False)
            .first()
            .copy()
        )

        proximas_exibir = pd.DataFrame({
            "Contrato": proximas["contrato"],
            "Parcela": proximas["numero_parcela_calc"].replace("", "-"),
            "Referência": proximas["referencia_calc"].replace("", "-"),
            "Vencimento": proximas["vencimento_calc"].dt.strftime("%d/%m/%Y").fillna("-"),
            "Valor": proximas["valor_total_calc"].apply(brl),
        })

        st.dataframe(
            proximas_exibir,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("Não há parcelas pendentes. Todos os contratos parecem quitados.")

    # -----------------------------------------------------
    # EVOLUÇÃO POR MÊS
    # -----------------------------------------------------
    st.markdown("### 📈 Evolução por mês")

    pagos = df[df["pago_calc"]].copy()

    if not pagos.empty:
        # Usa vencimento como referência do mês; se estiver vazio, tenta data atual da linha convertida
        pagos["mes_base"] = pagos["vencimento_calc"].dt.to_period("M").astype(str)
        pagos = pagos[pagos["mes_base"].notna()].copy()

        evolucao = (
            pagos.groupby(["mes_base", "contrato"], as_index=False)["valor_pago_calc"]
            .sum()
            .rename(columns={"valor_pago_calc": "valor_pago"})
        )

        if not evolucao.empty:
            evolucao["mes_ordenacao"] = pd.to_datetime(evolucao["mes_base"] + "-01", errors="coerce")
            evolucao = evolucao.sort_values(["mes_ordenacao", "contrato"])

            fig_evolucao = px.bar(
                evolucao,
                x="mes_base",
                y="valor_pago",
                color="contrato",
                barmode="stack",
                labels={
                    "mes_base": "Mês",
                    "valor_pago": "Valor pago",
                    "contrato": "Contrato",
                },
                text_auto=False,
            )
            fig_evolucao.update_layout(
                height=430,
                xaxis_title="Mês",
                yaxis_title="Valor pago",
                legend_title="Contrato",
            )
            st.plotly_chart(fig_evolucao, use_container_width=True)
        else:
            st.info("Ainda não há dados suficientes para montar a evolução mensal.")
    else:
        st.info("Ainda não há pagamentos registrados para montar a evolução mensal.")

    # -----------------------------------------------------
    # PIZZA: PAGO X PENDENTE POR CONTRATO
    # -----------------------------------------------------
    st.markdown("### 🥧 Pago x pendente por contrato")

    pizza_df = resumo.copy()

    pizza_long = pd.concat(
        [
            pizza_df[["contrato", "valor_pago"]].rename(columns={"valor_pago": "valor"}).assign(tipo="Pago"),
            pizza_df[["contrato", "valor_pendente"]].rename(columns={"valor_pendente": "valor"}).assign(tipo="Pendente"),
        ],
        ignore_index=True,
    )

    pizza_long = pizza_long[pizza_long["valor"] > 0].copy()

    if not pizza_long.empty:
        pizza_long["label"] = pizza_long["contrato"] + " - " + pizza_long["tipo"]

        fig_pizza = go.Figure(
            data=[
                go.Pie(
                    labels=pizza_long["label"],
                    values=pizza_long["valor"],
                    hole=0.45,
                    textinfo="label+percent",
                )
            ]
        )
        fig_pizza.update_layout(height=520)
        st.plotly_chart(fig_pizza, use_container_width=True)
    else:
        st.info("Não há valores suficientes para montar o gráfico de pizza.")

    # -----------------------------------------------------
    # TABELA RESUMO
    # -----------------------------------------------------
    st.markdown("### 📋 Resumo consolidado")

    resumo_exibir = resumo.copy()
    resumo_exibir["valor_total"] = resumo_exibir["valor_total"].apply(brl)
    resumo_exibir["valor_pago"] = resumo_exibir["valor_pago"].apply(brl)
    resumo_exibir["valor_pendente"] = resumo_exibir["valor_pendente"].apply(brl)
    resumo_exibir["percentual"] = resumo_exibir["percentual"].map(_fmt_pct)

    resumo_exibir = resumo_exibir.rename(
        columns={
            "contrato": "Contrato",
            "valor_total": "Valor total",
            "valor_pago": "Valor pago",
            "valor_pendente": "Valor pendente",
            "total_parcelas": "Qtd. parcelas",
            "parcelas_pagas": "Pagas",
            "parcelas_pendentes": "Restantes",
            "percentual": "% conclusão",
        }
    )

    st.dataframe(resumo_exibir, use_container_width=True, hide_index=True)