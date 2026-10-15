"""Contratto `contracts.VocabolarioTemi` (single source of truth)."""

from __future__ import annotations

import pytest
from contracts import VocabolarioTemi
from pydantic import ValidationError


def _ok(**override: object) -> VocabolarioTemi:
    base: dict[str, object] = {
        "contemplativi": frozenset({"silenzio", "verde"}),
        "arte": frozenset({"arte"}),
        "insoliti": frozenset({"artigianato"}),
        "verde": frozenset({"verde"}),
        "bambini": "con-bambini",
    }
    base.update(override)
    return VocabolarioTemi.model_validate(base)


def test_valido_e_hashable() -> None:
    v = _ok()
    assert v.bambini == "con-bambini"
    assert hash(v) == hash(_ok())
    assert v == _ok()


@pytest.mark.parametrize("campo", ["contemplativi", "arte", "insoliti", "verde"])
def test_insiemi_vuoti_ammessi(campo: str) -> None:
    assert getattr(_ok(**{campo: frozenset()}), campo) == frozenset()


@pytest.mark.parametrize("slug", ["", "Arte", "con bambini", "-x", "x-", "x--y", "à", "a_b"])
def test_slug_invalido_nei_gruppi(slug: str) -> None:
    with pytest.raises(ValidationError):
        _ok(arte=frozenset({slug}))


@pytest.mark.parametrize("slug", ["", "Con-Bambini", "con bambini", "-x", "x--y"])
def test_slug_invalido_in_bambini(slug: str) -> None:
    with pytest.raises(ValidationError):
        _ok(bambini=slug)


def test_bambini_obbligatorio_e_non_gruppo() -> None:
    with pytest.raises(ValidationError):
        VocabolarioTemi.model_validate(
            {
                "contemplativi": [],
                "arte": [],
                "insoliti": [],
                "verde": [],
            }
        )


def test_immutabile() -> None:
    v = _ok()
    with pytest.raises(ValidationError):
        setattr(v, "bambini", "altro")  # noqa: B010


def test_campi_extra_vietati() -> None:
    with pytest.raises(ValidationError):
        _ok(prezzo=1.0)


def test_roundtrip_json() -> None:
    v = _ok()
    assert VocabolarioTemi.model_validate_json(v.model_dump_json()) == v
