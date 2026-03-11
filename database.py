#database.py

import pandas as pd
import streamlit as st

from utils import normalizar_categoria, normalizar_status_banco


def load_parcelas(supabase):
    try:
        res = supabase.table("parcelas").select("*").order("numero_parcela").execute()
        df = pd.DataFrame(res.data)

        if df.empty:
            return df

        if "data_vencimento" in df.columns:
            df["data_vencimento"] = pd.to_datetime(df["data_vencimento"], errors="coerce")

        if "data_pagamento" in df.columns:
            df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce")

        for col in ["valor_principal", "valor_total", "valor_pago"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in [
            "contrato",
            "categoria",
            "origem",
            "descricao_parcela",
            "status",
            "responsavel_pagamento",
        ]:
            if col not in df.columns:
                df[col] = None

        df["status"] = df["status"].apply(normalizar_status_banco)
        df["categoria"] = df["categoria"].apply(normalizar_categoria)

        df["valor_principal"] = df["valor_principal"].fillna(0.0)
        df["valor_total"] = df["valor_total"].fillna(0.0)

        if "valor_pago" in df.columns:
            df["valor_pago"] = pd.to_numeric(df["valor_pago"], errors="coerce")

        df["eh_linha_resumo"] = (
            df["categoria"].fillna("").astype(str).str.lower().eq(" banco")
            | df["descricao_parcela"].fillna("").astype(str).str.lower().str.contains("corretora", na=False)
        )

        return df

    except Exception as e:
        st.error(f"Erro ao carregar parcelas: {e}")
        return pd.DataFrame()


def registrar_pagamento(supabase, parcela_id, data_pagamento, valor_pago, responsavel_pagamento):
    supabase.table("parcelas").update(
        {
            "status": "pago",
            "data_pagamento": str(data_pagamento),
            "valor_pago": float(valor_pago),
            "responsavel_pagamento": responsavel_pagamento,
        }
    ).eq("id", int(parcela_id)).execute()

    res_check = (
        supabase.table("parcelas")
        .select("id,status,data_pagamento,valor_pago,responsavel_pagamento")
        .eq("id", int(parcela_id))
        .execute()
    )

    return res_check.data


def atualizar_pagamento_existente(supabase, parcela_id, data_pagamento, valor_pago, responsavel_pagamento):
    supabase.table("parcelas").update(
        {
            "data_pagamento": str(data_pagamento),
            "valor_pago": float(valor_pago),
            "responsavel_pagamento": responsavel_pagamento,
        }
    ).eq("id", int(parcela_id)).execute()

    res_check = (
        supabase.table("parcelas")
        .select("id,status,data_pagamento,valor_pago,responsavel_pagamento")
        .eq("id", int(parcela_id))
        .execute()
    )

    return res_check.data


def desfazer_pagamento(supabase, parcela_id):
    supabase.table("parcelas").update(
        {
            "status": "pendente",
            "data_pagamento": None,
            "valor_pago": None,
        }
    ).eq("id", int(parcela_id)).execute()

    res_check = (
        supabase.table("parcelas")
        .select("id,status,data_pagamento,valor_pago")
        .eq("id", int(parcela_id))
        .execute()
    )

    return res_check.data