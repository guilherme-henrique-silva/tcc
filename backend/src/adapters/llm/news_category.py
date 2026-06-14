"""Categorias de notícias para classificação pelo LLM."""

from enum import Enum


class NewsCategory(str, Enum):
    FINANCAS = "finanças"
    MACROECONOMIA = "macroeconomia"
    MICROECONOMIA = "microeconomia"
    POLITICA = "política"
    AGRONEGOCIO = "agronegócio"
    TECNOLOGIA = "tecnologia"
