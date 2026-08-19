"""
PDF report generation using ReportLab.
Produces a clean single-page summary of a change analysis result.
"""
import logging
from pathlib import Path
from datetime import datetime
from io import BytesIO

logger = logging.getLogger(__name__)


def generate_pdf_report(result: dict, job_id: str, output_path: Path) -> Path:
    """
    Generate PDF report from analysis result dict.
    result keys: stats, interpretation, t1_date, t2_date, bbox, model_used, etc.
    Returns path to generated PDF.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a6e4a"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=4,
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#334155"),
        )
        small_style = ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
        )

        story = []

        # Header
        story.append(Paragraph("TerraDelta", title_style))
        story.append(Paragraph(
            "Automated Human Change Detection Report", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2,
                                color=colors.HexColor("#1a6e4a")))
        story.append(Spacer(1, 0.3*cm))

        # Job metadata
        bbox = result.get("bbox", [])
        bbox_str = (f"{bbox[0]:.4f}°E, {bbox[1]:.4f}°N to "
                    f"{bbox[2]:.4f}°E, {bbox[3]:.4f}°N") if len(bbox) == 4 else "N/A"
        
        timeline = result.get("timeline", [])
        actual_dates = result.get("actual_dates", [])
        cloud_covers = result.get("cloud_covers", [])
        
        dates_str = " → ".join(actual_dates) if actual_dates else "N/A"

        meta_data = [
            ["Job ID", job_id[:16] + "..."],
            ["Analysis Area (bbox)", bbox_str],
            ["Timeline Dates", dates_str],
            ["Model Used",      result.get("model_used", "Random Forest").upper()],
            ["Report Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
        ]
        meta_table = Table(meta_data, colWidths=[5*cm, 12*cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("FONTNAME",    (0,0), (0,-1), "Helvetica-Bold"),
            ("TEXTCOLOR",   (0,0), (0,-1), colors.HexColor("#1a6e4a")),
            ("TEXTCOLOR",   (1,0), (1,-1), colors.HexColor("#1e293b")),
            ("ROWBACKGROUNDS", (0,0), (-1,-1),
             [colors.HexColor("#f8fafc"), colors.white]),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.4*cm))

        from reportlab.platypus import PageBreak
        
        for i, step in enumerate(timeline):
            if i > 0:
                story.append(PageBreak())
                story.append(Paragraph(f"Change Statistics: Step {i+1}", section_style))
            else:
                story.append(Paragraph("Change Statistics", section_style))
                
            prev_date = actual_dates[i] if i < len(actual_dates) else "T1"
            curr_date = step.get("date", "T2")
            
            story.append(Paragraph(f"<b>Interval:</b> {prev_date} to {curr_date}", body_style))
            story.append(Spacer(1, 0.2*cm))
            
            stats = step.get("stats", {})

            stats_data = [
                ["Metric", "Value"],
                ["Changed Area", f"{stats.get('changed_area_ha', 0):.2f} ha "
                                 f"({stats.get('changed_area_m2', 0):,} m²)"],
                ["Change Percentage", f"{stats.get('change_percent', 0):.2f}% of AOI"],
                ["Number of Clusters", str(stats.get("num_clusters", 0))],
                ["Mean Confidence", f"{stats.get('mean_confidence', 0):.1%}"],
                ["High-Confidence Area",
                 f"{stats.get('high_confidence_area_ha', 0):.2f} ha"],
                ["Largest Cluster",
                 f"{stats.get('largest_cluster_ha', 0):.2f} ha"],
            ]
            stats_table = Table(stats_data, colWidths=[8*cm, 9*cm])
            stats_table.setStyle(TableStyle([
                ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",       (0,0), (-1,-1), 10),
                ("BACKGROUND",     (0,0), (-1,0), colors.HexColor("#1a6e4a")),
                ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
                ("ROWBACKGROUNDS", (0,1), (-1,-1),
                 [colors.white, colors.HexColor("#f0fdf4")]),
                ("TOPPADDING",     (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",  (0,0), (-1,-1), 6),
                ("LEFTPADDING",    (0,0), (-1,-1), 10),
                ("GRID",           (0,0), (-1,-1), 0.5,
                 colors.HexColor("#e2e8f0")),
            ]))
            story.append(stats_table)
            story.append(Spacer(1, 0.4*cm))

            # Interpretation
            story.append(Paragraph("AI Interpretation", section_style))
            interpretation = step.get("interpretation",
                                        "No interpretation available.")
            story.append(Paragraph(interpretation, body_style))
            story.append(Spacer(1, 0.4*cm))

        # Limitations disclaimer
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 0.2*cm))
        disclaimer = (
            "<b>Important Limitations:</b> This analysis uses Sentinel-2 imagery "
            "at 10 m spatial resolution. Objects smaller than ~30 m may not be "
            "reliably detected. The AI model uses spectral and texture features to "
            "distinguish human-caused changes from environmental variation; "
            "some false positives or missed changes are expected. "
            "Visual verification with high-resolution imagery is recommended "
            "before taking decisions based on this report."
        )
        story.append(Paragraph(disclaimer, small_style))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            "Generated by TerraDelta — ISRO Capstone Project | "
            "Data: ESA Copernicus Sentinel-2",
            small_style
        ))

        doc.build(story)
        buf.seek(0)

        with open(output_path, "wb") as f:
            f.write(buf.read())

        logger.info(f"PDF report saved: {output_path}")
        return output_path

    except ImportError:
        logger.error("ReportLab not installed. Cannot generate PDF.")
        raise
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise
