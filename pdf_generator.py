"""
PDF Quote Generator for Simple CRM
Generates professional quotes matching the Steelstack format.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from io import BytesIO
from pathlib import Path
from datetime import datetime

# Steelstack brand colors
STEELSTACK_RED = colors.HexColor('#d80010')
STEELSTACK_DARK = colors.HexColor('#0a1622')
STEELSTACK_GRAY = colors.HexColor('#6b7280')

STATIC_PATH = Path(__file__).parent / "static"


def format_currency(amount):
    """Format a number as currency."""
    if amount is None:
        amount = 0
    return "${:,.2f}".format(float(amount))


def format_date(date_str):
    """Format a date string nicely."""
    if not date_str:
        return ""
    try:
        if isinstance(date_str, str):
            # Handle various date formats
            for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                try:
                    dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
                    return dt.strftime('%B %d, %Y')
                except:
                    continue
        return date_str
    except:
        return date_str


def generate_quote_pdf(quote, items):
    """
    Generate a PDF quote document.

    Args:
        quote: Dict with quote data
        items: List of quote line items

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    # Styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'QuoteTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.white,
        spaceAfter=0,
        fontName='Helvetica-Bold'
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.white,
        leading=14
    )

    section_header = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=STEELSTACK_DARK,
        spaceBefore=20,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14
    )

    small_style = ParagraphStyle(
        'SmallStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=STEELSTACK_GRAY,
        leading=12
    )

    right_style = ParagraphStyle(
        'RightStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        leading=14
    )

    elements = []

    # ========== LOGO HEADER ==========
    logo_path = STATIC_PATH / "logo.png"
    if logo_path.exists():
        # Create header with logo on dark background
        logo = Image(str(logo_path), width=2*inch, height=0.5*inch)
        logo.hAlign = 'LEFT'

        # Logo table with dark background
        logo_table = Table([[logo]], colWidths=[7.5*inch])
        logo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), STEELSTACK_DARK),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ]))
        elements.append(logo_table)

    elements.append(Spacer(1, 0.1*inch))

    # ========== TITLE BANNER ==========
    customer_name = quote.get('customer_name') or quote.get('customer_company') or 'Customer'
    title_text = f"STEELSTACK | {customer_name.upper()}"
    title_para = Paragraph(title_text, title_style)

    # Customer info (left side)
    customer_info = []
    if quote.get('customer_name'):
        customer_info.append(f"<b>{quote['customer_name']}</b>")
    if quote.get('customer_email'):
        customer_info.append(quote['customer_email'])
    if quote.get('customer_phone'):
        customer_info.append(quote['customer_phone'])

    customer_text = "<br/>".join(customer_info) if customer_info else ""
    customer_para = Paragraph(customer_text, header_style)

    # Quote info (right side)
    quote_info = []
    quote_info.append(f"Reference: {quote.get('quote_number', '')}")
    quote_info.append(f"Quote created: {format_date(quote.get('quote_date') or quote.get('created_at'))}")
    if quote.get('expiry_date'):
        quote_info.append(f"Quote expires: {format_date(quote['expiry_date'])}")
    if quote.get('salesperson_name'):
        quote_info.append(f"Quote created by: {quote['salesperson_name']}")
    if quote.get('salesperson_email'):
        quote_info.append(f"<br/>{quote['salesperson_email']}")

    quote_text = "<br/>".join(quote_info)
    quote_para = Paragraph(quote_text, ParagraphStyle(
        'QuoteInfo',
        parent=header_style,
        alignment=TA_RIGHT
    ))

    # Title banner table
    banner_data = [
        [title_para, ''],
        [customer_para, quote_para]
    ]
    banner_table = Table(banner_data, colWidths=[3.75*inch, 3.75*inch])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), STEELSTACK_DARK),
        ('SPAN', (0, 0), (1, 0)),  # Title spans both columns
        ('TOPPADDING', (0, 0), (-1, 0), 20),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 20),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(banner_table)

    elements.append(Spacer(1, 0.3*inch))

    # ========== COMMENTS SECTION ==========
    if quote.get('notes'):
        salesperson = quote.get('salesperson_name', 'Salesperson')
        elements.append(Paragraph(f"<b>Comments from {salesperson}</b>", section_header))

        # Notes box
        notes_para = Paragraph(quote['notes'].replace('\n', '<br/>'), normal_style)
        notes_table = Table([[notes_para]], colWidths=[7.5*inch])
        notes_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(notes_table)
        elements.append(Spacer(1, 0.2*inch))

    # ========== PRODUCTS TABLE ==========
    elements.append(Paragraph("<b>Products & Services</b>", section_header))

    # Table header
    table_data = [
        [
            Paragraph('<b>Item & Description</b>', normal_style),
            Paragraph('<b>Quantity</b>', ParagraphStyle('', parent=normal_style, alignment=TA_CENTER)),
            Paragraph('<b>Unit Price</b>', ParagraphStyle('', parent=normal_style, alignment=TA_RIGHT)),
            Paragraph('<b>Total</b>', ParagraphStyle('', parent=normal_style, alignment=TA_RIGHT))
        ]
    ]

    # Add items
    for item in items:
        item_content = f"<b>{item.get('product_name', '')}</b>"
        if item.get('description'):
            # Add description on new lines
            desc_lines = item['description'].replace('\n', '<br/>')
            item_content += f"<br/><font size=9 color='#6b7280'>{desc_lines}</font>"

        table_data.append([
            Paragraph(item_content, normal_style),
            Paragraph(str(int(item.get('quantity', 1)) if item.get('quantity', 1) == int(item.get('quantity', 1)) else item.get('quantity', 1)),
                     ParagraphStyle('', parent=normal_style, alignment=TA_CENTER)),
            Paragraph(format_currency(item.get('unit_price', 0)),
                     ParagraphStyle('', parent=normal_style, alignment=TA_RIGHT)),
            Paragraph(format_currency(item.get('line_total', 0)),
                     ParagraphStyle('', parent=normal_style, alignment=TA_RIGHT))
        ])

    # Create table
    products_table = Table(table_data, colWidths=[4.5*inch, 0.8*inch, 1.1*inch, 1.1*inch])
    products_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f9fafb')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#e5e7eb')),
        # All rows
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        # Item rows - bottom border
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(products_table)

    elements.append(Spacer(1, 0.2*inch))

    # ========== TOTALS ==========
    totals_data = []

    # Subtotal
    totals_data.append([
        '', '',
        Paragraph('Subtotal', right_style),
        Paragraph(format_currency(quote.get('subtotal', 0)), right_style)
    ])

    # Discount if applicable
    if quote.get('discount_percent') and float(quote.get('discount_percent', 0)) > 0:
        totals_data.append([
            '', '',
            Paragraph(f"Discount ({quote['discount_percent']}%)", right_style),
            Paragraph(f"-{format_currency(quote.get('discount_amount', 0))}", right_style)
        ])

    # Tax if applicable
    if quote.get('tax_percent') and float(quote.get('tax_percent', 0)) > 0:
        totals_data.append([
            '', '',
            Paragraph(f"Tax ({quote['tax_percent']}%)", right_style),
            Paragraph(format_currency(quote.get('tax_amount', 0)), right_style)
        ])

    # Total
    totals_data.append([
        '', '',
        Paragraph('<b>Total</b>', ParagraphStyle('', parent=right_style, fontSize=12)),
        Paragraph(f"<b>{format_currency(quote.get('total', 0))}</b>",
                 ParagraphStyle('', parent=right_style, fontSize=12))
    ])

    totals_table = Table(totals_data, colWidths=[4.5*inch, 0.8*inch, 1.1*inch, 1.1*inch])
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEABOVE', (2, -1), (-1, -1), 1, colors.HexColor('#374151')),
    ]))
    elements.append(totals_table)

    # ========== PAGE 2: TERMS ==========
    elements.append(PageBreak())

    # Purchase Terms
    if quote.get('terms'):
        elements.append(Paragraph("<b>Purchase terms</b>", section_header))
        terms_text = quote['terms'].replace('\n', '<br/>')
        elements.append(Paragraph(terms_text, normal_style))
        elements.append(Spacer(1, 0.3*inch))

    # ========== PAYMENT LINK ==========
    if quote.get('payment_link'):
        elements.append(Paragraph("<b>Ready to Pay?</b>", section_header))

        payment_link_style = ParagraphStyle(
            'PaymentLink',
            parent=normal_style,
            fontSize=11,
            textColor=colors.HexColor('#047857'),
            leading=16
        )

        payment_url = quote['payment_link']
        payment_text = f'Click here to pay securely online: <a href="{payment_url}" color="#047857"><u>{payment_url}</u></a>'
        elements.append(Paragraph(payment_text, payment_link_style))
        elements.append(Spacer(1, 0.3*inch))

    # ========== FINANCING LINK ==========
    if quote.get('financing_link'):
        elements.append(Paragraph("<b>Need Financing?</b>", section_header))

        financing_link_style = ParagraphStyle(
            'FinancingLink',
            parent=normal_style,
            fontSize=11,
            textColor=colors.HexColor('#2563eb'),
            leading=16
        )

        financing_url = quote['financing_link']
        financing_text = f'Apply for financing here: <a href="{financing_url}" color="#2563eb"><u>{financing_url}</u></a>'
        elements.append(Paragraph(financing_text, financing_link_style))
        elements.append(Spacer(1, 0.3*inch))

    # Contact section
    elements.append(Paragraph("<b>Questions? Contact me</b>", section_header))

    if quote.get('salesperson_name'):
        elements.append(Paragraph(quote['salesperson_name'], normal_style))
    if quote.get('salesperson_email'):
        elements.append(Paragraph(quote['salesperson_email'], small_style))

    elements.append(Spacer(1, 0.3*inch))

    # Company address
    company_address = """<b>STEELSTACK</b><br/>
1633 West Main Street<br/>
Suite 1200<br/>
Lebanon, TN 37087<br/>
United States"""
    elements.append(Paragraph(company_address, normal_style))

    elements.append(Spacer(1, 0.5*inch))

    # ========== SIGNATURE SECTION ==========
    elements.append(Paragraph("<b>Acceptance & Authorization</b>", section_header))
    elements.append(Paragraph("By signing below, I accept this quote and authorize the work described above.", small_style))
    elements.append(Spacer(1, 0.3*inch))

    # Signature lines
    sig_line_style = ParagraphStyle(
        'SigLine',
        parent=normal_style,
        fontSize=10,
        spaceBefore=5
    )

    sig_data = [
        [
            Paragraph('_' * 45, sig_line_style),
            Paragraph('', normal_style),
            Paragraph('_' * 25, sig_line_style)
        ],
        [
            Paragraph('<b>Signature</b>', small_style),
            Paragraph('', normal_style),
            Paragraph('<b>Date</b>', small_style)
        ],
        [Paragraph('', normal_style), '', ''],  # Spacer row
        [
            Paragraph('_' * 45, sig_line_style),
            '',
            ''
        ],
        [
            Paragraph('<b>Printed Name</b>', small_style),
            '',
            ''
        ]
    ]

    sig_table = Table(sig_data, colWidths=[3.5*inch, 0.5*inch, 2*inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


if __name__ == "__main__":
    # Test with sample data
    sample_quote = {
        'quote_number': 'Q-2025-0001',
        'customer_name': 'Test Customer',
        'customer_email': 'test@example.com',
        'customer_phone': '(555) 123-4567',
        'quote_date': '2025-01-19',
        'expiry_date': '2025-02-18',
        'salesperson_name': 'Ray Bishop',
        'salesperson_email': 'ray.bishop@steelstackusa.com',
        'notes': 'Thank you for your interest in Steelstack!',
        'terms': '50% due upon receipt of PO, 50% before shipping.',
        'subtotal': 21495.00,
        'discount_percent': 0,
        'discount_amount': 0,
        'tax_percent': 0,
        'tax_amount': 0,
        'total': 21495.00
    }

    sample_items = [
        {
            'product_name': '8FT 5\' x 10\' STACK MAX - (ASSEMBLED)',
            'description': 'Absolute Dimensions (Single Unit):\nWidth: 142.125", Depth: 72.25", and Height: 97.375"\nWeight Capacity: 5,000 lbs. per cassette.',
            'quantity': 1,
            'unit_price': 19995.00,
            'line_total': 19995.00
        },
        {
            'product_name': 'Shipping TN > VA',
            'quantity': 1,
            'unit_price': 1500.00,
            'line_total': 1500.00
        }
    ]

    pdf_buffer = generate_quote_pdf(sample_quote, sample_items)
    with open('test_quote.pdf', 'wb') as f:
        f.write(pdf_buffer.read())
    print("Test PDF generated: test_quote.pdf")
