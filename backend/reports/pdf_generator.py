"""
PDF report generation using ReportLab.
Produces a clean single-page summary of a change analysis result.
"""
import logging
from pathlib import Path
from datetime import datetime
from io import BytesIO

logger = logging.getLogger(__name__)


def generate_pdf_report(result: dict, job_id: str, output_path: Path,
                        images_dir: Path = None) -> Path:
    """
    Generate PDF report from analysis result dict.
    result keys: stats, interpretation, t1_date, t2_date, bbox, model_used, etc.
    images_dir: directory containing date_0.png, date_i.png, change_i.png
                (defaults to output_path's parent directory).
    Returns path to generated PDF.
    """
    if images_dir is None:
        images_dir = output_path.parent

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable, Image as RLImage
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from PIL import Image as PILImage

        def _fit_image(path: Path, max_w_cm: float, max_h_cm: float):
            """Load a PNG and return a RLImage flowable scaled to fit within bounds."""
            if not path.exists():
                return None
            try:
                with PILImage.open(path) as im:
                    w_px, h_px = im.size
                aspect = h_px / w_px if w_px else 1
                w = max_w_cm
                h = w * aspect
                if h > max_h_cm:
                    h = max_h_cm
                    w = h / aspect
                return RLImage(str(path), width=w * cm, height=h * cm)
            except Exception as e:
                logger.warning(f"Could not embed image {path}: {e}")
                return None

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
        data_sources = result.get("data_sources", [])
        any_synthetic = any(s == "synthetic_fallback" for s in data_sources)
        
        dates_str = " → ".join(actual_dates) if actual_dates else "N/A"

        source_label = "Mixed / Unknown"
        if data_sources:
            if all(s == "real_sentinel2" for s in data_sources):
                source_label = "Real Sentinel-2 (Copernicus Data Space Ecosystem)"
            elif all(s == "synthetic_fallback" for s in data_sources):
                source_label = "SYNTHETIC DEMO DATA (no real satellite imagery)"
            else:
                source_label = "MIXED — some dates real, some synthetic demo data"

        meta_data = [
            ["Job ID", job_id[:16] + "..."],
            ["Analysis Area (bbox)", bbox_str],
            ["Timeline Dates", dates_str],
            ["Model Used",      result.get("model_used", "Random Forest").upper()],
            ["Imagery Source",  source_label],
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

        if any_synthetic:
            story.append(Spacer(1, 0.25*cm))
            warn_style = ParagraphStyle(
                'Warning', parent=styles['Normal'], fontSize=9,
                textColor=colors.HexColor("#92400e"),
                backColor=colors.HexColor("#fef3c7"),
                borderPadding=(6, 8, 6, 8), leading=13,
            )
            story.append(Paragraph(
                "<b>[!] Synthetic demo data notice:</b> One or more dates in this report used "
                "procedurally generated demo imagery, not real Sentinel-2 acquisitions — "
                "typically because no CDSE credentials were configured, no matching cloud-free "
                "scene was found, or the real download step failed. Statistics and change maps "
                "for those dates are illustrative only and must not be treated as real "
                "measurements of this location.", warn_style))

        story.append(Spacer(1, 0.4*cm))

        from reportlab.platypus import PageBreak

        # Baseline imagery (date_0)
        baseline_img = _fit_image(images_dir / "date_0.png", max_w_cm=8.5, max_h_cm=6.5)
        if baseline_img is not None:
            story.append(Paragraph("Baseline Imagery", section_style))
            story.append(Paragraph(
                f"<b>{actual_dates[0] if actual_dates else 'T1'}</b> — true-colour composite "
                "(Sentinel-2 B04/B03/B02)", body_style))
            story.append(Spacer(1, 0.15*cm))
            story.append(baseline_img)
            story.append(Spacer(1, 0.3*cm))

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

            # Side-by-side: date_i (post) image and change_i (overlay) image
            step_idx = i + 1  # timeline is 1-indexed relative to date_0
            after_img = _fit_image(images_dir / f"date_{step_idx}.png", max_w_cm=8.2, max_h_cm=6.0)
            change_img = _fit_image(images_dir / f"change_{step_idx}.png", max_w_cm=8.2, max_h_cm=6.0)

            if after_img is not None or change_img is not None:
                img_row = []
                label_row = []
                if after_img is not None:
                    img_row.append(after_img)
                    label_row.append(Paragraph(f"<b>{curr_date}</b> — true-colour", small_style))
                if change_img is not None:
                    img_row.append(change_img)
                    label_row.append(Paragraph("Detected change overlay (red = changed)", small_style))
                img_table = Table([label_row, img_row],
                                   colWidths=[8.5*cm] * len(img_row))
                img_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(img_table)
                story.append(Spacer(1, 0.3*cm))

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
