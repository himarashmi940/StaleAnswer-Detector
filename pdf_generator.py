
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from urllib.parse import urlsplit


def _safe_paragraph_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return escape(text).replace("\n", "<br/>")


def generate_pdf(results, freshness_score=None):

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph("Stale-Answer Detector Report", styles["Title"])
    )

    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "AI-Generated Answer Verification Results",
            styles["Heading2"]
        )
    )

    story.append(Spacer(1, 15))

    if freshness_score is not None:
        story.append(
            Paragraph(
                f"<b>Overall freshness score:</b> {int(freshness_score)}/100",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 15))

    for index, item in enumerate(results, start=1):

        story.append(
            Paragraph(f"Claim {index}", styles["Heading2"])
        )

        story.append(
            Paragraph(_safe_paragraph_text(item.get("claim", "")), styles["BodyText"])
        )

        story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                f"<b>Status:</b> {_safe_paragraph_text(item.get('status', 'Unknown'))}",
                styles["BodyText"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Explanation:</b> "
                f"{_safe_paragraph_text(item.get('explanation', ''))}",
                styles["BodyText"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Freshness:</b> "
                f"{_safe_paragraph_text(item.get('freshness_note', ''))}",
                styles["BodyText"]
            )
        )

        story.append(Spacer(1, 12))

        sources = item.get("sources", [])

        if sources:
            story.append(
                Paragraph("<b>Sources:</b>", styles["BodyText"])
            )

            for source in sources:
                url = source.get("url", "")
                title = _safe_paragraph_text(source.get("title", "Source"))

                if isinstance(url, str):
                    parsed_url = urlsplit(url)
                else:
                    parsed_url = None
                if (
                    parsed_url
                    and parsed_url.scheme in {"https", "http"}
                    and parsed_url.netloc
                ):
                    safe_url = escape(url, {'"': "&quot;", "'": "&apos;"})
                    story.append(
                        Paragraph(
                            f'<link href="{safe_url}" color="blue">'
                            f'{title}</link>',
                            styles["BodyText"]
                        )
                    )
                else:
                    story.append(Paragraph(title, styles["BodyText"]))

        story.append(Spacer(1, 20))

    document.build(story)

    buffer.seek(0)

    return buffer.getvalue()
