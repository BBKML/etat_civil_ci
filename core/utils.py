from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.core.files.base import ContentFile
from django.conf import settings
import hashlib
import datetime
import os
from io import BytesIO

def generer_pdf_naissance(demande, acte):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    logo_path = os.path.join(settings.BASE_DIR, "static/logo_ci.png")
    if os.path.exists(logo_path):
        c.drawImage(ImageReader(logo_path), 40, height - 80, width=60, preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 30, "RÉPUBLIQUE DE CÔTE D'IVOIRE")
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, height - 45, "Union - Discipline - Travail")

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y - 50, "🍼 ACTE DE NAISSANCE")
    c.setFont("Helvetica", 12)
    y -= 100

    lignes = [
        f"Numéro demande : {demande.numero_demande}",
        f"Date création   : {demande.date_creation.strftime('%d/%m/%Y')}",
        f"Nom enfant      : {acte.nom_enfant}",
        f"Prénom enfant   : {acte.prenom_enfant}",
        f"Sexe            : {acte.get_sexe_display()}",
        f"Né(e) le        : {acte.date_naissance}",
        f"Lieu naissance  : {acte.lieu_naissance}",
        f"Nom père        : {acte.nom_pere}",
        f"Nom mère        : {acte.nom_mere}",
        f"Structure       : {acte.agent.structure.nom if acte.agent else ''}",
    ]

    for ligne in lignes:
        c.drawString(50, y, ligne)
        y -= 20

    signature = hashlib.sha256(f"{demande.numero_demande}-{acte.pk}-{datetime.datetime.now()}".encode()).hexdigest()
    c.drawString(50, y - 20, "Signature numérique :")
    c.drawString(50, y - 40, signature[:64])
    if len(signature) > 64:
        c.drawString(50, y - 60, signature[64:])

    c.showPage()
    c.save()

    return ContentFile(buffer.getvalue()), signature


def generer_pdf_mariage(demande, acte):
    """Génère un PDF pour un acte de mariage"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "💍 ACTE DE MARIAGE")
    c.setFont("Helvetica", 12)
    y -= 50

    lignes = [
        f"Demande : {demande.numero_demande}",
        f"Date     : {demande.date_creation.strftime('%d/%m/%Y')}",
        f"Époux    : {acte.prenom_epoux} {acte.nom_epoux}",
        f"Épouse   : {acte.prenom_epouse} {acte.nom_epouse}",
        f"Date mariage  : {acte.date_mariage}",
        f"Heure mariage : {acte.heure_mariage or 'N/A'}",
        f"Lieu          : {acte.lieu_mariage}",
        f"Régime        : {acte.regime_matrimonial or 'Non précisé'}",
        f"Agent         : {acte.agent.get_full_name() if acte.agent else 'N/A'}",
        f"Structure     : {acte.agent.structure.nom if acte.agent and acte.agent.structure else 'N/A'}",
    ]

    for ligne in lignes:
        c.drawString(50, y, ligne)
        y -= 20

    raw = f"{demande.numero_demande}-{acte.pk}-{datetime.datetime.now().timestamp()}"
    signature = hashlib.sha256(raw.encode()).hexdigest()
    c.drawString(50, y - 20, "Signature numérique :")
    c.drawString(50, y - 40, signature[:64])
    if len(signature) > 64:
        c.drawString(50, y - 60, signature[64:])

    c.showPage()
    c.save()
    return ContentFile(buffer.getvalue()), signature
