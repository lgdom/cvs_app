import io
import os
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 1. REGISTRO DE FUENTES POPIINS
def register_poppins():
    fonts_dir = "assets/fonts"
    try:
        pdfmetrics.registerFont(TTFont('Poppins-Regular', os.path.join(fonts_dir, "Poppins-Regular.ttf")))
        pdfmetrics.registerFont(TTFont('Poppins-SemiBold', os.path.join(fonts_dir, "Poppins-SemiBold.ttf")))
        pdfmetrics.registerFont(TTFont('Poppins-Light', os.path.join(fonts_dir, "Poppins-Light.ttf")))
    except: pass

register_poppins()

meses_es = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", 
            "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

def generate_inventory_pdf(df, info_fecha, df_corta_cad=None, info_v_fechas=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, 
        leftMargin=0.5*inch, rightMargin=0.5*inch, 
        topMargin=0.3*inch, bottomMargin=0.3*inch,
        title="REPORTE DE EXISTENCIAS"
    )
    elements = []
    styles = getSampleStyleSheet()
    
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        img = Image(logo_path)
        aspect = img.imageHeight / float(img.imageWidth)
        img.drawWidth = 1.8 * inch
        img.drawHeight = 1.8 * inch * aspect
        img.hAlign = 'CENTER'
        elements.append(img)
        elements.append(Spacer(1, 0.1*inch))

    fn_sb = 'Poppins-SemiBold' if 'Poppins-SemiBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    fn_reg = 'Poppins-Regular' if 'Poppins-Regular' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    fn_light = 'Poppins-Light' if 'Poppins-Light' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    style_title = ParagraphStyle('MainTitle', fontName=fn_sb, fontSize=16, alignment=1, spaceAfter=14)
    style_subtitle = ParagraphStyle('SubTitle', fontName=fn_sb, fontSize=12, alignment=1, spaceAfter=8)
    style_date = ParagraphStyle('DateStyle', fontName=fn_light, fontSize=9, alignment=1, spaceAfter=2)
    style_cell = ParagraphStyle('CellText', fontName=fn_reg, fontSize=8, leading=9, alignment=0)
    style_code_link = ParagraphStyle('CodeLink', fontName=fn_reg, fontSize=8, leading=9, alignment=1)
    style_legend = ParagraphStyle('Legend', fontName=fn_light, fontSize=8, alignment=0)

    # -- PAG 1 --
    elements.append(Paragraph("REPORTE DE EXISTENCIAS", style_title))
    elements.append(Paragraph("ALMACÉN TIJUANA", style_subtitle))
    
    elements.append(Paragraph(f"ACTUALIZADO AL {info_fecha.upper()}", style_date))
    elements.append(Spacer(1, 0.1*inch))
    
    legend_data = [['', Paragraph("DISPONIBLE", style_legend), '', Paragraph("SOLO CORTA CADUCIDAD", style_legend), '', Paragraph("NO DISPONIBLE", style_legend)]]
    l_table = Table(legend_data, colWidths=[0.2*inch, 1.0*inch, 0.2*inch, 1.8*inch, 0.2*inch, 1.1*inch], rowHeights=[0.14*inch])
    l_table.hAlign = 'CENTER'
    l_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#c8e6c9")),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor("#fff9c4")),
        ('BACKGROUND', (4,0), (4,0), colors.HexColor("#ffcdd2")),
        ('GRID', (0,0), (0,0), 0.5, colors.grey),
        ('GRID', (2,0), (2,0), 0.5, colors.grey),
        ('GRID', (4,0), (4,0), 0.5, colors.grey)
    ]))
    elements.append(l_table)
    elements.append(Spacer(1, 0.1*inch))

    # TABLA 1 (ORIGINAL - PADDING 2)
    data = [['CÓDIGO', 'PRODUCTO', 'SUSTANCIA', 'EXISTENCIA', 'CORTA CAD']]
    cell_backgrounds = []
    for _, row in df.iterrows():
        codigo = str(row.get('CODIGO', '')).strip().upper()
        if codigo.startswith('S') or codigo == "F03025": continue
        ex, cc = int(row.get('EXISTENCIA', 0)), int(row.get('CORTA_CAD', 0))
        row_idx = len(data)
        bg = colors.HexColor("#c8e6c9") if ex > 0 else (colors.HexColor("#fff9c4") if cc > 0 else colors.HexColor("#ffcdd2"))
        cell_backgrounds.append(('BACKGROUND', (0, row_idx), (0, row_idx), bg))
        clean_id = "".join(filter(str.isalnum, codigo))
        codigo_display = f'<a name="HOME_{clean_id}"/><a href="#DETALLE_TECNICO">{codigo}</a>' if (cc > 0 and df_corta_cad is not None) else f'<a name="HOME_{clean_id}"/>{codigo}'
        data.append([Paragraph(codigo_display, style_code_link), Paragraph(str(row.get('PRODUCTO', '')), style_cell), Paragraph(str(row.get('SUSTANCIA', '')), style_cell), str(ex), str(cc)])

    table = Table(data, colWidths=[0.7*inch, 3.0*inch, 1.8*inch, 1.0*inch, 1.0*inch], repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), fn_sb), ('FONTSIZE', (0,0), (-1,0), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f4f4f4")),
        ('FONTNAME', (0,1), (-1,-1), fn_reg), ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (2,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ] + cell_backgrounds))
    elements.append(table)

    # -- PAG 2 --
    if df_corta_cad is not None and not df_corta_cad.empty:
        elements.append(PageBreak())
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph('<a name="DETALLE_TECNICO"/>DETALLE DE CORTA CADUCIDAD', style_title))
        
        info_v_fecha = "---"
        if info_v_fechas:
            try:
                dv = datetime.fromisoformat(info_v_fechas['interna']) if info_v_fechas.get('interna') else datetime.fromisoformat(info_v_fechas['creacion'].replace("Z", "+00:00"))
                info_v_fecha = f"ACTUALIZADO AL {dv.day} DE {meses_es[dv.month-1]} DE {dv.year}"
            except: info_v_fecha = "ACTUALIZACIÓN RECIENTE"
        
        elements.append(Paragraph(info_v_fecha, ParagraphStyle('DT2', fontName=fn_light, fontSize=10, alignment=1, spaceAfter=15)))
        l_tech_data = [['', Paragraph("CON EXISTENCIA GENERAL", style_legend), '', Paragraph("SOLO CORTA CADUCIDAD", style_legend)]]
        l_tech = Table(l_tech_data, colWidths=[0.2*inch, 1.8*inch, 0.2*inch, 1.8*inch], rowHeights=[0.14*inch])
        l_tech.hAlign = 'CENTER'
        l_tech.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
            ('BACKGROUND', (0,0), (0,0), colors.HexColor("#c8e6c9")),
            ('BACKGROUND', (2,0), (2,0), colors.HexColor("#fff9c4")), 
            ('GRID', (0,0), (0,0), 0.5, colors.grey),
            ('GRID', (2,0), (2,0), 0.5, colors.grey),
        ]))
        elements.append(l_tech)
        elements.append(Spacer(1, 0.2*inch))

        disc_table = Table([[Paragraph("ESTA TABLA SE ACTUALIZA UNA VEZ POR SEMANA<br/>LA DISPONIBILIDAD DE CIERTOS LOTES PUEDE VARIAR AL MOMENTO DE SU CONSULTA<br/>PARA INFORMACIÓN ACTUALIZADA, CONSULTE A SU AGENTE DE VENTAS", ParagraphStyle('DTX', fontName=fn_sb, fontSize=7, alignment=1, leading=10))]], colWidths=[6.0*inch])
        disc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fff1f2")), ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#ef4444")), 
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(disc_table)
        elements.append(Spacer(1, 0.2*inch))
        
        try:
            df_act_check = df[['CODIGO', 'PRODUCTO', 'EXISTENCIA', 'CORTA_CAD']].drop_duplicates('CODIGO')
            df_cad_merged = pd.merge(df_corta_cad, df_act_check, on='CODIGO', how='inner').query('EXISTENCIA > 0 or CORTA_CAD > 0')
        except: df_cad_merged = df_corta_cad
        
        data_cad = [['CÓDIGO', 'PRODUCTO', 'FECHAS DE CADUCIDAD (LOTES)']]
        cell_backgrounds_cad = []
        for _, row in df_cad_merged.iterrows():
            codigo = str(row['CODIGO']).strip().upper()
            if codigo.startswith('S') or codigo == "F03025": continue
            row_idx_cad = len(data_cad)
            ex = int(row.get('EXISTENCIA', 0))
            bg_cad = colors.HexColor("#c8e6c9") if ex > 0 else colors.HexColor("#fff9c4")
            cell_backgrounds_cad.append(('BACKGROUND', (0, row_idx_cad), (0, row_idx_cad), bg_cad))
            clean_id = "".join(filter(str.isalnum, codigo))
            data_cad.append([Paragraph(f'<a href="#HOME_{clean_id}">{codigo}</a>', style_code_link), Paragraph(str(row.get('PRODUCTO', '---')), style_cell), Paragraph(str(row.get('FECHAS_CAD', '---')), style_cell)])
            
        table_cad = Table(data_cad, colWidths=[1.0*inch, 3.5*inch, 3.0*inch], repeatRows=1)
        table_cad.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), fn_sb), ('FONTSIZE', (0,0), (-1,0), 9),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f4f4f4")),
            ('FONTNAME', (0,1), (-1,-1), fn_reg), ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('TOPPADDING', (0,0), (-1,-1), 3.6), ('BOTTOMPADDING', (0,0), (-1,-1), 3.6), # EL PUNTO DULCE: 3
        ] + cell_backgrounds_cad))
        elements.append(table_cad)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
