from src.processors._ocr import OCRPlugin
from src.processors.base import BaseDocumentProcessor, DocumentProcessorException

ocr = OCRPlugin()

__all__ = ["ocr", "BaseDocumentProcessor", "DocumentProcessorException"]
