from datetime import date
import pandas as pd
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TODOS,
    brl,
)


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


def _build_label_pendente(row, eh_todos=False):
    data_venc = pd.to_datetime(row.get("data_vencimento"), errors="coerce")
    data_venc_str = data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-"

    descricao = str(row.get("descricao_parcela", "Parcela"))
    num = int(row["numero_parcela"]) if pd.notnull(row.get("numero_parcela")) else 0
    total = int(row["total_parcelas"]) if pd.notnull(row.get("total_parcelas")) else 0
    valor = brl(row.get("valor_total", 0))

    if eh_todos:
        contrato = str(row.get("contrato", "")).strip()
        return f"{contrato} | {descricao} | {num}/{total} | vence {data_venc_str} | total {valor}"

    return f"{descricao} | {num}/{total} | vence {data_venc_str} | total {valor}"


def _build_label_pago(row, eh_todos=False):
    data_pag = pd.to_datetime(row.get("data_pagamento"), errors="coerce")
    data_pag_str = data_pag.strftime("%d/%m/%Y") if pd.notnull(data_pag) else "-"

    descricao = str(row.get("descricao_parcela", "Parcela"))
    num = int(row["numero_parcela"]) if pd.notnull(row.get("numero_parcela")) else 0
    total = int(row["total_parcelas"]) if pd.notnull(row.get("total_parcelas")) else 0
    valor = brl(row.get("valor_pago", 0))

    if eh_todos:
        contrato = str(row.get("contrato", "")).strip()
        return f"{contrato} | {descricao} | {num}/{total} | pago em {data_pag_str} | {valor}"

    return f"{descricao} | {num}/{total} | pago em {data_pag_str} | {valor}"


def registrar_pagamento(supabase, parcela_id, data_pagamento, valor_pago, responsavel_pagamento):
    payload = {
        "data_pagamento": _date_to_iso(data_pagamento),
        "valor_pago": float(valor_pago),
        "responsavel_pagamento": responsavel_pagamento,
        "status": "pago",
    }
    return _update_parcela(supabase, parcela_id, payload)


def atualizar_pagamento_existente(supabase, parcela_id, data_pagamento, valor_pago, responsavel_pagamento):
    payload = {
        "data_pagamento": _date_to_iso(data_pagamento),
        "valor_pago": float(valor_pago),
        "responsavel_pagamento": responsavel_pagamento,
        "status": "pago",
    }
    return _update_parcela(supabase, parcela_id, payload)


def desfazer_pagamento(supabase, parcela_id):
    payload = {
        "data_pagamento": None,
        "valor_pago": None,
        "status": "pendente",
    }
    return _update_parcela(supabase, parcela_id, payload)


# =========================================================
# TAB: REGISTRAR / EDITAR PAGAMENTO
# =========================================================
def render_pagamentos_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar):
    eh_todos = contrato_selecionado == CONTRATO_TODOS

    st.subheader(f"Registrar / Editar Pagamento — {contrato_selecionado}")

    if not pode_editar:
        st.info("Somente Matheus Moreira pode editar pagamentos.")
        return

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

    parcelas = parcelas_contrato.copy()

    if "eh_linha_resumo" in parcelas.columns:
        parcelas = parcelas[~parcelas["eh_linha_resumo"]].copy()

    if parcelas.empty:
        st.info("Sem parcelas disponíveis.")
        return

    # =========================================================
    # REGISTRAR PAGAMENTO - SOMENTE PRÓXIMA PENDENTE
    # =========================================================
    st.markdown("### Marcar parcela como paga")

    pendentes = parcelas[parcelas["status"] != "pago"].copy()

    if pendentes.empty:
        st.success("✅ Todas as parcelas desse contrato já estão pagas.")
    else:
        pendentes = pendentes.sort_values(["data_vencimento", "numero_parcela"]).copy()

        # somente a próxima pendente
        parcela_sel = pendentes.iloc[0]

        st.info(_build_label_pendente(parcela_sel, eh_todos=eh_todos))

        if parcela_sel["contrato"] == CONTRATO_DIRECIONAL:
            responsaveis_opcoes = ["Compradores"]
        else:
            responsaveis_opcoes = ["Compradores"]
            if parcelas["responsavel_pagamento"].fillna("").astype(str).eq("Corretora").any():
                responsaveis_opcoes.append("Corretora")

        c1, c2, c3 = st.columns(3)

        with c1:
            data_pagamento = st.date_input(
                "Data do pagamento",
                value=date.today(),
                format="DD/MM/YYYY",
                key="novo_pagamento_data",
            )

        with c2:
            valor_pago = st.number_input(
                "Valor pago",
                min_value=0.0,
                value=float(parcela_sel["valor_total"]) if pd.notnull(parcela_sel.get("valor_total")) else 0.0,
                step=0.01,
                format="%.2f",
                key="novo_pagamento_valor",
            )

        with c3:
            if parcela_sel["contrato"] == CONTRATO_DIRECIONAL:
                st.selectbox(
                    "Responsável pelo pagamento",
                    options=["Compradores"],
                    index=0,
                    disabled=True,
                    key="novo_pagamento_resp_dir",
                )
                responsavel_pagamento = "Compradores"
            else:
                idx_resp = 0
                if parcela_sel.get("responsavel_pagamento") in responsaveis_opcoes:
                    idx_resp = responsaveis_opcoes.index(parcela_sel["responsavel_pagamento"])

                responsavel_pagamento = st.selectbox(
                    "Responsável pelo pagamento",
                    options=responsaveis_opcoes,
                    index=idx_resp,
                    key="novo_pagamento_resp",
                )

        if st.button("Registrar pagamento", type="primary", key="btn_registrar_pagamento"):
            try:
                dados_atualizados = registrar_pagamento(
                    supabase=supabase,
                    parcela_id=parcela_sel["id"],
                    data_pagamento=data_pagamento,
                    valor_pago=valor_pago,
                    responsavel_pagamento=responsavel_pagamento,
                )

                if not dados_atualizados:
                    st.error("O banco não retornou a parcela atualizada.")
                else:
                    st.success("✅ Pagamento registrado com sucesso!")
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao registrar pagamento: {e}")

    st.markdown("---")
    st.markdown("### Editar parcela já paga")

    # =========================================================
    # EDITAR PAGAMENTO JÁ FEITO
    # =========================================================
    pagas = parcelas[parcelas["status"] == "pago"].copy()

    if pagas.empty:
        st.info("Nenhuma parcela paga para editar.")
        return

    pagas = pagas.sort_values(["data_pagamento", "numero_parcela"], ascending=[False, True]).copy()
    pagas["label"] = pagas.apply(lambda row: _build_label_pago(row, eh_todos=eh_todos), axis=1)

    parcela_paga_label = st.selectbox(
        "Selecione a parcela paga",
        pagas["label"].tolist(),
        key="edit_pago",
    )

    parcela_paga = pagas[pagas["label"] == parcela_paga_label].iloc[0]

    if parcela_paga["contrato"] == CONTRATO_DIRECIONAL:
        responsaveis_opcoes_edit = ["Compradores"]
    else:
        responsaveis_opcoes_edit = ["Compradores"]
        if parcelas["responsavel_pagamento"].fillna("").astype(str).eq("Corretora").any():
            responsaveis_opcoes_edit.append("Corretora")

    e1, e2, e3 = st.columns(3)

    with e1:
        nova_data_pagamento = st.date_input(
            "Nova data do pagamento",
            value=(
                parcela_paga["data_pagamento"].date()
                if pd.notnull(parcela_paga.get("data_pagamento"))
                and hasattr(parcela_paga["data_pagamento"], "date")
                else _to_date_or_none(parcela_paga.get("data_pagamento")) or date.today()
            ),
            format="DD/MM/YYYY",
            key="edit_data_pagamento",
        )

    with e2:
        novo_valor_pago = st.number_input(
            "Novo valor pago",
            min_value=0.0,
            value=float(parcela_paga["valor_pago"]) if pd.notnull(parcela_paga.get("valor_pago")) else 0.0,
            step=0.01,
            format="%.2f",
            key="edit_valor_pago",
        )

    with e3:
        if parcela_paga["contrato"] == CONTRATO_DIRECIONAL:
            st.selectbox(
                "Responsável",
                options=["Compradores"],
                index=0,
                disabled=True,
                key="edit_responsavel_dir",
            )
            novo_responsavel = "Compradores"
        else:
            idx_edit = 0
            if parcela_paga.get("responsavel_pagamento") in responsaveis_opcoes_edit:
                idx_edit = responsaveis_opcoes_edit.index(parcela_paga["responsavel_pagamento"])

            novo_responsavel = st.selectbox(
                "Responsável",
                options=responsaveis_opcoes_edit,
                index=idx_edit,
                key="edit_responsavel",
            )

    b1, b2 = st.columns(2)

    with b1:
        if st.button("Salvar edição do pagamento", key="btn_salvar_edicao_pagamento"):
            try:
                dados_atualizados = atualizar_pagamento_existente(
                    supabase=supabase,
                    parcela_id=parcela_paga["id"],
                    data_pagamento=nova_data_pagamento,
                    valor_pago=novo_valor_pago,
                    responsavel_pagamento=novo_responsavel,
                )

                if not dados_atualizados:
                    st.error("O banco não retornou a parcela atualizada.")
                else:
                    st.success("✅ Pagamento atualizado com sucesso!")
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao atualizar pagamento: {e}")

    with b2:
        if st.button("Desfazer pagamento", key="btn_desfazer_pagamento"):
            try:
                dados_atualizados = desfazer_pagamento(
                    supabase=supabase,
                    parcela_id=parcela_paga["id"],
                )

                if not dados_atualizados:
                    st.error("O banco não retornou a parcela atualizada.")
                else:
                    st.success("✅ Pagamento desfeito com sucesso!")
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao desfazer pagamento: {e}")


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

    parcelas["label_parcela"] = parcelas.apply(
        lambda row: (
            f"{str(row.get('contrato', '')).strip() + ' | ' if str(row.get('contrato', '')).strip() else ''}"
            f"{str(row.get('descricao_parcela', 'Parcela'))} | "
            f"{int(row['numero_parcela']) if pd.notnull(row.get('numero_parcela')) else 0}/"
            f"{int(row['total_parcelas']) if pd.notnull(row.get('total_parcelas')) else 0} | "
            f"Venc.: "
            f"{pd.to_datetime(row['data_vencimento'], errors='coerce').strftime('%d/%m/%Y') if pd.notnull(row.get('data_vencimento')) else '-'} | "
            f"{brl(row.get('valor_total', 0))}"
        ),
        axis=1,
    )

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