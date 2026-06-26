"""Service for generating and retrieving paper summaries."""

import logging
import os

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.models.setting import Setting
from src.services.drive import DriveService
from src.services.pdf_parser import PdfParser

logger = logging.getLogger(__name__)


class SummaryService:
    def get_summary(self, paper_id: str, db: Session) -> tuple[str | None, bool]:
        """Retrieve the cached summary text and whether a whiteboard image is stored."""
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise ValueError("Paper not found")
        return paper.summary_text, paper.summary_image is not None

    def generate_summary(
        self, paper_id: str, db: Session, instructions: str | None = None
    ) -> tuple[str, bool]:
        """Generate a paper summary and a whiteboard visual.

        The summary is tailored to the user's background (from Settings) and optionally
        guided by user-provided custom instructions. Saves both to the database.
        """
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise ValueError("Paper not found")

        # 1. Ensure full text is available
        text = paper.extracted_text
        if not text or len(text.strip()) < 100:
            logger.info("Extracted text is empty or too short. Attempting to parse PDF.")
            # DriveService or PdfParser might raise exceptions; let them bubble up as 502/503
            pdf_bytes = DriveService().download(paper.drive_file_id)
            text = PdfParser().extract_full_text(pdf_bytes)
            if not text:
                raise ValueError("Could not extract text from the PDF file")
            paper.extracted_text = text
            db.flush()

        # 2. Get user settings background
        about_me_setting = db.query(Setting).filter(Setting.key == "about_me").first()
        about_me = about_me_setting.value.strip() if about_me_setting else ""

        # 3. Call Gemini to generate the summary text
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        model_name = os.environ.get("GEMINI_PDF_MODEL", "").strip()
        if not model_name or model_name == "gemini-2.0-flash":
            model_name = "gemini-2.5-flash"

        client = genai.Client(api_key=api_key)

        prompt = (
            "You are a research assistant. Read the following paper text and "
            "generate a comprehensive summary. The summary must satisfy these constraints:\n"
            "- Be approximately one page long (around 500-800 words).\n"
            "- Summarize the key points and the relevance of the paper.\n"
            "- Only include mathematics if it is a core part of the summary, "
            "and if so, explain all the terms.\n"
            "- Use LaTeX notation for mathematical equations, using standard "
            "markdown formatting (e.g., $math$ for inline and $$math$$ for block "
            "equations).\n"
        )
        if about_me:
            prompt += f"- Tailor the explanation to a reader with this background: '{about_me}'.\n"
        if instructions:
            prompt += f"- Please incorporate these custom user instructions: '{instructions}'.\n"
        prompt += "Return the summary in clean markdown format."

        logger.info("Generating summary for paper %s using model %s", paper_id, model_name)
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, text],  # type: ignore[arg-type]
        )

        summary_text = response.text
        if not summary_text:
            raise ValueError("Gemini returned an empty summary text response")

        # 4. Generate whiteboard visual using gemini-3.1-flash-image
        img_bytes = None
        try:
            image_prompt = (
                f"Take the following summary text:\n\n{summary_text}\n\n"
                "Transform this summary into a whiteboard diagram (with diagrams, "
                "arrows, boxes, and captions explaining the core idea visually "
                "with colorful marker colors). "
                "The image must have a solid, clean, pure white background, with "
                "no classroom or lab background. "
                "The view must be a flat 2D perspective, front-facing, with no "
                "fisheye lens effect, no camera tilt, and no borders or frames."
            )
            logger.info(
                "Generating whiteboard image for paper %s using gemini-3.1-flash-image",
                paper_id,
            )
            image_response = client.models.generate_content(
                model="gemini-3.1-flash-image",
                contents=[image_prompt],  # type: ignore[arg-type]
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )

            # Retrieve parts from response safely
            content_parts = []
            if hasattr(image_response, "parts") and image_response.parts:
                content_parts = image_response.parts
            elif hasattr(image_response, "candidates") and image_response.candidates:
                candidate = image_response.candidates[0]
                if candidate.content and candidate.content.parts:
                    content_parts = candidate.content.parts

            for part in content_parts:
                if part.inline_data and part.inline_data.data:
                    img_bytes = part.inline_data.data
                    break
        except Exception as e:
            # Silent image generation failure per user instructions
            logger.exception("Silent error: failed to generate summary whiteboard image: %s", e)

        # Fallback to SVG diagram if image generation failed
        if img_bytes is None:
            logger.info("Image generation failed. Falling back to SVG diagram generation.")
            img_bytes = self._generate_fallback_svg(client, model_name, summary_text)

        # 5. Persist to DB
        paper.summary_text = summary_text
        paper.summary_image = img_bytes
        db.commit()

        return summary_text, img_bytes is not None

    def _generate_fallback_svg(
        self, client: genai.Client, model_name: str, summary_text: str
    ) -> bytes | None:
        """Fallback to generating a hand-drawn-style SVG diagram using the text model."""
        prompt = (
            f"Take the following summary text:\n\n{summary_text}\n\n"
            "now take the text from your reply and transform it into a professor's "
            "whiteboard image: diagrams, arrows, boxes, and captions explaining "
            "the core idea visually. Use colors as well.\n\n"
            "Generate this whiteboard diagram as a clean, responsive, and "
            "visually appealing SVG. Use a light whiteboard theme (with "
            "white/off-white background, and colored marker lines for arrows, "
            "boxes, and text). Ensure all text labels are readable and "
            "properly positioned.\n"
            "Return ONLY the raw SVG code. Do not wrap it in markdown code "
            "fences, do not write any explanation. Start immediately with "
            "'<svg' and end with '</svg>'."
        )
        try:
            logger.info("Generating fallback SVG diagram using text model %s", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt],  # type: ignore[arg-type]
            )
            svg_text = response.text
            if not svg_text:
                return None
            svg_text = svg_text.strip()
            # Remove potential markdown block wrap
            if svg_text.startswith("```"):
                lines = svg_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                svg_text = "\n".join(lines).strip()

            # Find the starting <svg tag
            if not svg_text.startswith("<svg"):
                idx = svg_text.find("<svg")
                if idx != -1:
                    svg_text = svg_text[idx:]
                else:
                    logger.warning("Generated text did not contain a valid SVG root tag")
                    return None
            return svg_text.encode("utf-8")
        except Exception as e:
            logger.exception("Failed to generate fallback SVG: %s", e)
            return None
