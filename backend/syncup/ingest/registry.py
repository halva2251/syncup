"""Service registry — maps service names to client instances.

Import register_default_clients and call it from the app lifespan to populate
the registry at startup. All other code (sync route, dimensions validator) uses
get_client() and registered_services() for service-agnostic dispatch.
"""
from __future__ import annotations

from syncup.config import Settings
from syncup.ingest.protocol import ServiceClient

_REGISTRY: dict[str, ServiceClient] = {}


def register(client: ServiceClient) -> None:
    """Register a service client. Replaces any existing client for that service."""
    _REGISTRY[client.service_name] = client


def get_client(service: str) -> ServiceClient:
    """Return the registered client for *service*.

    Raises KeyError if the service is not registered.
    """
    try:
        return _REGISTRY[service]
    except KeyError:
        raise KeyError(service) from None


def registered_services() -> set[str]:
    """Return a copy of all currently registered service names."""
    return set(_REGISTRY)


def _clear() -> None:
    """Remove all registered clients. Use only in tests."""
    _REGISTRY.clear()


def register_default_clients(settings: Settings) -> None:
    """Construct and register the built-in service clients.

    Called from the app lifespan with the loaded Settings object.
    Safe to call multiple times — registering overwrites the previous entry.
    """
    from syncup.ingest.lastfm import LastfmClient
    from syncup.ingest.spotify import SpotifyClient
    from syncup.ingest.steam import SteamClient

    register(SteamClient(api_key=settings.steam_api_key))
    register(LastfmClient(api_key=settings.lastfm_api_key))
    register(
        SpotifyClient(
            client_id=settings.spotify_client_id,
            redirect_uri=settings.spotify_redirect_uri,
            client_secret=settings.spotify_client_secret,
        )
    )
