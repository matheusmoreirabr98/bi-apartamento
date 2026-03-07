import pandas as pd
import streamlit as st

from utils import brl


def _formatar_dataframe_pagamentos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "data_vencimento" in df.columns:
        df["data_vencimento"] = pd.to_datetime(df["data_vencimento"], errors="coerce").dt.date

    if "data_pagamento" in df.columns:
        df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce").dt.date

    for col in ["valor_principal", "valor_total", "valor_pago"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: brl(x) if pd.notnull(x) else "-")

    return df


def render_pagamentos_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar):
    st.subheader(f"Registrar / Editar Pagamento — {contrato_selecionado}")

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

    parcelas = parcelas_contrato.copy()

    if "eh_linha_resumo" in parcelas.columns:
        parcelas = parcelas[~parcelas["eh_linha_resumo"]].copy()

    if parcelas.empty:
        st.info("Sem parcelas disponíveis para pagamento.")
        return

    filtros_col1, filtros_col2 = st.columns(2)

    with filtros_col1:
        opcoes_status = ["Todos", "Pendentes/Atrasadas", "Pagas"]
        status_filtro = st.selectbox(
            "Filtrar por status",
            opcoes_status,
            key="pagamentos_status_filtro",
        )

    with filtros_col2:
        opcoes_resp = ["Todos"]
        if "responsavel_pagamento" in parcelas.columns:
            opcoes_resp += sorted(parcelas["responsavel_pagamento"].dropna().astype(str).unique().tolist())

        responsavel_filtro = st.selectbox(
            "Responsável",
            opcoes_resp,
            key="pagamentos_responsavel_filtro",
        )

    if status_filtro == "Pendentes/Atrasadas":
        parcelas = parcelas[parcelas["status"] != "pago"].copy()
    elif status_filtro == "Pagas":
        parcelas = parcelas[parcelas["status"] == "pago"].copy()

    if responsavel_filtro != "Todos" and "responsavel_pagamento" in parcelas.columns:
        parcelas = parcelas[parcelas["responsavel_pagamento"] == responsavel_filtro].copy()

    if parcelas.empty:
        st.info("Nenhuma parcela encontrada com os filtros selecionados.")
        return

    parcelas = parcelas.sort_values(
        ["data_vencimento", "numero_parcela"],
        ascending=[True, True],
    ).copy()

    parcelas["label_parcela"] = parcelas.apply(
        lambda row: (
            f"{row.get('descricao_parcela', 'Parcela')} | "
            f"{int(row['numero_parcela'])}/{int(row['total_parcelas'])} | "
            f"Venc.: "
            f"{pd.to_datetime(row['data_vencimento'], errors='coerce').strftime('%d/%m/%Y') if pd.notnull(row.get('data_vencimento')) else '-'} | "
            f"{brl(row.get('valor_total', 0))}"
        ),
        axis=1,
    )

    parcela_escolhida_label = st.selectbox(
        "Selecione a parcela",
        parcelas["label_parcela"].tolist(),
        key="pagamentos_parcela_select",
    )

    parcela_escolhida = parcelas[parcelas["label_parcela"] == parcela_escolhida_label].iloc[0]

    st.markdown("### Dados da Parcela")

    info_cols = st.columns(3)

    with info_cols[0]:
        st.caption("Parcela")
        st.write(f"{int(parcela_escolhida['numero_parcela'])}/{int(parcela_escolhida['total_parcelas'])}")

        st.caption("Status")
        st.write(str(parcela_escolhida.get("status_exibicao", "-")))

    with info_cols[1]:
        st.caption("Vencimento")
        data_venc = pd.to_datetime(parcela_escolhida.get("data_vencimento"), errors="coerce")
        st.write(data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-")

        st.caption("Responsável")
        st.write(str(parcela_escolhida.get("responsavel_pagamento", "-")))

    with info_cols[2]:
        st.caption("Valor total")
        st.write(brl(parcela_escolhida.get("valor_total", 0)))

        st.caption("Valor pago atual")
        valor_pago_atual = parcela_escolhida.get("valor_pago")
        st.write(brl(valor_pago_atual) if pd.notnull(valor_pago_atual) else "-")

    st.markdown("### Edição de Pagamento")

    if not pode_editar:
        st.warning("Você não tem permissão para editar pagamentos.")
        return

    st.info(
        "A estrutura desta aba foi restaurada para o app voltar a abrir sem erro. "
        "Se quiser, no próximo passo eu monto a lógica completa de salvar pagamento no Supabase."
    )

    with st.form("form_pagamento_placeholder"):
        novo_valor_pago = st.number_input(
            "Valor pago",
            min_value=0.0,
            value=float(parcela_escolhida["valor_pago"]) if pd.notnull(parcela_escolhida.get("valor_pago")) else 0.0,
            step=0.01,
            format="%.2f",
        )

        nova_data_pagamento = st.date_input(
            "Data do pagamento",
            value=(
                pd.to_datetime(parcela_escolhida["data_pagamento"], errors="coerce").date()
                if pd.notnull(parcela_escolhida.get("data_pagamento"))
                else pd.Timestamp.today().date()
            ),
        )

        submitted = st.form_submit_button("Salvar pagamento")

    if submitted:
        st.warning(
            "O botão foi mantido apenas como placeholder seguro para não arriscar quebrar a lógica do banco. "
            "A persistência no Supabase ainda precisa ser implementada com base no schema real."
        )


def render_atualizar_parcelas_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar):
    st.subheader(f"Atualizar Parcelas — {contrato_selecionado}")

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

    parcelas = parcelas_contrato.copy()

    if "eh_linha_resumo" in parcelas.columns:
        parcelas = parcelas[~parcelas["eh_linha_resumo"]].copy()

    if parcelas.empty:
        st.info("Sem parcelas disponíveis.")
        return

    st.info(
        "Esta aba foi restaurada para eliminar o erro de importação. "
        "Ela pode ser expandida depois com a lógica de atualização em massa."
    )

    resumo_cols = st.columns(4)

    with resumo_cols[0]:
        st.metric("Total de parcelas", len(parcelas))

    with resumo_cols[1]:
        qtd_pagas = int((parcelas["status"] == "pago").sum()) if "status" in parcelas.columns else 0
        st.metric("Pagas", qtd_pagas)

    with resumo_cols[2]:
        qtd_abertas = int((parcelas["status"] != "pago").sum()) if "status" in parcelas.columns else 0
        st.metric("Em aberto", qtd_abertas)

    with resumo_cols[3]:
        total_em_aberto = (
            parcelas.loc[parcelas["status"] != "pago", "valor_total"].fillna(0).sum()
            if "status" in parcelas.columns and "valor_total" in parcelas.columns
            else 0
        )
        st.metric("Total em aberto", brl(total_em_aberto))

    colunas_show = [
        col for col in [
            "contrato",
            "origem",
            "categoria",
            "descricao_parcela",
            "numero_parcela",
            "total_parcelas",
            "data_vencimento",
            "data_pagamento",
            "valor_principal",
            "valor_total",
            "valor_pago",
            "status_exibicao",
            "responsavel_pagamento",
        ]
        if col in parcelas.columns
    ]

    parcelas_show = _formatar_dataframe_pagamentos(parcelas[colunas_show])

    st.markdown("### Visualização das Parcelas")
    st.dataframe(parcelas_show, use_container_width=True, hide_index=True)

    if not pode_editar:
        st.warning("Você não tem permissão para atualizar parcelas.")
        return

    with st.form("form_atualizacao_placeholder"):
        st.text_input(
            "Observação",
            value="",
            placeholder="Ex.: futuramente usar para atualizar vencimentos, status ou valores",
        )
        submitted = st.form_submit_button("Aplicar atualização")

    if submitted:
        st.warning(
            "A atualização em massa ainda não foi implementada no banco. "
            "Mantive apenas a estrutura segura para o app funcionar."
        )