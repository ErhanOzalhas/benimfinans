from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from services.prices import format_try


def excel_bytes(assets: pd.DataFrame, transactions: pd.DataFrame, snapshots: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        assets.to_excel(writer, sheet_name="Portfoy", index=False)
        transactions.to_excel(writer, sheet_name="Islemler", index=False)
        snapshots.to_excel(writer, sheet_name="Gecmis", index=False)
    buffer.seek(0)
    return buffer.getvalue()


def pdf_bytes(total: float, assets: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    y = h - 50
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "Benim Finans - Portfoy Raporu")
    y -= 35
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    y -= 22
    c.drawString(50, y, f"Toplam Portfoy: {format_try(total)}")
    y -= 35
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Varlik")
    c.drawString(180, y, "Kategori")
    c.drawString(280, y, "Miktar")
    c.drawString(370, y, "Toplam TL")
    y -= 16
    c.setFont("Helvetica", 9)
    for _, r in assets.head(28).iterrows():
        c.drawString(50, y, str(r.get("name", ""))[:20])
        c.drawString(180, y, str(r.get("category", ""))[:15])
        c.drawString(280, y, f"{float(r.get('quantity',0) or 0):.4f}")
        c.drawString(370, y, format_try(float(r.get("total_try",0) or 0)))
        y -= 14
        if y < 60:
            c.showPage(); y = h - 50
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
