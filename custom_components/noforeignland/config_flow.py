"""Config, reconfigure and options flows (SPEC HA-SAIL-SPEC-001 §9.10).

No request is sent here: a test send would put a point on noforeignland's public map, so a
key is only proved by the first send.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import protocol
from .const import (
    CONF_BOAT_KEY,
    CONF_CAPACITY,
    CONF_INTEGRATION_KEY,
    CONF_KEEPALIVE_H,
    CONF_MIN_MOVE_M,
    CONF_MIN_SPEED_KN,
    CONF_SAMPLE_S,
    CONF_SEND_MIN,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
)
from .protocol import is_integration_key

SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

# Option: (minimum, maximum, step, unit)
OPTION_RANGES: dict[str, tuple[float, float, float, str]] = {
    CONF_SAMPLE_S: (10, 3600, 10, "s"),
    CONF_MIN_MOVE_M: (0, 5000, 10, "m"),
    CONF_MIN_SPEED_KN: (0, 20, 0.1, "kn"),
    CONF_KEEPALIVE_H: (1, 168, 1, "h"),
    CONF_SEND_MIN: (1, 1440, 1, "min"),
    CONF_CAPACITY: (100, 100_000, 100, "points"),
}


def vigie_tracker(hass: HomeAssistant) -> str | None:
    """Vigie's own boat tracker, proposed as the source."""
    for entry in er.async_get(hass).entities.values():
        if entry.platform == "vigie" and entry.translation_key == "position":
            return entry.entity_id
    return None


def _keys_errors(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input[CONF_BOAT_KEY].strip():
        errors[CONF_BOAT_KEY] = "boat_key"
    override = user_input.get(CONF_INTEGRATION_KEY, "").strip()
    if override and not is_integration_key(override):
        errors[CONF_INTEGRATION_KEY] = "integration_key"
    elif not override and protocol.integration_key(None) is None:
        errors[CONF_INTEGRATION_KEY] = "integration_key_needed"
    return errors


def _keys(user_input: dict[str, Any]) -> dict[str, Any]:
    """Keys as stored: the override only when given (OD-45: built in otherwise)."""
    data = {k: v.strip() for k, v in user_input.items() if k != CONF_SOURCE}
    data[CONF_INTEGRATION_KEY] = data.get(CONF_INTEGRATION_KEY, "")
    return data


class NflConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _keys_errors(user_input)
            if not errors:
                source = user_input[CONF_SOURCE]
                await self.async_set_unique_id(source)
                self._abort_if_unique_id_configured()
                state = self.hass.states.get(source)
                title = state.name if state else source
                data = {CONF_SOURCE: source, **_keys(user_input)}
                return self.async_create_entry(title=title, data=data)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOURCE, default=vigie_tracker(self.hass) or vol.UNDEFINED
                ): EntitySelector(EntitySelectorConfig(domain="device_tracker")),
                vol.Required(CONF_BOAT_KEY): SECRET,
                vol.Optional(CONF_INTEGRATION_KEY): SECRET,
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """New keys, for example after noforeignland refused one."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _keys_errors(user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=_keys(user_input))
        schema = vol.Schema(
            {vol.Required(CONF_BOAT_KEY): SECRET, vol.Optional(CONF_INTEGRATION_KEY): SECRET}
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> NflOptionsFlow:
        return NflOptionsFlow()


class NflOptionsFlow(OptionsFlow):
    """OD-43: the reference client's defaults, all adjustable."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options
        fields: dict[Any, Any] = {}
        for key, (low, high, step, unit) in OPTION_RANGES.items():
            fields[vol.Required(key, default=current.get(key, DEFAULTS[key]))] = NumberSelector(
                NumberSelectorConfig(
                    min=low,
                    max=high,
                    step=step,
                    unit_of_measurement=unit,
                    mode=NumberSelectorMode.BOX,
                )
            )
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
