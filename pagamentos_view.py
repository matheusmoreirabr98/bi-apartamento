import time
from datetime import date

import pandas as pd
import streamlit as st

from database import (
    atualizar_pagamento_existente,
    desfazer_pagamento,
    registrar_pagamento,
)
from utils import CONTRATO_DIRECIONAL, CONTRATO_TODOS, brl


def render_pagamentos_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar):
    eh_todos = contrato_selecionado == CONTRATO_TODOS

    st.subheader(f"Registrar / Editar Pagamento — {contrato_selecionado}")

    if not pode_editar:
        st.info("Somente Matheus Moreira pode editar pagamentos.")
        return

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

    pendentes = parcelas_contrato[
        (parcelas_contrato["status"] != "pago") & (~parcelas_contrato["eh_linha_resumo"])
    ].copy()

    st.markdown("### Marcar parcela como paga")

    if pendentes.empty:
        st.success("✅ Todas as parcelas desse contrato já estão pagas.")
    else:
        pendentes = pendentes.sort_values(["data_vencimento", "numero_parcela"]).copy()

        if eh_todos:
            pendentes["label"] = (
                pendentes["contrato"]
                + " | "
                + pendentes["descricao_parcela"]
                + " | "
                + pendentes["numero_parcela"].astype(str)
                + "/"
                + pendentes["total_parcelas"].astype(str)
                + " | vence "
                + pendentes["data_vencimento"].dt.strftime("%d/%m/%Y")
                + " | total "
                + pendentes["valor_total"].apply(brl)
            )
        else:
            pendentes["label"] = (
                pendentes["descricao_parcela"]
                + " | "
                + pendentes["numero_parcela"].astype(str)
                + "/"
                + pendentes["total_parcelas"].astype(str)
                + " | vence "
                + pendentes["data_vencimento"].dt.strftime("%d/%m/%Y")
                + " | total "
                + pendentes["valor_total"].apply(brl)
            )

        parcela_label = st.selectbox(
            "Selecione a parcela",
            pendentes["label"].tolist(),
            key="tab3_selecao_pendente",
        )
        parcela_sel = pendentes[pendentes["label"] == parcela_label].iloc[0]

        if parcela_sel["contrato"] == CONTRATO_DIRECIONAL:
            responsaveis_opcoes = ["Compradores"]
        else:
            responsaveis_opcoes = ["Compradores"]
            if parcelas_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any():
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
                value=float(parcela_sel["valor_total"]),
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
                if parcela_sel["responsavel_pagamento"] in responsaveis_opcoes:
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
                    supabase,
                    parcela_id=parcela_sel["id"],
                    data_pagamento=data_pagamento,
                    valor_pago=valor_pago,
                    responsavel_pagamento=responsavel_pagamento,
                )

                if not dados_atualizados:
                    st.error("O banco não retornou a parcela atualizada.")
                else:
                    linha = dados_atualizados[0]
                    if linha.get("status") != "pago":
                        st.error("A parcela não foi marcada como paga no banco.")
                    else:
                        st.success("✅ Pagamento registrado com sucesso!")
                        time.sleep(0.8)
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao registrar pagamento: {e}")

    st.markdown("---")
    st.markdown("### Editar parcela já paga")

    pagas = parcelas_contrato[
        (parcelas_contrato["status"] == "pago") & (~parcelas_contrato["eh_linha_resumo"])
    ].copy()

    if pagas.empty:
        st.info("Nenhuma parcela paga para editar.")
    else:
        pagas = pagas.sort_values(["data_pagamento", "numero_parcela"], ascending=[False, True]).copy()

        if eh_todos:
            pagas["label"] = (
                pagas["contrato"]
                + " | "
                + pagas["descricao_parcela"]
                + " | "
                + pagas["numero_parcela"].astype(str)
                + "/"
                + pagas["total_parcelas"].astype(str)
                + " | pago em "
                + pagas["data_pagamento"].dt.strftime("%d/%m/%Y")
                + " | "
                + pagas["valor_pago"].fillna(0).apply(brl)
            )
        else:
            pagas["label"] = (
                pagas["descricao_parcela"]
                + " | "
                + pagas["numero_parcela"].astype(str)
                + "/"
                + pagas["total_parcelas"].astype(str)
                + " | pago em "
                + pagas["data_pagamento"].dt.strftime("%d/%m/%Y")
                + " | "
                + pagas["valor_pago"].fillna(0).apply(brl)
            )

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
            if parcelas_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any():
                responsaveis_opcoes_edit.append("Corretora")

        e1, e2, e3 = st.columns(3)
        with e1:
            nova_data_pagamento = st.date_input(
                "Nova data do pagamento",
                value=parcela_paga["data_pagamento"].date()
                if pd.notnull(parcela_paga["data_pagamento"])
                else date.today(),
                format="DD/MM/YYYY",
                key="edit_data_pagamento",
            )
        with e2:
            novo_valor_pago = st.number_input(
                "Novo valor pago",
                min_value=0.0,
                value=float(parcela_paga["valor_pago"]) if pd.notnull(parcela_paga["valor_pago"]) else 0.0,
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
                if parcela_paga["responsavel_pagamento"] in responsaveis_opcoes_edit:
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
                        supabase,
                        parcela_id=parcela_paga["id"],
                        data_pagamento=nova_data_pagamento,
                        valor_pago=novo_valor_pago,
                        responsavel_pagamento=novo_responsavel,
                    )

                    if not dados_atualizados:
                        st.error("O banco não retornou a parcela atualizada.")
                    else:
                        st.success("✅ Pagamento atualizado com sucesso!")
                        time.sleep(0.8)
                        st.rerun()

                except Exception as e:
                    st.error(f"Erro ao atualizar pagamento: {e}")

        with b2:
            if st.button("Desfazer pagamento", key="btn_desfazer_pagamento"):
                try:
                    dados_atualizados = desfazer_pagamento(supabase, parcela_paga["id"])

                    if not dados_atualizados:
                        st.error("O banco não retornou a parcela atualizada.")
                    else:
                        linha = dados_atualizados[0]
                        if linha.get("status") != "pendente":
                            st.error("A parcela não voltou para pendente no banco.")
                        else:
                            st.success("✅ Pagamento desfeito com sucesso!")
                            time.sleep(0.8)
                            st.rerun()

                except Exception as e:
                    st.error(f"Erro ao desfazer pagamento: {e}")


def render_atualizar_parcelas_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar):
    eh_todos = contrato_selecionado == CONTRATO_TODOS

    st.subheader(f"Atualizar Parcelas — {contrato_selecionado}")

    if not pode_editar:
        st.info("Somente Matheus Moreira pode atualizar parcelas.")
        return

    if parcelas_contrato.empty:
        st.info("Sem parcelas cadastradas.")
        return

    edit_cols = [
        "id",
        "categoria",
        "origem",
        "descricao_parcela",
        "numero_parcela",
        "total_parcelas",
        "data_vencimento",
        "valor_principal",
        "valor_total",
        "status",
        "responsavel_pagamento",
    ]

    edit_df = parcelas_contrato[edit_cols + ["eh_linha_resumo", "contrato"]].copy()
    edit_df["data_vencimento"] = pd.to_datetime(edit_df["data_vencimento"]).dt.date
    edit_df["valor_principal"] = edit_df["valor_principal"].round(2)
    edit_df["valor_total"] = edit_df["valor_total"].round(2)

    responsaveis_editor = ["Compradores"]
    if parcelas_contrato["responsavel_pagamento"].fillna("").eq("Corretora").any():
        responsaveis_editor.append("Corretora")

    st.markdown("### Edite os campos abaixo e clique em salvar")
    edited = st.data_editor(
        edit_df.drop(columns=["eh_linha_resumo"]),
        use_container_width=True,
        hide_index=True,
        disabled=["id", "contrato"] if eh_todos else ["id"],
        column_config={
            "id": st.column_config.NumberColumn("ID"),
            "contrato": st.column_config.TextColumn("Contrato"),
            "categoria": st.column_config.TextColumn("Categoria"),
            "origem": st.column_config.TextColumn("Origem"),
            "descricao_parcela": st.column_config.TextColumn("Descrição"),
            "numero_parcela": st.column_config.NumberColumn("Nº parcela"),
            "total_parcelas": st.column_config.NumberColumn("Total parcelas"),
            "data_vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
            "valor_principal": st.column_config.NumberColumn("Valor principal", format="%.2f"),
            "valor_total": st.column_config.NumberColumn("Valor total", format="%.2f"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["pendente", "pago", "atrasado"],
            ),
            "responsavel_pagamento": st.column_config.SelectboxColumn(
                "Responsável",
                options=responsaveis_editor,
            ),
        },
        key="editor_parcelas_novo",
    )

    if st.button("Salvar alterações das parcelas", type="primary"):
        try:
            original = edit_df.drop(columns=["eh_linha_resumo"]).set_index("id")
            novo = edited.set_index("id")

            alteradas = 0

            for parcela_id in novo.index:
                row_old = original.loc[parcela_id]
                row_new = novo.loc[parcela_id]

                venc_old = pd.to_datetime(row_old["data_vencimento"]).date()
                venc_new = pd.to_datetime(row_new["data_vencimento"]).date()

                payload = {}

                campos = [
                    "categoria",
                    "origem",
                    "descricao_parcela",
                    "numero_parcela",
                    "total_parcelas",
                    "valor_principal",
                    "valor_total",
                    "status",
                    "responsavel_pagamento",
                ]

                for campo in campos:
                    old_val = row_old[campo]
                    new_val = row_new[campo]

                    if pd.isna(old_val) and pd.isna(new_val):
                        continue

                    if old_val != new_val:
                        payload[campo] = new_val

                if venc_old != venc_new:
                    payload["data_vencimento"] = str(venc_new)

                if payload:
                    if "categoria" in payload:
                        payload["categoria"] = (
                            "registro" if str(payload["categoria"]).strip().lower() == "taxas cartoriais"
                            else payload["categoria"]
                        )

                    supabase.table("parcelas").update(payload).eq("id", int(parcela_id)).execute()
                    alteradas += 1

            if alteradas == 0:
                st.info("Nenhuma alteração detectada.")
            else:
                st.success(f"✅ {alteradas} parcela(s) atualizada(s) com sucesso!")
                time.sleep(0.8)
                st.rerun()

        except Exception as e:
            st.error(f"Erro ao salvar alterações: {e}")