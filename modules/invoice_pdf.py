
# modules/invoice_pdf.py

from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def money(paise):
    value = Decimal(int(paise or 0)) / Decimal(100)
    return f"Rs. {value:,.2f}"


def safe(value):
    if value is None or str(value).strip() == "":
        return "-"
    return escape(str(value))

def generate_invoice_pdf(details):
    """Generate invoice PDF in memory."""

    invoice = details["invoice"]
    items = details["items"]
    payments = details["payments"]

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=19,
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name="SmallText",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
    ))

    styles.add(ParagraphStyle(
        name="RightText",
        parent=styles["Normal"],
        alignment=TA_RIGHT,
    ))

    story = []

    # Business information: saved snapshot preferred
    business_name = invoice.get(
        "business_name_snapshot"
    ) or "SmartBill"

    business_address = invoice.get(
        "business_address_snapshot"
    )
    business_phone = invoice.get(
        "business_phone_snapshot"
    )
    business_gstin = invoice.get(
        "business_gstin_snapshot"
    )

    story.append(
        Paragraph("TAX INVOICE", styles["InvoiceTitle"])
    )

    story.append(Paragraph(
        f"<b>{safe(business_name)}</b>",
        styles["Heading2"],
    ))

    story.append(Paragraph(
        safe(business_address), styles["Normal"]
    ))

    story.append(Paragraph(
        f"Phone: {safe(business_phone)}",
        styles["Normal"],
    ))

    story.append(Paragraph(
        f"GSTIN: {safe(business_gstin)}",
        styles["Normal"],
    ))

    story.append(Spacer(1, 8 * mm))

    customer_name = invoice.get(
        "customer_name"
    ) or "Walk-in Customer"

    customer_address = invoice.get("customer_address")
    customer_phone = invoice.get("customer_phone")
    customer_gstin = invoice.get("customer_gstin")

    info = [
        [
            Paragraph(
                f"<b>Invoice No:</b> "
                f"{safe(invoice['invoice_number'])}",
                styles["Normal"],
            ),
            Paragraph(
                f"<b>Date:</b> "
                f"{safe(invoice['invoice_date'])}",
                styles["RightText"],
            ),
        ],
        [
            Paragraph(
                f"<b>Customer:</b> {safe(customer_name)}",
                styles["Normal"],
            ),
            Paragraph(
                f"<b>Status:</b> {safe(invoice['status'])}",
                styles["RightText"],
            ),
        ],
        [
            Paragraph(
                f"<b>Address:</b> {safe(customer_address)}",
                styles["SmallText"],
            ),
            Paragraph(
                f"<b>Payment:</b> "
                f"{safe(invoice['payment_status'])}",
                styles["RightText"],
            ),
        ],
        [
            Paragraph(
                f"<b>Phone:</b> {safe(customer_phone)}",
                styles["SmallText"],
            ),
            Paragraph(
                f"<b>Customer GSTIN:</b> "
                f"{safe(customer_gstin)}",
                styles["RightText"],
            ),
        ],
    ]

    info_table = Table(info, colWidths=[90*mm, 90*mm])

    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(info_table)
    story.append(Spacer(1, 8 * mm))

    # Item table
    data = [[
        "Item",
        "SKU",
        "Qty",
        "Unit Price",
        "Discount",
        "Tax",
        "Total",
    ]]

    for item in items:
        quantity = Decimal(
            int(item["quantity_milli"])
        ) / Decimal(1000)

        data.append([
            Paragraph(
                safe(item["product_name"]),
                styles["SmallText"],
            ),
            safe(item.get("sku")),
            f"{quantity:,.3f}".rstrip("0").rstrip("."),
            money(item["unit_price_paise"]),
            money(item["discount_paise"]),
            money(item["tax_paise"]),
            money(item["line_total_paise"]),
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            42*mm, 22*mm, 15*mm, 24*mm,
            23*mm, 21*mm, 27*mm
        ],
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    story.append(Spacer(1, 8 * mm))

    # Totals
    totals = [
        ["Subtotal", money(invoice["subtotal_paise"])],
        ["Discount", money(invoice["discount_paise"])],
        ["Tax", money(invoice["tax_paise"])],
        ["Grand Total", money(invoice["total_paise"])],
        ["Amount Paid", money(details["paid_paise"])],
        ["Balance Due", money(details["balance_paise"])],
    ]

    totals_table = Table(
        [["Description", "Amount"]] + totals,
        colWidths=[55*mm, 35*mm],
        hAlign="RIGHT",
    )

    totals_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(totals_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(
        "<b>Payment Records</b>",
        styles["Heading3"],
    ))

    if payments:
        payment_data = [
            ["Date", "Method", "Amount", "Status"]
        ]

        for payment in payments:
            payment_data.append([
                safe(payment["payment_date"]),
                safe(payment["method"]),
                money(payment["amount_paise"]),
                safe(payment["status"]),
            ])

        payment_table = Table(
            payment_data,
            colWidths=[48*mm, 40*mm, 45*mm, 45*mm],
        )

        payment_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))

        story.append(payment_table)
    else:
        story.append(Paragraph(
            "No payment records.",
            styles["Normal"],
        ))

    notes = invoice.get("notes")

    if notes:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(
            f"<b>Notes:</b> {safe(notes)}",
            styles["SmallText"],
        ))

    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph(
        "Thank you for your purchase!",
        styles["Normal"],
    ))

    doc.build(story)

    buffer.seek(0)
    return buffer.getvalue()
