from backend.services.document_services import ReceiptService, SaleService, TransferService, ReturnToSupplierService, \
    ReturnFromClientService, InventoryService, StockInDocumentService


def get_document_service(document):
    service_map = {
        'receipt': ReceiptService,
        'sale': SaleService,
        'return_to_supplier': ReturnToSupplierService,
        'transfer': TransferService,
        'return_from_client': ReturnFromClientService,
        'inventory': InventoryService,
        'stock_in': StockInDocumentService,  # ⬅️ ДОДАВ ЦЕЙ РЯДОК
    }

    service_class = service_map.get(document.doc_type)
    if not service_class:
        raise ValueError(f"Unsupported document type: {document.doc_type}")

    return service_class(document)
