"""Pydantic request/response models for the FastAPI backend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QuoteUpdateRequest(BaseModel):
    customer_name: str | None = None
    machine_model: str | None = None
    sold_to_address: str | None = None
    ship_to_address: str | None = None
    telephone: str | None = None
    customer_contact_person: str | None = None
    customer_po: str | None = None
    incoterm: str | None = None
    company: str | None = None
    serial_number: str | None = None
    ax: str | None = None
    ox: str | None = None
    via: str | None = None
    tax_id: str | None = None
    hs_code: str | None = None
    customer_number: str | None = None
    order_date: str | None = None


class QuoteResponse(BaseModel):
    id: int
    quote_ref: str
    customer_name: str | None = None
    machine_model: str | None = None
    sold_to_address: str | None = None
    ship_to_address: str | None = None
    telephone: str | None = None
    customer_contact_person: str | None = None
    customer_po: str | None = None
    processing_date: str | None = None
    incoterm: str | None = None
    company: str | None = None
    serial_number: str | None = None
    ax: str | None = None
    ox: str | None = None
    via: str | None = None
    tax_id: str | None = None
    hs_code: str | None = None
    customer_number: str | None = None
    order_date: str | None = None


class QuoteUploadResponse(BaseModel):
    quote_ref: str
    items_count: int
    linked_existing_client_id: int | None = None


class PricedItemResponse(BaseModel):
    id: int
    item_description: str | None = None
    item_quantity: str | None = None
    item_price_str: str | None = None
    item_price_numeric: float | None = None


class LineItem(BaseModel):
    description: str = ""
    quantity_text: str | None = None
    selection_text: str | None = None
    item_price_numeric: float | None = None


class MachineData(BaseModel):
    machine_name: str
    main_item: dict[str, Any] = Field(default_factory=dict)
    add_ons: list[dict[str, Any]] = Field(default_factory=list)
    common_items: list[dict[str, Any]] = Field(default_factory=list)
    client_quote_ref: str | None = None


class MachineResponse(BaseModel):
    id: int
    machine_name: str
    description: str | None = None
    machine_type: str | None = None
    quote_ref: str
    client_name: str | None = None
    client_id: int | None = None
    machine_template_id: int | None = None
    status: Literal["draft", "processed", "ready"] = "processed"
    processing_date: str | None = None
    template_data: dict[str, Any] | None = None


class MachineDetailResponse(BaseModel):
    id: int
    machine_name: str
    client_quote_ref: str
    processing_date: str | None = None
    machine_data: dict[str, Any]


class MachineGroupingRequest(BaseModel):
    quote_ref: str | None = None
    all_items: list[dict[str, Any]]
    main_machine_indices: list[int]
    common_option_indices: list[int]


class MachineGroupingResponse(BaseModel):
    machines: list[dict[str, Any]]
    common_items: list[dict[str, Any]]


class IdentifyMachinesRequest(BaseModel):
    items: list[dict[str, Any]]


class ExtractionRequest(BaseModel):
    machine_data: dict[str, Any]
    common_items: list[dict[str, Any]] = Field(default_factory=list)
    template_contexts: dict[str, Any] | None = None
    full_pdf_text: str


class ExtractionResponse(BaseModel):
    filled_data: dict[str, str]
    confidence_scores: dict[str, float]
    suggestions: list[dict[str, Any]]
    metadata: dict[str, Any] | None = None


class GenerateDocumentRequest(BaseModel):
    machine_data: dict[str, Any]
    filled_data: dict[str, str]
    common_items: list[dict[str, Any]] = Field(default_factory=list)
    template_contexts: dict[str, Any] | None = None
    machine_id: int | None = None


class GenerateDocumentResponse(BaseModel):
    file_path: str
    machine_id: int | None = None
    machine_template_id: int | None = None


class GoaFormModification(BaseModel):
    field_key: str
    original_value: str | None = None
    modified_value: str
    reason: str | None = None


class GoaOutputOptions(BaseModel):
    included_sections: list[str] | None = None
    hide_empty_sections: bool = True
    hide_empty_fields: bool = True
    pure_output: bool = False
    label_overrides: dict[str, str] = Field(default_factory=dict)
    format: Literal["html"] = "html"


class FillFormRequest(BaseModel):
    filled_data: dict[str, Any] = Field(default_factory=dict)
    output_options: GoaOutputOptions | None = None


class FillFormResponse(BaseModel):
    html: str


class GoaFormSaveRequest(BaseModel):
    filled_data: dict[str, Any] = Field(default_factory=dict)
    modifications: list[GoaFormModification] | None = None
    generate_output: bool = True
    output_options: GoaOutputOptions | None = None


class GoaGenerateDocumentRequest(BaseModel):
    output_options: GoaOutputOptions | None = None


class GoaFormSaveResponse(BaseModel):
    machine_template_id: int
    saved_at: str
    file_path: str
    html: str


class GoaFormListItemResponse(BaseModel):
    machine_template_id: int
    machine_id: int
    quote_ref: str
    machine_name: str
    template_type: str
    generated_file_path: str | None = None
    processing_date: str | None = None


class GoaSchemaFieldResponse(BaseModel):
    key: str
    label: str
    type: Literal["text", "textarea", "checkbox", "number"]


class GoaSchemaGroupResponse(BaseModel):
    title: str | None = None
    fields: list[GoaSchemaFieldResponse] = Field(default_factory=list)


class GoaSchemaSectionResponse(BaseModel):
    id: str
    title: str
    field_count: int = 0
    groups: list[GoaSchemaGroupResponse] = Field(default_factory=list)


class GoaFormSchemaResponse(BaseModel):
    sections: list[GoaSchemaSectionResponse] = Field(default_factory=list)
    field_count: int = 0


class GoaFormDetailResponse(BaseModel):
    machine_template_id: int
    machine_id: int
    quote_ref: str
    machine_name: str
    template_type: str
    generated_file_path: str | None = None
    processing_date: str | None = None
    template_data: dict[str, Any] = Field(default_factory=dict)
    output_options: GoaOutputOptions | None = None
    field_labels: dict[str, str] = Field(default_factory=dict)
    modifications: list[dict[str, Any]] = Field(default_factory=list)
    html: str


class GoaGenerateDocumentApiRequest(BaseModel):
    machine_template_id: int
    filled_data: dict[str, Any] = Field(default_factory=dict)
    options: GoaOutputOptions | None = None


class GoaGenerateDocumentApiResponse(BaseModel):
    machine_template_id: int
    generated_at: str
    format: Literal["html", "docx"]
    file_path: str
    download_url: str


class ShippingPrefillResponse(BaseModel):
    quote_id: int
    quote_ref: str
    shipping_data: dict[str, Any] = Field(default_factory=dict)


class ShippingSaveRequest(BaseModel):
    shipping_data: dict[str, Any] = Field(default_factory=dict)


class ShippingSaveResponse(BaseModel):
    quote_id: int
    quote_ref: str
    saved_at: str
    shipping_data: dict[str, Any] = Field(default_factory=dict)


class ShippingLoadResponse(BaseModel):
    quote_id: int
    quote_ref: str
    created_date: str | None = None
    modified_date: str | None = None
    shipping_data: dict[str, Any] = Field(default_factory=dict)


class ShippingGenerateRequest(BaseModel):
    document_type: Literal["packing_slip", "commercial_invoice", "certificate_origin", "all"] = "all"
    output_format: Literal["docx", "html"] = "docx"
    shipping_data: dict[str, Any] | None = None


class CorPrefillResponse(BaseModel):
    quote_id: int
    quote_ref: str
    cor_data: dict[str, Any] = Field(default_factory=dict)


class CorSaveRequest(BaseModel):
    cor_data: dict[str, Any] = Field(default_factory=dict)


class CorSaveResponse(BaseModel):
    quote_id: int
    quote_ref: str
    saved_at: str
    cor_data: dict[str, Any] = Field(default_factory=dict)


class CorLoadResponse(BaseModel):
    quote_id: int
    quote_ref: str
    created_date: str | None = None
    modified_date: str | None = None
    cor_data: dict[str, Any] = Field(default_factory=dict)


class CorGenerateRequest(BaseModel):
    cor_data: dict[str, Any] | None = None


class TemplateUpdateRequest(BaseModel):
    template_data: dict[str, Any]
    template_type: str = "GOA"
    generated_file_path: str | None = None


class TemplateResponse(BaseModel):
    id: int
    template_data: dict[str, Any]
    generated_file_path: str | None = None
    processing_date: str | None = None


class ReportResponse(BaseModel):
    machine_id: int
    machine_name: str
    html: str


class ProcessingArtifactsResponse(BaseModel):
    quote_ref: str
    full_pdf_text: str
    pdf_filename: str | None = None
    items: list[dict[str, Any]]
    machines: list[dict[str, Any]]


class MachineProcessingDataResponse(BaseModel):
    machine_id: int
    quote_ref: str
    machine_data: dict[str, Any]
    main_item: dict[str, Any] = Field(default_factory=dict)
    options: list[dict[str, Any]] = Field(default_factory=list)
    common_items: list[dict[str, Any]] = Field(default_factory=list)
    full_pdf_text: str = ""
