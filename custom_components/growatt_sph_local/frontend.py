"""Mitgelieferte Dashboard-Karte: einmal pro HA-Lauf ausliefern und als Lovelace-Ressource eintragen.

Das Vorgehen (Ressource statt add_extra_js_url, Cache-Busting über die Version) ist
übernommen aus BavarianData von Chris Krammer (MIT-Lizenz),
https://github.com/JustChr/BavarianData – custom_components/bavariandata/frontend.py
"""
from __future__ import annotations

import json
import logging
import os

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_started

from .const import CARD_FILENAME, CARD_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_DATA_KEY = f"{DOMAIN}_card_registered"


async def async_register_card(hass: HomeAssistant) -> None:
    """Karte unter /growatt_sph_local/growatt-sph-card.js ausliefern und in Lovelace eintragen.

    Als Lovelace-Ressource statt über ``add_extra_js_url``: Letzteres lädt die Karte
    ohne Warten, und der Service-Worker des Frontends liefert die Seite nach einem
    Neuladen manchmal aus dem Cache ohne sie aus (home-assistant/frontend#18728).
    """
    if hass.data.get(_DATA_KEY):
        return
    path = os.path.join(os.path.dirname(__file__), "www", CARD_FILENAME)
    if not os.path.isfile(path):
        _LOGGER.warning("Dashboard-Karte fehlt: %s", path)
        return

    from homeassistant.components.http import StaticPathConfig

    hass.data[_DATA_KEY] = True  # vor dem ersten await belegen (mehrere Einträge)
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, path, cache_headers=False)]
        )
    except BaseException:
        hass.data.pop(_DATA_KEY, None)
        raise

    version = await hass.async_add_executor_job(_integration_version)
    url = f"{CARD_URL}?v={version}"

    async def _publish(_hass: HomeAssistant) -> None:
        if not await _async_register_resource(hass, url):
            _async_add_module(hass, url)

    async_at_started(hass, _publish)


async def _async_register_resource(hass: HomeAssistant, url: str) -> bool:
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        return False
    mode = getattr(lovelace, "resource_mode", None) or getattr(lovelace, "mode", None)
    if mode != "storage":
        return False
    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True
    try:
        for item in resources.async_items():
            if str(item.get("url", "")).split("?", 1)[0] != CARD_URL:
                continue
            if item.get("url") != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return True
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:  # noqa: BLE001 – Einrichtung nie an einer Dashboard-Ressource scheitern lassen
        _LOGGER.exception("Dashboard-Karte konnte nicht als Ressource eingetragen werden")
        return False
    _LOGGER.debug("%s: Karte als Lovelace-Ressource %s eingetragen", DOMAIN, url)
    return True


@callback
def _async_add_module(hass: HomeAssistant, url: str) -> None:
    """Rückfall für YAML-verwaltete Ressourcen."""
    if "frontend" not in hass.config.components:
        return
    try:
        from homeassistant.components.frontend import add_extra_js_url
    except ImportError:  # pragma: no cover
        return
    add_extra_js_url(hass, url)


def _integration_version() -> str:
    try:
        with open(os.path.join(os.path.dirname(__file__), "manifest.json"), encoding="utf-8") as fh:
            return str(json.load(fh).get("version", "0"))
    except (OSError, ValueError):
        return "0"
