"""Docling converter adapter - converte links de notícias em Markdown (Seção 8 do spec)."""

from typing import Optional
from urllib.parse import urlparse


# Mapa dos portais listados no plano (G1, UOL, CNN Brasil, Folha, Estadão, Metrópoles).
PORTAL_NAMES = {
    "g1.globo.com": "G1",
    "globo.com": "G1",
    "uol.com.br": "UOL",
    "economia.uol.com.br": "UOL",
    "cnnbrasil.com.br": "CNN Brasil",
    "folha.uol.com.br": "Folha",
    "www1.folha.uol.com.br": "Folha",
    "estadao.com.br": "Estadão",
    "einvestidor.estadao.com.br": "Estadão",
    "metropoles.com": "Metrópoles",
}


class DoclingConverterAdapter:
    """Wrapper sobre docling.DocumentConverter (texto e tabelas; ignora mídia)."""

    def __init__(self, converter=None):
        """Recebe um DocumentConverter já configurado ou cria o padrão (lazy)."""
        self._converter = converter

    def to_markdown(self, url: str) -> str:
        """Converte o conteúdo de um link em Markdown, ignorando mídia não textual."""
        converter = self._get_converter()
        result = converter.convert(url)
        return result.document.export_to_markdown()

    def site_name(self, url: str) -> str:
        """Deriva o nome do portal a partir do domínio do link (Rule 1)."""
        host = (urlparse(url).hostname or "").lower()

        if host.startswith("www."):
            host = host[4:]

        return PORTAL_NAMES.get(host, host or "desconhecido")

    def _get_converter(self):
        """Cria o DocumentConverter desabilitando OCR/imagens (lazy import)."""
        if self._converter is not None:
            return self._converter

        self._converter = self._build_default_converter()
        return self._converter

    def _build_default_converter(self):
        """Build a DocumentConverter that keeps only text and tables (Rule 1)."""
        from docling.document_converter import DocumentConverter

        pipeline_options = self._build_pipeline_options()

        if pipeline_options is None:
            return DocumentConverter()

        return self._converter_with_options(DocumentConverter, pipeline_options)

    def _build_pipeline_options(self):
        """Disable OCR and image extraction when the API exposes it (Rule 1)."""
        try:
            from docling.datamodel.pipeline_options import PdfPipelineOptions

            options = PdfPipelineOptions()
            options.do_ocr = False
            options.generate_page_images = False
            options.generate_picture_images = False
            return options

        except Exception:
            return None

    def _converter_with_options(self, converter_cls, pipeline_options):
        """Attach pipeline options across docling versions, falling back safely."""
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import PdfFormatOption

            return converter_cls(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

        except Exception:
            return converter_cls()
