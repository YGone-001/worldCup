from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
import json
import os


DEFAULT_EXTERNAL_MATCH_ID_MAP: dict[str, dict[str, str]] = {
    "espn": {
        "760415": "wc2026_mex_rsa",
        "760414": "wc2026_kor_cze",
        "760416": "wc2026_can_bih",
        "760417": "wc2026_usa_par",
        "760420": "wc2026_qat_sui",
        "760419": "wc2026_bra_mar",
        "760418": "wc2026_hai_sco",
        "760428": "wc2026_esp_cvi",
        "760431": "wc2026_aut_jor",
        "760435": "wc2026_por_cod",
        "760437": "wc2026_eng_cro",
        "760434": "wc2026_gha_pan",
        "760436": "wc2026_uzb_col",
    },
    "sporttery": {
        "2040174": "wc2026_esp_cvi",
    }
}


class ExternalMatchIdMapper(Protocol):
    def resolve_match_id(self, provider: str, external_match_id: str) -> str | None:
        raise NotImplementedError


class StaticExternalMatchIdMapper:
    def __init__(self, mapping: Mapping[tuple[str, str], str] | None = None) -> None:
        self._mapping: dict[tuple[str, str], str] = {}
        if mapping is not None:
            for key, value in mapping.items():
                provider, external_match_id = key
                self.add(provider, external_match_id, value)

    def add(self, provider: str, external_match_id: str, match_id: str) -> None:
        self._mapping[(self._normalize(provider), str(external_match_id))] = str(match_id)

    def resolve_match_id(self, provider: str, external_match_id: str) -> str | None:
        return self._mapping.get((self._normalize(provider), str(external_match_id)))

    @classmethod
    def from_env(
        cls,
        env_name: str = "WORLDCUP_EXTERNAL_MATCH_ID_MAP",
    ) -> StaticExternalMatchIdMapper:
        mapper = cls()
        for provider, provider_mapping in DEFAULT_EXTERNAL_MATCH_ID_MAP.items():
            for external_match_id, match_id in provider_mapping.items():
                mapper.add(provider, external_match_id, match_id)

        raw_mapping = os.getenv(env_name, "{}")
        try:
            decoded = json.loads(raw_mapping)
        except json.JSONDecodeError:
            decoded = {}

        if not isinstance(decoded, dict):
            return mapper

        for provider, provider_mapping in decoded.items():
            if not isinstance(provider_mapping, dict):
                continue
            for external_match_id, match_id in provider_mapping.items():
                mapper.add(str(provider), str(external_match_id), str(match_id))
        return mapper

    @staticmethod
    def _normalize(provider: str) -> str:
        return provider.strip().lower()
