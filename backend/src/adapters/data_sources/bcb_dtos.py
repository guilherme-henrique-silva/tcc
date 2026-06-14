"""DTOs (Pydantic) das respostas da API do Banco Central do Brasil."""

from typing import List
from pydantic import BaseModel, Field


class SelicRecordDTO(BaseModel):
    """Um ponto da série Selic (SGS 11). Campos chegam como string da API."""

    data: str                       # "DD/MM/YYYY"
    valor: str                      # ex.: "0.045513" — converter p/ float no parse


class DolarCotacaoDTO(BaseModel):
    """Uma cotação PTAX do dólar."""

    cotacao_compra: float = Field(alias="cotacaoCompra")
    cotacao_venda: float = Field(alias="cotacaoVenda")
    data_hora_cotacao: str = Field(alias="dataHoraCotacao")  # "YYYY-MM-DD HH:MM:SS.fff"

    model_config = {"populate_by_name": True}


class PtaxResponseDTO(BaseModel):
    """Envelope OData retornado pelo endpoint PTAX."""

    value: List[DolarCotacaoDTO]
