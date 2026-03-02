"""
Validación de archivos PDF para el sistema electoral.
Previene ataques de archivos maliciosos, oversized, o inválidos.
"""
import io
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from config import Config

logger = logging.getLogger(__name__)

# Configuración de límites (desde Config)
MAX_FILE_SIZE_MB = Config.E14_MAX_FILE_SIZE_MB
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_PAGES = Config.E14_MAX_PAGES
MIN_FILE_SIZE_BYTES = 1024  # 1KB mínimo (PDF válido)

# Magic bytes para PDF
PDF_MAGIC_BYTES = b'%PDF'


@dataclass
class PDFValidationResult:
    """Resultado de validación de PDF."""
    is_valid: bool
    pdf_bytes: Optional[bytes] = None
    page_count: int = 0
    file_size_bytes: int = 0
    error_message: Optional[str] = None

    @property
    def file_size_mb(self) -> float:
        return self.file_size_bytes / (1024 * 1024)


def validate_pdf_bytes(pdf_bytes: bytes) -> PDFValidationResult:
    """
    Valida bytes de PDF.

    Args:
        pdf_bytes: Bytes del archivo PDF

    Returns:
        PDFValidationResult con estado de validación
    """
    file_size = len(pdf_bytes)

    # 1. Verificar tamaño mínimo
    if file_size < MIN_FILE_SIZE_BYTES:
        return PDFValidationResult(
            is_valid=False,
            file_size_bytes=file_size,
            error_message=f"Archivo muy pequeño ({file_size} bytes). No parece ser un PDF válido."
        )

    # 2. Verificar tamaño máximo
    if file_size > MAX_FILE_SIZE_BYTES:
        return PDFValidationResult(
            is_valid=False,
            file_size_bytes=file_size,
            error_message=f"Archivo muy grande: {file_size/1024/1024:.1f}MB (máximo {MAX_FILE_SIZE_MB}MB)"
        )

    # 3. Verificar magic bytes (header PDF)
    if not pdf_bytes[:4] == PDF_MAGIC_BYTES:
        return PDFValidationResult(
            is_valid=False,
            file_size_bytes=file_size,
            error_message="El archivo no es un PDF válido (header incorrecto)"
        )

    # 4. Verificar estructura PDF y contar páginas
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)

        if page_count == 0:
            return PDFValidationResult(
                is_valid=False,
                file_size_bytes=file_size,
                error_message="El PDF no tiene páginas"
            )

        if page_count > MAX_PAGES:
            return PDFValidationResult(
                is_valid=False,
                file_size_bytes=file_size,
                page_count=page_count,
                error_message=f"Demasiadas páginas: {page_count} (máximo {MAX_PAGES})"
            )

    except Exception as e:
        logger.warning(f"Error parseando PDF: {e}")
        return PDFValidationResult(
            is_valid=False,
            file_size_bytes=file_size,
            error_message=f"PDF corrupto o inválido: {str(e)}"
        )

    # 5. Validación exitosa
    return PDFValidationResult(
        is_valid=True,
        pdf_bytes=pdf_bytes,
        page_count=page_count,
        file_size_bytes=file_size
    )


def validate_pdf_file(file) -> PDFValidationResult:
    """
    Valida un archivo PDF desde Flask request.files.

    Args:
        file: FileStorage de Flask

    Returns:
        PDFValidationResult con estado de validación
    """
    # Verificar nombre de archivo
    if not file.filename:
        return PDFValidationResult(
            is_valid=False,
            error_message="No se proporcionó nombre de archivo"
        )

    if not file.filename.lower().endswith('.pdf'):
        return PDFValidationResult(
            is_valid=False,
            error_message="El archivo debe tener extensión .pdf"
        )

    # Leer bytes y validar
    try:
        pdf_bytes = file.read()
        file.seek(0)  # Reset para posible re-lectura
        return validate_pdf_bytes(pdf_bytes)
    except Exception as e:
        logger.error(f"Error leyendo archivo: {e}")
        return PDFValidationResult(
            is_valid=False,
            error_message=f"Error leyendo archivo: {str(e)}"
        )


def validate_pdf_url(url: str, timeout: int = 30) -> PDFValidationResult:
    """
    Valida un PDF desde URL.

    Args:
        url: URL del PDF
        timeout: Timeout en segundos

    Returns:
        PDFValidationResult con estado de validación
    """
    import httpx

    # Validar URL básica
    if not url or not url.startswith(('http://', 'https://')):
        return PDFValidationResult(
            is_valid=False,
            error_message="URL inválida"
        )

    try:
        # Descargar con límite de tamaño
        with httpx.Client(timeout=timeout) as client:
            # Primero HEAD para verificar tamaño
            head_response = client.head(url, follow_redirects=True)
            content_length = head_response.headers.get('content-length')

            if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
                return PDFValidationResult(
                    is_valid=False,
                    file_size_bytes=int(content_length),
                    error_message=f"Archivo muy grande: {int(content_length)/1024/1024:.1f}MB"
                )

            # Descargar
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

            return validate_pdf_bytes(response.content)

    except httpx.TimeoutException:
        return PDFValidationResult(
            is_valid=False,
            error_message=f"Timeout descargando PDF ({timeout}s)"
        )
    except httpx.HTTPStatusError as e:
        return PDFValidationResult(
            is_valid=False,
            error_message=f"Error HTTP: {e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"Error descargando PDF: {e}")
        return PDFValidationResult(
            is_valid=False,
            error_message=f"Error descargando PDF: {str(e)}"
        )
