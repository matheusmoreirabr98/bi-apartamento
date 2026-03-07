import pandas as pd
import streamlit as st

from utils import brl


# =========================================================
# HELPERS
# =========================================================
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


def _to_float(valor):
    if pd.isnull(valor):
        return 0.0
    try:
        return float(valor)
    except Exception:
        return 0.0


def _to_date_or_none(valor):
    if valor in [None, "", pd.NaT]:
        return None
    try:
        return pd.to_datetime(valor, errors="coerce").date()
    except Exception:
        return None


def _date_to_iso(valor):
    if valor is None:
        return None
    try:
        return pd.to_datetime(valor).date().isoformat()
    except Exception:
        return None


def _update_parcela(supabase, parcela_id, payload: dict):
    return supabase.table("parcelas").update(payload).eq("id", parcela_id).execute()


def _build_label_parcela(row):
    data_venc = pd.to_datetime(row.get("data_vencimento"), errors="coerce")
    data_venc_str = data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-"

    descricao = str(row.get("descricao_parcela", "Parcela"))
    num = int(row["numero_parcela"]) if pd.notnull(row.get("numero_parcela")) else 0
    total = int(row["total_parcelas"]) if pd.notnull(row.get("total_parcelas")) else 0
    valor = brl(row.get("valor_total", 0))

    contrato = str(row.get("contrato", "")).strip()
    prefixo = f"{contrato} | " if contrato else ""

    return f"{prefixo}{descricao} | {num}/{total} | Venc.: {data_venc_str} | {valor}"


# =========================================================
# TAB: REGISTRAR / EDITAR PAGAMENTO
# =========================================================
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
            opcoes_resp += sorted(
                parcelas["responsavel_pagamento"].dropna().astype(str).unique().tolist()
            )

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

    parcelas["label_parcela"] = parcelas.apply(_build_label_parcela, axis=1)

    parcela_escolhida_label = st.selectbox(
        "Selecione a parcela",
        parcelas["label_parcela"].tolist(),
        key="pagamentos_parcela_select",
    )

    parcela_escolhida = parcelas[parcelas["label_parcela"] == parcela_escolhida_label].iloc[0]

    st.markdown("## Dados da Parcela")

    info_cols = st.columns(3)

    with info_cols[0]:
        st.caption("Parcela")
        st.write(
            f"{int(parcela_escolhida['numero_parcela'])}/{int(parcela_escolhida['total_parcelas'])}"
        )

        st.caption("Status")
        st.write(str(parcela_escolhida.get("status_exibicao", parcela_escolhida.get("status", "-"))))

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

    st.markdown("## Edição de Pagamento")

    if not pode_editar:
        st.warning("Você não tem permissão para editar pagamentos.")
        return

    valor_pago_inicial = _to_float(parcela_escolhida.get("valor_pago"))
    data_pagamento_inicial = _to_date_or_none(parcela_escolhida.get("data_pagamento"))
    status_atual = str(parcela_escolhida.get("status", "")).strip().lower()

    with st.form("form_pagamento"):
        novo_valor_pago = st.number_input(
            "Valor pago",
            min_value=0.0,
            value=valor_pago_inicial,
            step=0.01,
            format="%.2f",
        )

        limpar_data = st.checkbox(
            "Remover data de pagamento",
            value=False,
            key="pagamento_limpar_data",
        )

        if limpar_data:
            nova_data_pagamento = None
            st.caption("A data de pagamento será removida ao salvar.")
        else:
            nova_data_pagamento = st.date_input(
                "Data do pagamento",
                value=data_pagamento_inicial or pd.Timestamp.today().date(),
            )

        marcar_como_pago = st.checkbox(
            "Marcar parcela como paga",
            value=(status_atual == "pago"),
            key="pagamento_status_pago",
        )

        submitted = st.form_submit_button("Salvar pagamento", use_container_width=True)

    col_acoes1, col_acoes2 = st.columns(2)

    with col_acoes1:
        limpar_pagamento = st.button(
            "Limpar pagamento",
            use_container_width=True,
            disabled=not pode_editar,
        )

    with col_acoes2:
        pass

    if submitted:
        try:
            parcela_id = parcela_escolhida["id"]

            status_novo = "pago" if marcar_como_pago else "pendente"

            payload = {
                "valor_pago": float(novo_valor_pago) if marcar_como_pago else None,
                "data_pagamento": _date_to_iso(nova_data_pagamento) if marcar_como_pago else None,
                "status": status_novo,
            }

            _update_parcela(supabase, parcela_id, payload)

            st.success("Pagamento atualizado com sucesso.")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao salvar pagamento: {e}")

    if limpar_pagamento:
        try:
            parcela_id = parcela_escolhida["id"]

            payload = {
                "valor_pago": None,
                "data_pagamento": None,
                "status": "pendente",
            }

            _update_parcela(supabase, parcela_id, payload)

            st.success("Pagamento removido com sucesso.")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao limpar pagamento: {e}")


# =========================================================
# TAB: ATUALIZAR PARCELAS
# =========================================================
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

    st.markdown("### Visualização das Parcelas")

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
    st.dataframe(parcelas_show, use_container_width=True, hide_index=True)

    st.markdown("### Editar Parcela")

    parcelas = parcelas.sort_values(
        ["data_vencimento", "numero_parcela"],
        ascending=[True, True],
    ).copy()

    parcelas["label_parcela"] = parcelas.apply(_build_label_parcela, axis=1)

    parcela_label = st.selectbox(
        "Selecione a parcela para atualizar",
        parcelas["label_parcela"].tolist(),
        key="atualizar_parcela_select",
    )

    parcela_escolhida = parcelas[parcelas["label_parcela"] == parcela_label].iloc[0]

    if not pode_editar:
        st.warning("Você não tem permissão para atualizar parcelas.")
        return

    descricao_inicial = str(parcela_escolhida.get("descricao_parcela", "") or "")
    data_venc_inicial = _to_date_or_none(parcela_escolhida.get("data_vencimento"))
    valor_principal_inicial = _to_float(parcela_escolhida.get("valor_principal"))
    valor_total_inicial = _to_float(parcela_escolhida.get("valor_total"))
    responsavel_atual = str(parcela_escolhida.get("responsavel_pagamento", "") or "").strip()

    opcoes_responsavel = ["Compradores", "Corretora"]
    if responsavel_atual and responsavel_atual not in opcoes_responsavel:
        opcoes_responsavel.append(responsavel_atual)

    indice_resp = opcoes_responsavel.index(responsavel_atual) if responsavel_atual in opcoes_responsavel else 0

    with st.form("form_atualizar_parcela"):
        col1, col2 = st.columns(2)

        with col1:
            nova_descricao = st.text_input(
                "Descrição da parcela",
                value=descricao_inicial,
            )

            nova_data_vencimento = st.date_input(
                "Data de vencimento",
                value=data_venc_inicial or pd.Timestamp.today().date(),
            )

            novo_responsavel = st.selectbox(
                "Responsável",
                opcoes_responsavel,
                index=indice_resp,
            )

        with col2:
            novo_valor_principal = st.number_input(
                "Valor principal",
                min_value=0.0,
                value=valor_principal_inicial,
                step=0.01,
                format="%.2f",
            )

            novo_valor_total = st.number_input(
                "Valor total",
                min_value=0.0,
                value=valor_total_inicial,
                step=0.01,
                format="%.2f",
            )

            st.text_input(
                "Contrato",
                value=str(parcela_escolhida.get("contrato", "-")),
                disabled=True,
            )

        submitted = st.form_submit_button("Salvar alterações", use_container_width=True)

    if submitted:
        try:
            parcela_id = parcela_escolhida["id"]

            payload = {
                "descricao_parcela": nova_descricao,
                "data_vencimento": _date_to_iso(nova_data_vencimento),
                "valor_principal": float(novo_valor_principal),
                "valor_total": float(novo_valor_total),
                "responsavel_pagamento": novo_responsavel,
            }

            _update_parcela(supabase, parcela_id, payload)

            st.success("Parcela atualizada com sucesso.")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao atualizar parcela: {e}")