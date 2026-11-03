"""Integration-wide sidebar visibility without changing dashboard contents."""

PANEL_VISIBILITY = "show_nextgen_sidebar"
DASHBOARD_VISIBILITY = "show_lovelace_sidebar"
PANEL_PATH = "r290-control"
DASHBOARD_PATH = "r290-heatpump"


def apply_sidebar_visibility(hass, options):
    """Update existing registered panels, keeping their configuration and URLs."""
    from homeassistant.components import frontend

    panels = hass.data.get(frontend.DATA_PANELS, {})
    for key, path in ((PANEL_VISIBILITY, PANEL_PATH), (DASHBOARD_VISIBILITY, DASHBOARD_PATH)):
        if key not in options or (panel := panels.get(path)) is None:
            continue
        visible = bool(options[key])
        if panel.show_in_sidebar == visible:
            continue
        frontend.async_register_built_in_panel(
            hass, panel.component_name, sidebar_title=panel.sidebar_title,
            sidebar_icon=panel.sidebar_icon,
            sidebar_default_visible=panel.sidebar_default_visible,
            frontend_url_path=path, config=panel.config,
            require_admin=panel.require_admin,
            config_panel_domain=panel.config_panel_domain,
            show_in_sidebar=visible, update=True,
        )


def setup_sidebar_visibility(hass, entry):
    """Restore saved settings now and after Lovelace finishes loading."""
    from homeassistant.const import EVENT_COMPONENT_LOADED
    from homeassistant.core import callback

    apply_sidebar_visibility(hass, entry.options)

    @callback
    def component_loaded(event):
        if event.data.get("component") == "lovelace":
            apply_sidebar_visibility(hass, entry.options)

    entry.async_on_unload(hass.bus.async_listen(EVENT_COMPONENT_LOADED, component_loaded))
