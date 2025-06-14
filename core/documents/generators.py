from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from django.conf import settings
import os
import hashlib
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont



# Enregistrement des polices
arial_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'arial.ttf')
arial_bold_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'arialbd.ttf')

class ActeGenerator:
    @staticmethod
    def generate_acte_naissance(acte):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Styles personnalisés
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontName='Arial-Bold',
            fontSize=14,
            alignment=1,
            spaceAfter=20
        )
        
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading2'],
            fontName='Arial-Bold',
            fontSize=12,
            spaceAfter=10
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontName='Arial',
            fontSize=10,
            leading=12
        )
        
        # Contenu du document
        story = []
        
        # En-tête
        story.append(Paragraph("REPUBLIQUE DE COTE D'IVOIRE", title_style))
        story.append(Paragraph("Union - Discipline - Travail", title_style))
        story.append(Paragraph(f"COMMUNE DE {acte.commune_enregistrement.nom.upper()}", title_style))
        story.append(Spacer(1, 20))
        
        # Titre de l'acte
        story.append(Paragraph("ACTE DE NAISSANCE", title_style))
        story.append(Spacer(1, 20))
        
        # Informations de l'acte
        info_data = [
            ["Numéro d'acte:", acte.numero_acte],
            ["Numéro de registre:", acte.numero_registre],
            ["Page:", acte.page_registre],
            ["Date d'enregistrement:", acte.date_enregistrement.strftime('%d/%m/%Y')],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
            ('FONTSIZE', (0, 0), (-1, -1), 10,)
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Informations de la personne
        story.append(Paragraph("INFORMATIONS DE L'ENFANT", header_style))
        
        personne = acte.personne
        personne_data = [
            ["Nom:", personne.nom],
            ["Prénoms:", personne.prenoms],
            ["Date de naissance:", personne.date_naissance.strftime('%d/%m/%Y')],
            ["Lieu de naissance:", personne.lieu_naissance],
            ["Sexe:", personne.get_sexe_display()],
        ]
        
        personne_table = Table(personne_data, colWidths=[2*inch, 3*inch])
        story.append(personne_table)
        story.append(Spacer(1, 20))
        
        # Informations des parents
        story.append(Paragraph("INFORMATIONS DES PARENTS", header_style))
        
        parents_data = [
            ["Nom du père:", personne.nom_pere],
            ["Prénoms du père:", personne.prenoms_pere],
            ["Nom de la mère:", personne.nom_mere],
            ["Prénoms de la mère:", personne.prenoms_mere],
        ]
        
        parents_table = Table(parents_data, colWidths=[2*inch, 3*inch])
        story.append(parents_table)
        story.append(Spacer(1, 20))
        
        # Déclarant et témoins
        story.append(Paragraph("DECLARATION", header_style))
        
        declaration_data = [
            ["Déclarant:", acte.declarant_nom],
            ["Qualité:", acte.declarant_qualite],
            ["Témoin 1:", acte.temoin1_nom],
            ["Témoin 2:", acte.temoin2_nom],
        ]
        
        declaration_table = Table(declaration_data, colWidths=[2*inch, 3*inch])
        story.append(declaration_table)
        story.append(Spacer(1, 20))
        
        # Observations
        if acte.observations:
            story.append(Paragraph("OBSERVATIONS", header_style))
            story.append(Paragraph(acte.observations, normal_style))
            story.append(Spacer(1, 20))
        
        # Signature
        story.append(Paragraph(f"Fait à {acte.commune_enregistrement.nom}, le {datetime.now().strftime('%d/%m/%Y')}", normal_style))
        story.append(Spacer(1, 40))
        story.append(Paragraph("L'Officier d'État Civil", normal_style))
        
        # Générer le PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_acte_mariage(acte):
        # Implémentation similaire pour l'acte de mariage
        pass

    @staticmethod
    def generate_acte_deces(acte):
        # Implémentation similaire pour l'acte de décès
        pass