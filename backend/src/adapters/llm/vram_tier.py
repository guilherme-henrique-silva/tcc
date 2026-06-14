"""VramTier — enum de faixas de VRAM para recomendação de uso dos modelos locais.

A VRAM mínima de cada modelo é obtida da string no catálogo (variável de ambiente
LLM_MODELS). Este enum transforma essa faixa em uma recomendação textual padronizada,
sem depender de strings livres no .env.
"""

from __future__ import annotations

import re
from enum import Enum


class VramTier(Enum):
    """Faixas fixas de VRAM mínima com recomendação de uso associada."""

    LIGHT = "light"        # <= 4 GB
    BALANCED = "balanced"  # 5–8 GB
    ADVANCED = "advanced"  # > 8 GB

    @property
    def recommendation(self) -> str:
        """Texto de recomendação de uso exibido na UI."""
        _MAP = {
            VramTier.LIGHT: (
                "Modelo leve, ideal para laptops com pouca memória gráfica. "
                "Boa escolha para tarefas de limpeza e extração de metadados em textos curtos."
            ),
            VramTier.BALANCED: (
                "Equilíbrio entre custo e qualidade. Adequado para tratamento de notícias com "
                "bom desempenho mesmo em GPUs de entrada (4–8 GB de VRAM)."
            ),
            VramTier.ADVANCED: (
                "Modelo maior, indicado para revisão detalhada de texto, ajuste de tom e "
                "sumarização avançada. Requer GPU dedicada com mais de 8 GB de VRAM."
            ),
        }
        return _MAP[self]

    @classmethod
    def from_vram_string(cls, vram: str) -> "VramTier":
        """Infere a faixa a partir da string de VRAM do catálogo (ex.: '8 GB', '4 GB', '16 GB').

        Extrai o primeiro número inteiro encontrado e classifica na faixa correspondente.
        Valores não reconhecidos retornam BALANCED como padrão seguro.
        """
        match = re.search(r"(\d+)", vram or "")
        if not match:
            return cls.BALANCED

        gb = int(match.group(1))

        if gb <= 4:
            return cls.LIGHT
        if gb <= 8:
            return cls.BALANCED
        return cls.ADVANCED
