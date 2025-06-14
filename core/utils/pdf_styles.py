from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

def get_acte_styles():
    """Retourne les styles améliorés pour les actes d'état civil"""
    styles = getSampleStyleSheet()
    
    # Style République (en-tête principal avec couleur officielle)
    styles.add(ParagraphStyle(
        name='Republique',
        fontName='Times-Bold',
        fontSize=16,
        textColor=colors.HexColor('#8B0000'),  # Rouge bordeaux officiel
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=10,
        leading=20,
        borderWidth=1,
        borderColor=colors.HexColor('#8B0000'),
        borderPadding=8
    ))
    
    # Style Ministère avec couleur bleue
    styles.add(ParagraphStyle(
        name='Ministere',
        fontName='Times-Bold',
        fontSize=12,
        textColor=colors.HexColor('#000080'),  # Bleu marine
        alignment=TA_CENTER,
        spaceAfter=6,
        leading=16,
        backColor=colors.HexColor('#F0F8FF')  # Bleu très clair en arrière-plan
    ))
    
    # Style Titre Acte avec bordure élégante
    styles.add(ParagraphStyle(
        name='TitreActe',
        fontName='Times-Bold',
        fontSize=18,
        textColor=colors.HexColor('#8B0000'),
        alignment=TA_CENTER,
        spaceAfter=20,
        spaceBefore=15,
        leading=22,
        borderWidth=2,
        borderColor=colors.HexColor('#DAA520'),  # Bordure dorée
        borderPadding=12,
        backColor=colors.HexColor('#FFFAF0')  # Fond crème
    ))
    
    # Style Section avec fond coloré
    styles.add(ParagraphStyle(
        name='Section',
        fontName='Arial-Bold',
        fontSize=11,
        textColor=colors.HexColor('#2F4F4F'),  # Gris ardoise foncé
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=12,
        backColor=colors.HexColor('#E6E6FA'),  # Lavande clair
        borderWidth=1,
        borderColor=colors.HexColor('#9370DB'),  # Violet moyen
        borderPadding=6
    ))
    
    # Style Corps de texte professionnel
    styles.add(ParagraphStyle(
        name='CorpsTexte',
        fontName='Arial',
        fontSize=10,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=4,
        leading=14,
        firstLineIndent=0
    ))
    
    # Style Signature élégant
    styles.add(ParagraphStyle(
        name='Signature',
        fontName='Times-Italic',
        fontSize=11,
        textColor=colors.HexColor('#2F4F4F'),
        alignment=TA_RIGHT,
        spaceAfter=6,
        leading=16,
        backColor=colors.HexColor('#F5F5DC')  # Fond beige clair
    ))
    
    # Style Date automatique
    styles.add(ParagraphStyle(
        name='DateAuto',
        fontName='Arial-Italic',
        fontSize=9,
        textColor=colors.HexColor('#696969'),  # Gris foncé
        alignment=TA_RIGHT,
        spaceAfter=4,
        leading=12
    ))
    
    # Style pour les tableaux de données
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Arial-Bold',
        fontSize=10,
        textColor=colors.white,
        alignment=TA_CENTER,
        backColor=colors.HexColor('#4682B4')  # Bleu acier
    ))
    
    # Style pour les valeurs importantes
    styles.add(ParagraphStyle(
        name='Valeur',
        fontName='Arial-Bold',
        fontSize=10,
        textColor=colors.HexColor('#8B0000'),
        alignment=TA_LEFT
    ))
    
    # Style Centré normal
    styles.add(ParagraphStyle(
        name='NormalCenter',
        fontName='Arial',
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=6
    ))
    
    # Style Aligné à droite
    styles.add(ParagraphStyle(
        name='NormalRight',
        fontName='Arial',
        fontSize=10,
        alignment=TA_RIGHT,
        spaceAfter=6
    ))
    
    # Style Aligné à gauche
    styles.add(ParagraphStyle(
        name='NormalLeft',
        fontName='Arial',
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=6
    ))
    
    # Style pour les notes en bas de page
    styles.add(ParagraphStyle(
        name='NoteBas',
        fontName='Arial-Italic',
        fontSize=8,
        textColor=colors.HexColor('#808080'),
        alignment=TA_CENTER,
        spaceAfter=4
    ))
    
    # Style pour les mentions légales
    styles.add(ParagraphStyle(
        name='MentionLegale',
        fontName='Arial',
        fontSize=8,
        textColor=colors.HexColor('#2F4F4F'),
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=10,
        backColor=colors.HexColor('#F8F8FF'),
        borderWidth=0.5,
        borderColor=colors.HexColor('#B0C4DE'),
        borderPadding=4
    ))
    
    return styles

def get_table_styles():
    """Retourne les styles pour les tableaux"""
    return {
        'default': [
            ('FONT', (0, 0), (-1, -1), 'Arial', 10),
            ('FONTNAME', (0, 0), (0, -1), 'Arial-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')])
        ],
        'header': [
            ('FONT', (0, 0), (-1, 0), 'Arial-Bold', 11),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4682B4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, 0), 10)
        ],
        'signature': [
            ('FONT', (0, 0), (-1, -1), 'Times-Italic', 11),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5DC'))
        ]
    }

def get_colors():
    """Retourne la palette de couleurs officielles"""
    return {
        'rouge_officiel': colors.HexColor('#8B0000'),
        'bleu_marine': colors.HexColor('#000080'),
        'or': colors.HexColor('#DAA520'),
        'gris_ardoise': colors.HexColor('#2F4F4F'),
        'lavande': colors.HexColor('#E6E6FA'),
        'beige': colors.HexColor('#F5F5DC'),
        'blanc_casse': colors.HexColor('#FFFAF0'),
        'gris_clair': colors.HexColor('#F5F5F5')
    }