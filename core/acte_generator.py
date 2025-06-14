import os
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, Polygon
from reportlab.graphics import renderPDF
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from PyPDF2 import PdfReader, PdfWriter
from hashlib import sha256
import rsa
import base64
from datetime import datetime
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

class ActeGenerator:
    # Couleurs du drapeau ivoirien
    ORANGE_CI = colors.HexColor('#FF8C00')  # Orange (Union)
    BLANC_CI = colors.HexColor('#FFFFFF')   # Blanc (Discipline)
    VERT_CI = colors.HexColor('#228B22')    # Vert (Travail)
    OR_CI = colors.HexColor('#FFD700')      # Or pour les accents
    ROUGE_BORDEAUX = colors.HexColor('#8B0000')  # Rouge officiel

    @staticmethod
    def _register_fonts():
        """Enregistre les polices personnalisées"""
        try:
            font_dir = os.path.join(settings.BASE_DIR, 'static/font')
            
            fonts = {
                'Arial': 'arial.ttf',
                'Arial-Bold': 'arialbd.ttf',
                'Arial-Italic': 'ariali.ttf',
                'Times-Roman': 'times.ttf',
                'Times-Bold': 'timesbd.ttf',
                'Garamond': 'garamond.ttf',
                'Garamond-Bold': 'garamondbd.ttf'
            }
            
            for font_name, font_file in fonts.items():
                font_path = os.path.join(font_dir, font_file)
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    
        except Exception as e:
            print(f"Erreur lors de l'enregistrement des polices : {e}")



    @staticmethod
    def _get_logo_image():
        """Récupère l'image du logo officiel"""
        try:
            # Chemin vers le logo (à adapter selon votre structure)
            logo_path = os.path.join(settings.BASE_DIR, 'static/images/armoiries.png')
            
            if os.path.exists(logo_path):
                # Créer l'image avec ReportLab
                logo = Image(logo_path, width=0.8*inch, height=0.8*inch)
                logo.hAlign = 'CENTER'
                return logo
            else:
                print(f"Logo non trouvé à : {logo_path}")
                return None
        except Exception as e:
            print(f"Erreur lors du chargement du logo : {e}")
            return None         

    @staticmethod
    def _create_watermark_armoiries():
        """Crée un filigrane avec les armoiries de Côte d'Ivoire en transparence"""
        drawing = Drawing(400, 500)
        
        # Éléphant stylisé (symbole de la Côte d'Ivoire)
        # Corps de l'éléphant
        elephant = Polygon([
            200, 250,  # Tête
            180, 240, 170, 220, 160, 200,  # Trompe
            150, 180, 140, 160, 130, 140,
            140, 120, 160, 110, 180, 100,  # Ventre
            220, 100, 240, 110, 250, 120,  # Pattes arrière
            260, 140, 270, 160, 280, 180,  # Dos
            290, 200, 280, 220, 270, 240,  # Arrière-train
            250, 250, 230, 260, 210, 255   # Retour à la tête
        ])
        elephant.fillColor = colors.Color(0.5, 0.5, 0.5, alpha=0.1)  # Gris très transparent
        elephant.strokeColor = colors.Color(0.3, 0.3, 0.3, alpha=0.15)
        elephant.strokeWidth = 1
        drawing.add(elephant)
        
        # Couronne ou ornements
        couronne = Circle(200, 280, 15)
        couronne.fillColor = colors.Color(1, 0.84, 0, alpha=0.1)  # Or transparent
        couronne.strokeColor = colors.Color(0.8, 0.6, 0, alpha=0.15)
        drawing.add(couronne)
        
        return drawing

    @staticmethod
    def _create_decorative_border():
        """Crée une bordure décorative avec les couleurs ivoiriennes"""
        drawing = Drawing(500, 650)
        
        # Bordure externe orange
        border_orange = Rect(10, 10, 480, 630)
        border_orange.fillColor = None
        border_orange.strokeColor = ActeGenerator.ORANGE_CI
        border_orange.strokeWidth = 3
        drawing.add(border_orange)
        
        # Bordure interne verte
        border_vert = Rect(15, 15, 470, 620)
        border_vert.fillColor = None
        border_vert.strokeColor = ActeGenerator.VERT_CI
        border_vert.strokeWidth = 2
        drawing.add(border_vert)
        
        # Coins décoratifs
        for x, y in [(20, 620), (470, 620), (20, 20), (470, 20)]:
            coin = Circle(x, y, 8)
            coin.fillColor = ActeGenerator.OR_CI
            coin.strokeColor = ActeGenerator.ROUGE_BORDEAUX
            coin.strokeWidth = 1
            drawing.add(coin)
        
        return drawing

    @staticmethod
    def _get_enhanced_styles():
        """Retourne les styles améliorés avec les couleurs ivoiriennes"""
        styles = getSampleStyleSheet()

        # Style République avec gradient orange-vert
        styles.add(ParagraphStyle(
            name='Republique',
            fontName='Times-Bold',
            fontSize=14,
            textColor=ActeGenerator.ROUGE_BORDEAUX,
            alignment=TA_CENTER,
            spaceAfter=6,
            spaceBefore=4,
            leading=16,
            backColor=colors.Color(1, 0.9, 0.7, alpha=0.3),  # Fond orange clair
            borderWidth=2,
            borderColor=ActeGenerator.ORANGE_CI,
            borderPadding=6
        ))

        # Style Ministère
        styles.add(ParagraphStyle(
            name='Ministere',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=ActeGenerator.VERT_CI,
            alignment=TA_CENTER,
            spaceAfter=4,
            leading=12,
            backColor=colors.Color(0.9, 1, 0.9, alpha=0.5)  # Fond vert clair
        ))

        # Style Titre Acte compact
        styles.add(ParagraphStyle(
            name='TitreActe',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=ActeGenerator.ROUGE_BORDEAUX,
            alignment=TA_CENTER,
            spaceAfter=6,
            spaceBefore=4,
            leading=14,
            borderWidth=2,
            borderColor=ActeGenerator.OR_CI,
            borderPadding=4,
            backColor=colors.Color(1, 1, 0.9, alpha=0.8)  # Fond crème
        ))

        # Style Section compact (remplace Arial-Bold par Helvetica-Bold)
        styles.add(ParagraphStyle(
            name='Section',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=ActeGenerator.VERT_CI,
            alignment=TA_CENTER,
            spaceAfter=2,
            spaceBefore=3,
            backColor=colors.Color(0.9, 0.95, 0.9, alpha=0.6),
            borderWidth=1,
            borderColor=ActeGenerator.ORANGE_CI,
            borderPadding=2
        ))

        # Style Corps de texte compact (remplace Arial par Helvetica)
        styles.add(ParagraphStyle(
            name='CorpsTexte',
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=2,
            leading=10
        ))

        # Style Signature avec fond décoratif
        styles.add(ParagraphStyle(
            name='Signature',
            fontName='Times-Italic',
            fontSize=9,
            textColor=ActeGenerator.ROUGE_BORDEAUX,
            alignment=TA_RIGHT,
            spaceAfter=4,
            leading=12,
            backColor=colors.Color(1, 0.95, 0.8, alpha=0.5)
        ))

        # Style Date (remplace Arial-Italic par Helvetica-Oblique)
        styles.add(ParagraphStyle(
            name='DateAuto',
            fontName='Helvetica-Oblique',
            fontSize=7,
            textColor=ActeGenerator.VERT_CI,
            alignment=TA_RIGHT,
            spaceAfter=2
        ))

        return styles

    @staticmethod
    def create_qr_code(data, size=40):
        """Crée un QR code compact"""
        qr_code = QrCodeWidget(data)
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        drawing = Drawing(size, size, transform=[size/width, 0, 0, size/height, 0, 0])
        drawing.add(qr_code)
        
        return drawing

    @staticmethod
    def _create_signature_image():
        """Crée une signature stylisée"""
        drawing = Drawing(120, 40)
        
        # Signature cursive stylisée
        signature_path = [
            (10, 20), (20, 25), (30, 22), (40, 28),
            (50, 15), (65, 30), (80, 18), (95, 25),
            (110, 20)
        ]
        
        # Tracer la signature
        for i in range(len(signature_path) - 1):
            x1, y1 = signature_path[i]
            x2, y2 = signature_path[i + 1]
            line = Line(x1, y1, x2, y2)
            line.strokeColor = ActeGenerator.ROUGE_BORDEAUX
            line.strokeWidth = 2
            drawing.add(line)
        
        # Paraphe décoratif
        paraphe = Circle(60, 25, 15)
        paraphe.fillColor = None
        paraphe.strokeColor = ActeGenerator.ORANGE_CI
        paraphe.strokeWidth = 1
        drawing.add(paraphe)
        
        return drawing

    @staticmethod
    def _add_header_with_logo(elements, styles, acte_type="NAISSANCE"):
        """Ajoute l'en-tête compact avec vrai logo"""
        
        # Bordure décorative en en-tête
        border_drawing = Drawing(500, 30)
        # Ligne orange
        line1 = Line(0, 25, 500, 25)
        line1.strokeColor = ActeGenerator.ORANGE_CI
        line1.strokeWidth = 3
        border_drawing.add(line1)
        # Ligne verte
        line2 = Line(0, 20, 500, 20)
        line2.strokeColor = ActeGenerator.VERT_CI
        line2.strokeWidth = 2
        border_drawing.add(line2)
        # Ligne blanche
        line3 = Line(0, 22, 500, 22)
        line3.strokeColor = ActeGenerator.BLANC_CI
        line3.strokeWidth = 1
        border_drawing.add(line3)
        
        elements.append(border_drawing)
        elements.append(Spacer(1, 0.1*inch))
        
        # Récupérer le logo
        logo = ActeGenerator._get_logo_image()
        
        # Si pas de logo, utiliser l'emoji comme fallback
        if logo is None:
            logo_left = "🇨🇮"
            logo_right = "🇨🇮"
            logo_font_size = 24
        else:
            logo_left = logo
            logo_right = logo  # Même logo des deux côtés
            logo_font_size = 8  # Pas utilisé pour les images
        
        # Table pour l'en-tête avec logos
        header_data = [
            [logo_left, 
            Paragraph("RÉPUBLIQUE DE CÔTE D'IVOIRE<br/>Union - Discipline - Travail", styles['Republique']),
            logo_right]
        ]
        
        header_table = Table(header_data, colWidths=[0.8*inch, 4.4*inch, 0.8*inch])
        
        if logo is None:
            # Style pour émojis
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (0, 0), logo_font_size),
                ('FONTSIZE', (2, 0), (2, 0), logo_font_size),
            ]))
        else:
            # Style pour images
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # Ministère
        elements.append(Paragraph("MINISTÈRE DE L'INTÉRIEUR ET DE LA SÉCURITÉ", styles['Ministere']))
        elements.append(Paragraph("DIRECTION DE L'ÉTAT CIVIL", styles['Ministere']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Titre de l'acte
        titre_map = {
            "NAISSANCE": "📋 EXTRAIT DE NAISSANCE 📋",
            "MARIAGE": "💒 ACTE DE MARIAGE 💒", 
            "DECES": "🕊️ ACTE DE DÉCÈS 🕊️"
        }
        elements.append(Paragraph(titre_map.get(acte_type, "ACTE OFFICIEL"), styles['TitreActe']))
        elements.append(Spacer(1, 0.1*inch))
        
        return elements

    @staticmethod
    def _create_info_table_compact(data, styles, title=None):
        """Crée une table d'informations compacte"""
        elements = []
        
        if title:
            elements.append(Paragraph(title, styles['Section']))
            elements.append(Spacer(1, 0.05*inch))
            
        table = Table(data, colWidths=[1.8*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Arial', 8),
            ('FONTNAME', (0, 0), (0, -1), 'Arial-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, ActeGenerator.VERT_CI),
            ('BACKGROUND', (0, 0), (0, -1), colors.Color(1, 0.9, 0.7, alpha=0.3)),  # Orange clair
            ('BACKGROUND', (1, 0), (1, -1), colors.Color(0.95, 1, 0.95, alpha=0.3)),  # Vert très clair
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.1*inch))
        
        return elements

    @staticmethod
    def _add_footer_with_signature(elements, styles, agent_nom="", poste="Agent d'État Civil"):
        """Ajoute le pied de page avec signature visible"""
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Date et lieu
        date_actuelle = datetime.now().strftime("%d/%m/%Y")
        heure_actuelle = datetime.now().strftime("%H:%M")
        
        elements.append(Paragraph(
            f"📍 Fait et dressé à Abidjan, le {date_actuelle} à {heure_actuelle}",
            styles['DateAuto']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        
        # Table pour QR code et signature
        qr_data = f"Acte officiel - {date_actuelle} - {agent_nom}"
        qr_code = ActeGenerator.create_qr_code(qr_data, 35)
        signature_drawing = ActeGenerator._create_signature_image()
        
        footer_data = [
            [qr_code, 
             Paragraph(f"<b>{poste}</b><br/><br/>{agent_nom}", styles['Signature']),
             signature_drawing]
        ]
        
        footer_table = Table(footer_data, colWidths=[0.8*inch, 2.5*inch, 1.7*inch])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.Color(1, 1, 0.9, alpha=0.5)),
            ('BOX', (0, 0), (-1, -1), 1, ActeGenerator.ORANGE_CI),
        ]))
        
        elements.append(footer_table)
        
        # Cachet officiel
        cachet_data = [
            ["🏛️ CACHET OFFICIEL", "⚖️ RÉPUBLIQUE DE CÔTE D'IVOIRE"]
        ]
        
        cachet_table = Table(cachet_data, colWidths=[2.5*inch, 2.5*inch])
        cachet_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Arial-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.Color(1, 0.84, 0, alpha=0.3)),  # Or transparent
            ('BOX', (0, 0), (-1, -1), 1, ActeGenerator.ROUGE_BORDEAUX),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        
        elements.append(Spacer(1, 0.1*inch))
        elements.append(cachet_table)
        
        return elements

    @staticmethod
    def generate_acte_naissance(acte_naissance):
        """Génère un PDF embelli pour un acte de naissance - UNE SEULE PAGE"""
        ActeGenerator._register_fonts()
        styles = ActeGenerator._get_enhanced_styles()
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.4*inch,
            bottomMargin=0.4*inch
        )
        elements = []
        
        # Filigrane armoiries (sera en arrière-plan)
        # watermark = ActeGenerator._create_watermark_armoiries()
        # elements.append(watermark)
        
        # En-tête
        ActeGenerator._add_header_with_logo(elements, styles, "NAISSANCE")
        
        # Informations compactes en 2 colonnes
        personne = acte_naissance.personne
        
        # Colonne 1: Infos acte + enfant
        col1_data = [
            ["N° Acte:", acte_naissance.numero_acte],
            ["Date enreg.:", acte_naissance.date_enregistrement.strftime("%d/%m/%Y")],
            ["Commune:", acte_naissance.commune_enregistrement.nom],
            ["📋 ENFANT", ""],
            ["Nom:", personne.nom.upper()],
            ["Prénoms:", personne.prenoms],
            ["Né(e) le:", personne.date_naissance.strftime("%d/%m/%Y")],
            ["À:", f"{personne.commune_naissance.nom}"],
            ["Sexe:", "♂ Masculin" if personne.sexe == 'M' else "♀ Féminin"],
        ]
        
        # Colonne 2: Parents + déclaration
        col2_data = [
            ["👨 PÈRE", ""],
            ["Nom:", (personne.nom_pere or "Non déclaré").upper()],
            ["Prénoms:", personne.prenoms_pere or "Non déclaré"],
            ["Profession:", personne.profession_pere or "Non déclarée"],
            ["👩 MÈRE", ""],
            ["Nom:", (personne.nom_mere or "Non déclaré").upper()],
            ["Prénoms:", personne.prenoms_mere or "Non déclaré"],
            ["Profession:", personne.profession_mere or "Non déclarée"],
            ["📝 Déclarant:", acte_naissance.declarant_nom],
        ]
        
        # Table principale en 2 colonnes
        main_table_data = []
        max_rows = max(len(col1_data), len(col2_data))
        
        for i in range(max_rows):
            row = []
            if i < len(col1_data):
                row.extend(col1_data[i])
            else:
                row.extend(["", ""])
            if i < len(col2_data):
                row.extend(col2_data[i])
            else:
                row.extend(["", ""])
            main_table_data.append(row)
        
        main_table = Table(main_table_data, colWidths=[0.8*inch, 1.7*inch, 0.8*inch, 1.7*inch])
        main_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Arial', 7),
            ('FONTNAME', (0, 0), (0, -1), 'Arial-Bold'),  # Col 1 labels
            ('FONTNAME', (2, 0), (2, -1), 'Arial-Bold'),  # Col 3 labels
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, ActeGenerator.VERT_CI),
            ('BACKGROUND', (0, 0), (0, -1), colors.Color(1, 0.9, 0.7, alpha=0.3)),
            ('BACKGROUND', (2, 0), (2, -1), colors.Color(1, 0.9, 0.7, alpha=0.3)),
            ('PADDING', (0, 0), (-1, -1), 3),
            # Highlight section headers
            ('BACKGROUND', (0, 3), (1, 3), ActeGenerator.ORANGE_CI),  # ENFANT
            ('BACKGROUND', (2, 0), (3, 0), ActeGenerator.ORANGE_CI),  # PÈRE
            ('BACKGROUND', (2, 4), (3, 4), ActeGenerator.VERT_CI),    # MÈRE
            ('TEXTCOLOR', (0, 3), (1, 3), colors.white),
            ('TEXTCOLOR', (2, 0), (3, 0), colors.white),
            ('TEXTCOLOR', (2, 4), (3, 4), colors.white),
        ]))
        
        elements.append(main_table)
        
        # Observations si présentes
        if acte_naissance.observations:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("💬 OBSERVATIONS", styles['Section']))
            elements.append(Paragraph(acte_naissance.observations, styles['CorpsTexte']))
        
        # Footer avec signature
        agent_nom = acte_naissance.agent_enregistreur.get_full_name() if acte_naissance.agent_enregistreur else "Agent d'État Civil"
        ActeGenerator._add_footer_with_signature(elements, styles, agent_nom)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_acte_mariage(acte_mariage):
        """Génère un PDF embelli pour un acte de mariage - UNE SEULE PAGE"""
        ActeGenerator._register_fonts()
        styles = ActeGenerator._get_enhanced_styles()
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.4*inch,
            bottomMargin=0.4*inch
        )
        elements = []
        
        # En-tête
        ActeGenerator._add_header_with_logo(elements, styles, "MARIAGE")
        
        # Informations compactes
        # Info acte
        info_acte = [
            ["N° Acte:", acte_mariage.numero_acte],
            ["Date mariage:", acte_mariage.date_mariage.strftime("%d/%m/%Y")],
            ["Commune:", acte_mariage.commune_mariage.nom],
            ["Régime:", acte_mariage.get_regime_matrimonial_display()],
            ["Registre:", f"Vol. {acte_mariage.numero_registre}, Page {acte_mariage.page_registre}"],
        ]
        
        elements.extend(ActeGenerator._create_info_table_compact(
            info_acte, styles, "📋 INFORMATIONS DE L'ACTE"
        ))
        
        # Époux et Épouse en 2 colonnes
        epoux_data = [
            ["👨 ÉPOUX", ""],
            ["Nom:", acte_mariage.epoux.nom.upper()],
            ["Prénoms:", acte_mariage.epoux.prenoms],
            ["Né le:", acte_mariage.epoux.date_naissance.strftime("%d/%m/%Y")],
            ["À:", acte_mariage.epoux.commune_naissance.nom],
            ["Profession:", acte_mariage.epoux.profession or "Non précisée"],
            ["Domicile:", acte_mariage.epoux.adresse or "Non précisé"],
        ]
        
        epouse_data = [
            ["👩 ÉPOUSE", ""],
            ["Nom:", acte_mariage.epouse.nom.upper()],
            ["Prénoms:", acte_mariage.epouse.prenoms],
            ["Née le:", acte_mariage.epouse.date_naissance.strftime("%d/%m/%Y")],
            ["À:", acte_mariage.epouse.commune_naissance.nom],
            ["Profession:", acte_mariage.epouse.profession or "Non précisée"],
            ["Domicile:", acte_mariage.epouse.adresse or "Non précisé"],
        ]
        
        # Table époux/épouse
        couple_table_data = []
        max_rows = max(len(epoux_data), len(epouse_data))
        
        for i in range(max_rows):
            row = []
            if i < len(epoux_data):
                row.extend(epoux_data[i])
            else:
                row.extend(["", ""])
            if i < len(epouse_data):
                row.extend(epouse_data[i])
            else:
                row.extend(["", ""])
            couple_table_data.append(row)
        
        couple_table = Table(couple_table_data, colWidths=[0.8*inch, 1.7*inch, 0.8*inch, 1.7*inch])
        couple_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Arial', 7),
            ('FONTNAME', (0, 0), (0, -1), 'Arial-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Arial-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, ActeGenerator.VERT_CI),
            ('BACKGROUND', (0, 0), (1, 0), ActeGenerator.ORANGE_CI),  # ÉPOUX
            ('BACKGROUND', (2, 0), (3, 0), ActeGenerator.VERT_CI),    # ÉPOUSE
            ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
            ('TEXTCOLOR', (2, 0), (3, 0), colors.white),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(couple_table)
        
        # Témoins
        elements.append(Spacer(1, 0.1*inch))
        temoins_data = [
            ["👥 Témoin époux 1:", acte_mariage.temoin_epoux_1],
            ["👥 Témoin époux 2:", acte_mariage.temoin_epoux_2],
            ["👥 Témoin épouse 1:", acte_mariage.temoin_epouse_1],
            ["👥 Témoin épouse 2:", acte_mariage.temoin_epouse_2],
        ]
        
        elements.extend(ActeGenerator._create_info_table_compact(
            temoins_data, styles, "👥 TÉMOINS"
        ))
        
        # Observations
        if acte_mariage.observations:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("💬 OBSERVATIONS", styles['Section']))
            elements.append(Paragraph(acte_mariage.observations, styles['CorpsTexte']))
        
        # Footer avec signature
        agent_nom = acte_mariage.officier_etat_civil.get_full_name() if acte_mariage.officier_etat_civil else "Officier d'État Civil"
        ActeGenerator._add_footer_with_signature(elements, styles, agent_nom, "Officier d'État Civil")
        
        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_acte_deces(acte_deces):
        """Génère un PDF embelli pour un acte de décès - UNE SEULE PAGE"""
        ActeGenerator._register_fonts()
        styles = ActeGenerator._get_enhanced_styles()
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.4*inch,
            bottomMargin=0.4*inch
        )
        elements = []
        
        # En-tête
        ActeGenerator._add_header_with_logo(elements, styles, "DECES")
        
        # Informations compactes
        personne = acte_deces.personne
        
        # Info acte
        info_acte = [
            ["N° Acte:", acte_deces.numero_acte],
            ["Date décès:", acte_deces.date_deces.strftime("%d/%m/%Y")],
            ["Heure décès:", acte_deces.heure_deces.strftime("%H:%M") if acte_deces.heure_deces else "Non précisée"],
            ["Lieu décès:", acte_deces.lieu_deces],
            ["Commune:", acte_deces.commune_deces.nom],
        ]
        
        elements.extend(ActeGenerator._create_info_table_compact(
            info_acte, styles, "📋 INFORMATIONS DE L'ACTE"
        ))
        
        # Défunt
        defunt_data = [
            ["🕊️ DÉFUNT", ""],
            ["Nom:", personne.nom.upper()],
            ["Prénoms:", personne.prenoms],
            ["Né(e) le:", personne.date_naissance.strftime("%d/%m/%Y")],
            ["À:", personne.commune_naissance.nom],
            ["Sexe:", "♂ Masculin" if personne.sexe == 'M' else "♀ Féminin"],
            ["Domicile:", personne.adresse or "Non précisé"],
            ["Profession:", personne.profession or "Non précisée"],
        ]
        
        elements.extend(ActeGenerator._create_info_table_compact(
            defunt_data, styles
        ))
        
        # Informations médicales
        if acte_deces.medecin_nom or acte_deces.numero_certificat_medical:
            medical_data = []
            if acte_deces.medecin_nom:
                medical_data.append(["👨⚕️ Médecin:", acte_deces.medecin_nom])
            if acte_deces.numero_certificat_medical:
                medical_data.append(["📄 N° certificat:", acte_deces.numero_certificat_medical])
            
            elements.extend(ActeGenerator._create_info_table_compact(
                medical_data, styles, "🏥 INFORMATIONS MÉDICALES"
            ))
        
        # Cause du décès
        if acte_deces.cause_deces:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("💀 CAUSE DU DÉCÈS", styles['Section']))
            elements.append(Paragraph(acte_deces.cause_deces, styles['CorpsTexte']))
        
        # Déclarant
        declarant_data = [
            ["📝 Déclarant:", acte_deces.declarant_nom],
            ["Qualité:", acte_deces.declarant_qualite],
        ]
        
        elements.extend(ActeGenerator._create_info_table_compact(
            declarant_data, styles, "📝 DÉCLARATION"
        ))
        
        # Observations
        if acte_deces.observations:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("💬 OBSERVATIONS", styles['Section']))
            elements.append(Paragraph(acte_deces.observations, styles['CorpsTexte']))
        
        # Footer avec signature
        agent_nom = acte_deces.agent_enregistreur.get_full_name() if acte_deces.agent_enregistreur else "Agent d'État Civil"
        ActeGenerator._add_footer_with_signature(elements, styles, agent_nom)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer