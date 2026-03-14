from datetime import date
import pandas as pd
import streamlit as st

from utils import (
    CONTRATO_DIRECIONAL,
    CONTRATO_TODOS,
    CONTRATO_TAXAS,
    brl,
)

MAPA_MESES = {
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

st.markdown("""
<style>
div[data-testid="stWidgetLabel"] {
    margin-bottom: 10px !important;
}

/* espaço geral dos botões */
div.stButton {
    margin-top: 0 !important;
}

/* botão primário */
div.stButton > button[data-testid="stBaseButton-primary"] {
    background: rgba(34, 197, 94, 0.45) !important;
    border: 1px solid rgba(34, 197, 94, 0.55) !important;
    color: white !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}

/* hover botão primário */
div.stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: rgba(34, 197, 94, 0.58) !important;
    border: 1px solid rgba(34, 197, 94, 0.68) !important;
    color: white !important;
}

/* botão secundário */
div.stButton > button[data-testid="stBaseButton-secondary"] {
    background: rgba(239, 68, 68, 0.16) !important;
    border: 1px solid rgba(239, 68, 68, 0.26) !important;
    color: #8b1e1e !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}

/* hover botão secundário */
div.stButton > button[data-testid="stBaseButton-secondary"]:hover {
    background: rgba(239, 68, 68, 0.24) !important;
    border: 1px solid rgba(239, 68, 68, 0.34) !important;
    color: #7a1616 !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def _is_evolucao_obra(valor_contrato) -> bool:
    contrato = str(valor_contrato).strip().lower()
    return contrato in ["evolução de obra", "evolucao de obra"]


def _formatar_mes_referencia(valor_data):
    data_ref = pd.to_datetime(valor_data, errors="coerce")
    if pd.isnull(data_ref):
        return "-"
    return f"{MAPA_MESES[data_ref.month]}/{data_ref.year}"


def _data_vencimento_padrao(ano, mes):
    return date(ano, mes, 24)


def _proximo_mes(ano, mes):
    if mes == 12:
        return ano + 1, 1
    return ano, mes + 1


def _texto_parcela(row):
    num = int(row["numero_parcela"]) if pd.notnull(row.get("numero_parcela")) else 0

    if _is_evolucao_obra(row.get("contrato")):
        return f"{num}/{num}"

    total = int(row["total_parcelas"]) if pd.notnull(row.get("total_parcelas")) else 0
    return f"{num}/{total}"


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


def _update_contrato_encerrado(supabase, contrato: str, encerrado: bool):
    return (
        supabase.table("parcelas")
        .update({"contrato_encerrado": encerrado})
        .eq("contrato", contrato)
        .execute()
    )


def _garantir_parcelas_evolucao_obra(supabase, parcelas: pd.DataFrame):
    if parcelas.empty:
        return False

    if not _is_evolucao_obra(parcelas["contrato"].iloc[0]):
        return False

    if "contrato_encerrado" in parcelas.columns:
        if parcelas["contrato_encerrado"].fillna(False).astype(bool).any():
            return False

    contrato_real = str(parcelas["contrato"].iloc[0]).strip()

    hoje = date.today()
    limite_final = date(2027, 2, 24)

    ano_alvo = hoje.year
    mes_alvo = hoje.month
    data_alvo = _data_vencimento_padrao(ano_alvo, mes_alvo)

    if data_alvo > limite_final:
        data_alvo = limite_final

    datas_existentes = set(
        pd.to_datetime(parcelas["data_vencimento"], errors="coerce")
        .dropna()
        .dt.date
        .tolist()
    )

    if parcelas["numero_parcela"].dropna().empty:
        ultimo_numero = 0
    else:
        ultimo_numero = int(parcelas["numero_parcela"].dropna().max())

    if parcelas["data_vencimento"].dropna().empty:
        return False

    ultima_data_existente = pd.to_datetime(parcelas["data_vencimento"], errors="coerce").dropna().max().date()
    ano_cursor, mes_cursor = _proximo_mes(ultima_data_existente.year, ultima_data_existente.month)

    inserts = []

    while True:
        data_venc = _data_vencimento_padrao(ano_cursor, mes_cursor)

        if data_venc > data_alvo or data_venc > limite_final:
            break

        if data_venc not in datas_existentes:
            ultimo_numero += 1
            referencia = f"{MAPA_MESES[mes_cursor]}/{ano_cursor}"

            inserts.append({
                "contrato": contrato_real,
                "descricao_parcela": f"Evolução de Obra - {referencia}",
                "numero_parcela": ultimo_numero,
                "total_parcelas": ultimo_numero,
                "data_vencimento": _date_to_iso(data_venc),
                "data_pagamento": None,
                "valor_principal": 0.0,
                "valor_total": 0.0,
                "valor_pago": None,
                "status": "pendente",
                "responsavel_pagamento": "Compradores",
                "contrato_encerrado": False,
            })

        ano_cursor, mes_cursor = _proximo_mes(ano_cursor, mes_cursor)

    if inserts:
        supabase.table("parcelas").insert(inserts).execute()
        return True

    return False


def _build_label_pendente(row, eh_todos=False):
    data_venc = pd.to_datetime(row.get("data_vencimento"), errors="coerce")
    data_venc_str = data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-"
    contrato = str(row.get("contrato", "")).strip()
    parcela_txt = _texto_parcela(row)
    return f"{contrato} | {parcela_txt} |  {data_venc_str}"


def _build_label_pago(row, eh_todos=False):
    data_venc = pd.to_datetime(row.get("data_vencimento"), errors="coerce")
    data_venc_str = data_venc.strftime("%d/%m/%Y") if pd.notnull(data_venc) else "-"
    contrato = str(row.get("contrato", "")).strip()
    parcela_txt = _texto_parcela(row)
    return f"{contrato} | {parcela_txt} | {data_venc_str}"


def registrar_pagamento(
    supabase,
    parcela_id,
    data_pagamento,
    valor_pago,
    responsavel_pagamento,
    contrato,
    numero_parcela,
    eh_evolucao_obra=False,
    ultima_parcela=False,
):
    payload = {
        "data_pagamento": _date_to_iso(data_pagamento),
        "valor_pago": float(valor_pago),
        "responsavel_pagamento": responsavel_pagamento,
        "status": "pago",
    }

    if eh_evolucao_obra:
        payload["total_parcelas"] = int(numero_parcela)
        payload["contrato_encerrado"] = bool(ultima_parcela)
        payload["valor_total"] = float(valor_pago)
        payload["valor_principal"] = float(valor_pago)

    resposta = _update_parcela(supabase, parcela_id, payload)

    if eh_evolucao_obra:
        _update_contrato_encerrado(supabase, contrato, bool(ultima_parcela))

    return resposta


def atualizar_pagamento_existente(
    supabase,
    parcela_id,
    data_pagamento,
    valor_pago,
    responsavel_pagamento,
    contrato,
    numero_parcela,
    eh_evolucao_obra=False,
    ultima_parcela=False,
):
    payload = {
        "data_pagamento": _date_to_iso(data_pagamento),
        "valor_pago": float(valor_pago),
        "responsavel_pagamento": responsavel_pagamento,
        "status": "pago",
    }

    if eh_evolucao_obra:
        payload["total_parcelas"] = int(numero_parcela)
        payload["contrato_encerrado"] = bool(ultima_parcela)
        payload["valor_total"] = float(valor_pago)
        payload["valor_principal"] = float(valor_pago)

    resposta = _update_parcela(supabase, parcela_id, payload)

    if eh_evolucao_obra:
        _update_contrato_encerrado(supabase, contrato, bool(ultima_parcela))

    return resposta


def desfazer_pagamento(
    supabase,
    parcela_id,
    contrato=None,
    eh_evolucao_obra=False,
):
    payload = {
        "data_pagamento": None,
        "valor_pago": None,
        "status": "pendente",
    }

    if eh_evolucao_obra:
        payload["contrato_encerrado"] = False
        payload["valor_total"] = 0.0
        payload["valor_principal"] = 0.0

    resposta = _update_parcela(supabase, parcela_id, payload)

    if eh_evolucao_obra and contrato:
        _update_contrato_encerrado(supabase, contrato, False)

    return resposta


# =========================================================
# TAB: REGISTRAR / EDITAR PAGAMENTO
# =========================================================
def render_pagamentos_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar):
    st.markdown("""
    <style>
    div[data-testid="stWidgetLabel"] {
        margin-bottom: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    eh_todos = contrato_selecionado == CONTRATO_TODOS
    contrato_eh_evolucao = _is_evolucao_obra(contrato_selecionado)
    exibir_responsavel = contrato_selecionado == CONTRATO_TAXAS

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

    if contrato_eh_evolucao:
        if _garantir_parcelas_evolucao_obra(supabase, parcelas):
            st.rerun()
            return

    if contrato_eh_evolucao and "contrato_encerrado" in parcelas.columns:
        contrato_encerrado = parcelas["contrato_encerrado"].fillna(False).astype(bool).any()

        c1, c2 = st.columns([2, 1])

        with c1:
            if contrato_encerrado:
                st.markdown(
                    """
                    <div style="
                        background-color: rgba(40, 167, 69, 0.12);
                        color: #155724;
                        padding: 0.75rem 1rem;
                        border-radius: 0.5rem;
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 0.5rem;
                        text-align: center;
                    ">
                        <span style="display:flex; align-items:center; justify-content:center;">✅</span>
                        <span>Evolução de Obra está marcada como concluída.</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="
                        background-color: rgba(23, 162, 184, 0.12);
                        color: #0c5460;
                        padding: 0.75rem 1rem;
                        border-radius: 0.5rem;
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 0.5rem;
                        text-align: center;
                    ">
                        <span style="display:flex; align-items:center; justify-content:center;">ℹ️</span>
                        <span>Evolução de Obra está em andamento.</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with c2:
            if st.button("Retomar Evolução de Obra", key="btn_retomar_evolucao"):
                try:
                    _update_contrato_encerrado(supabase, "Evolução de Obra", False)
                    st.success("✅ Evolução de Obra retomada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao retomar Evolução de Obra: {e}")

        st.markdown("---")

    st.markdown(
        "<h3 style='text-align: center;'>Registrar Pagamento</h3>",
        unsafe_allow_html=True
    )

    pendentes = parcelas[parcelas["status"] != "pago"].copy()

    if pendentes.empty:
        st.success("✅ Todas as parcelas desse contrato já estão pagas.")
    else:
        pendentes = pendentes.sort_values(["data_vencimento", "numero_parcela"]).copy()
        pendentes["label"] = pendentes.apply(lambda row: _build_label_pendente(row, eh_todos=eh_todos), axis=1)

        parcela_label = st.selectbox(
            "Selecione a parcela",
            pendentes["label"].tolist(),
            index=0,
            key="tab3_selecao_pendente",
        )
        
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        parcela_sel = pendentes[pendentes["label"] == parcela_label].iloc[0]
        parcela_eh_evolucao = _is_evolucao_obra(parcela_sel.get("contrato"))

        responsavel_pagamento = "Compradores"
        if exibir_responsavel:
            responsaveis_opcoes = ["Compradores"]
            if parcelas["responsavel_pagamento"].fillna("").astype(str).eq("Corretora").any():
                responsaveis_opcoes.append("Corretora")

        if parcela_eh_evolucao:
            ref_mes = _formatar_mes_referencia(parcela_sel.get("data_vencimento"))
            data_pag_fixa = _to_date_or_none(parcela_sel.get("data_vencimento")) or date.today()

            if exibir_responsavel:
                c1, c2, c3 = st.columns(3, gap="large")

                with c1:
                    st.text_input(
                        "Mês de referência",
                        value=ref_mes,
                        disabled=True,
                        key="novo_pagamento_mes_ref_evolucao",
                    )

                with c2:
                    st.date_input(
                        "Data do pagamento",
                        value=data_pag_fixa,
                        format="DD/MM/YYYY",
                        disabled=True,
                        key="novo_pagamento_data_evolucao",
                    )

                with c3:
                    st.selectbox(
                        "Responsável pelo pagamento",
                        options=["Compradores"],
                        index=0,
                        disabled=True,
                        key="novo_pagamento_resp_evolucao",
                    )
            else:
                c1, c2 = st.columns(2)

                with c1:
                    st.text_input(
                        "Mês de referência",
                        value=ref_mes,
                        disabled=True,
                        key="novo_pagamento_mes_ref_evolucao",
                    )

                with c2:
                    st.date_input(
                        "Data do pagamento",
                        value=data_pag_fixa,
                        format="DD/MM/YYYY",
                        disabled=True,
                        key="novo_pagamento_data_evolucao",
                    )

            valor_pago = st.number_input(
                "Valor pago",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key="novo_pagamento_valor_evolucao",
            )

            ultima_parcela = st.checkbox(
                "Esta é a última parcela da Evolução de Obra?",
                value=False,
                key="checkbox_ultima_parcela_evolucao",
            )

            data_pagamento = data_pag_fixa

        else:
            if exibir_responsavel:
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
                    idx_resp = 0
                    if parcela_sel.get("responsavel_pagamento") in responsaveis_opcoes:
                        idx_resp = responsaveis_opcoes.index(parcela_sel["responsavel_pagamento"])

                    responsavel_pagamento = st.selectbox(
                        "Responsável pelo pagamento",
                        options=responsaveis_opcoes,
                        index=idx_resp,
                        key="novo_pagamento_resp",
                    )
            else:
                c1, c2 = st.columns(2)

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

            ultima_parcela = False

            _, col_btn_centro, _ = st.columns([1, 3, 1])

            with col_btn_centro:
                if st.button("Registrar Pagamento", type="primary", key="btn_registrar_pagamento", use_container_width=True):
                    try:
                        dados_atualizados = registrar_pagamento(
                            supabase=supabase,
                            parcela_id=parcela_sel["id"],
                            data_pagamento=data_pagamento,
                            valor_pago=valor_pago,
                            responsavel_pagamento=responsavel_pagamento,
                            contrato=str(parcela_sel.get("contrato", "")),
                            numero_parcela=int(parcela_sel["numero_parcela"]) if pd.notnull(parcela_sel.get("numero_parcela")) else 0,
                            eh_evolucao_obra=parcela_eh_evolucao,
                            ultima_parcela=ultima_parcela,
                        )

                        if not dados_atualizados:
                            st.error("O banco não retornou a parcela atualizada.")
                        else:
                            st.success("✅ Pagamento registrado com sucesso!")
                            st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao registrar pagamento: {e}")

    st.markdown("---")
    st.markdown(
        "<h3 style='text-align: center;'>Editar Parcela</h3>",
        unsafe_allow_html=True
    )

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

    st.markdown("<div style='height: 35px;'></div>", unsafe_allow_html=True)

    parcela_paga = pagas[pagas["label"] == parcela_paga_label].iloc[0]
    parcela_paga_eh_evolucao = _is_evolucao_obra(parcela_paga.get("contrato"))

    novo_responsavel = "Compradores"
    if exibir_responsavel:
        responsaveis_opcoes_edit = ["Compradores"]
        if parcelas["responsavel_pagamento"].fillna("").astype(str).eq("Corretora").any():
            responsaveis_opcoes_edit.append("Corretora")

    if parcela_paga_eh_evolucao:
        ref_mes_edit = _formatar_mes_referencia(parcela_paga.get("data_vencimento"))
        data_pagamento_fixa_edit = _to_date_or_none(parcela_paga.get("data_vencimento")) or date.today()

        if exibir_responsavel:
            e1, e2, e3 = st.columns(3)

            with e1:
                st.text_input(
                    "Mês de referência",
                    value=ref_mes_edit,
                    disabled=True,
                    key="edit_mes_ref_evolucao",
                )

            with e2:
                st.date_input(
                    "Data do pagamento",
                    value=data_pagamento_fixa_edit,
                    format="DD/MM/YYYY",
                    disabled=True,
                    key="edit_data_pagamento_evolucao",
                )
                nova_data_pagamento = data_pagamento_fixa_edit

            with e3:
                st.selectbox(
                    "Responsável",
                    options=["Compradores"],
                    index=0,
                    disabled=True,
                    key="edit_responsavel_evolucao",
                )
        else:
            e1, e2 = st.columns(2)

            with e1:
                st.text_input(
                    "Mês de referência",
                    value=ref_mes_edit,
                    disabled=True,
                    key="edit_mes_ref_evolucao",
                )

            with e2:
                st.date_input(
                    "Data do pagamento",
                    value=data_pagamento_fixa_edit,
                    format="DD/MM/YYYY",
                    disabled=True,
                    key="edit_data_pagamento_evolucao",
                )
                nova_data_pagamento = data_pagamento_fixa_edit

        novo_valor_pago = st.number_input(
            "Novo valor pago",
            min_value=0.0,
            value=float(parcela_paga["valor_pago"]) if pd.notnull(parcela_paga.get("valor_pago")) else 0.0,
            step=0.01,
            format="%.2f",
            key="edit_valor_pago_evolucao",
        )

        valor_inicial_ultima = bool(parcela_paga.get("contrato_encerrado", False))
        ultima_parcela_edit = st.checkbox(
            "Esta é a última parcela da Evolução de Obra?",
            value=valor_inicial_ultima,
            key="checkbox_ultima_parcela_edit_evolucao",
        )

    else:
        if exibir_responsavel:
            e1, e2, e3 = st.columns(3)

            with e1:
                valor_data_atual = _to_date_or_none(parcela_paga.get("data_pagamento")) or date.today()
                nova_data_pagamento = st.date_input(
                    "Nova data do pagamento",
                    value=valor_data_atual,
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
                idx_edit = 0
                if parcela_paga.get("responsavel_pagamento") in responsaveis_opcoes_edit:
                    idx_edit = responsaveis_opcoes_edit.index(parcela_paga["responsavel_pagamento"])

                novo_responsavel = st.selectbox(
                    "Responsável",
                    options=responsaveis_opcoes_edit,
                    index=idx_edit,
                    key="edit_responsavel",
                )
        else:
            e1, e2 = st.columns(2)

            with e1:
                valor_data_atual = _to_date_or_none(parcela_paga.get("data_pagamento")) or date.today()
                nova_data_pagamento = st.date_input(
                    "Nova data do pagamento",
                    value=valor_data_atual,
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

        ultima_parcela_edit = False

    st.markdown("<div style='height: 35px;'></div>", unsafe_allow_html=True)

    b1, b2 = st.columns([1, 1], gap="small")

    with b1:
        if st.button(
            "Salvar Edição",
            type="primary",
            key="btn_salvar_edicao_pagamento",
            use_container_width=True
        ):
            try:
                dados_atualizados = atualizar_pagamento_existente(
                    supabase=supabase,
                    parcela_id=parcela_paga["id"],
                    data_pagamento=nova_data_pagamento,
                    valor_pago=novo_valor_pago,
                    responsavel_pagamento=novo_responsavel,
                    contrato=str(parcela_paga.get("contrato", "")),
                    numero_parcela=int(parcela_paga["numero_parcela"]) if pd.notnull(parcela_paga.get("numero_parcela")) else 0,
                    eh_evolucao_obra=parcela_paga_eh_evolucao,
                    ultima_parcela=ultima_parcela_edit,
                )

                if not dados_atualizados:
                    st.error("O banco não retornou a parcela atualizada.")
                else:
                    st.success("✅ Pagamento atualizado com sucesso!")
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao atualizar pagamento: {e}")

    with b2:
        if st.button(
            "Desfazer Pagamento",
            key="btn_desfazer_pagamento",
            use_container_width=True
        ):
            try:
                dados_atualizados = desfazer_pagamento(
                    supabase=supabase,
                    parcela_id=parcela_paga["id"],
                    contrato=str(parcela_paga.get("contrato", "")),
                    eh_evolucao_obra=parcela_paga_eh_evolucao,
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
            "contrato_encerrado",
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
            f"{str(row.get('contrato', '')).strip()} | "
            f"{_texto_parcela(row)} | "
            f"vence "
            f"{pd.to_datetime(row['data_vencimento'], errors='coerce').strftime('%d/%m/%Y') if pd.notnull(row.get('data_vencimento')) else '-'}"
        ),
        axis=1,
    )

    parcela_label = st.selectbox(
        "Selecione a parcela para atualizar",
        parcelas["label_parcela"].tolist(),
        key="atualizar_parcela_select",
    )

    parcela_escolhida = parcelas[parcelas["label_parcela"] == parcela_label].iloc[0]
    parcela_escolhida_eh_evolucao = _is_evolucao_obra(parcela_escolhida.get("contrato"))
    exibir_responsavel = contrato_selecionado == CONTRATO_TAXAS

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
        if exibir_responsavel:
            col1, col2 = st.columns(2)
        else:
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

            if exibir_responsavel:
                novo_responsavel = st.selectbox(
                    "Responsável",
                    opcoes_responsavel,
                    index=indice_resp,
                    disabled=parcela_escolhida_eh_evolucao,
                )
            else:
                novo_responsavel = "Compradores"

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
                "responsavel_pagamento": "Compradores" if (parcela_escolhida_eh_evolucao or not exibir_responsavel) else novo_responsavel,
            }

            if parcela_escolhida_eh_evolucao and pd.notnull(parcela_escolhida.get("numero_parcela")):
                payload["total_parcelas"] = int(parcela_escolhida["numero_parcela"])

            _update_parcela(supabase, parcela_id, payload)

            st.success("Parcela atualizada com sucesso.")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao atualizar parcela: {e}")