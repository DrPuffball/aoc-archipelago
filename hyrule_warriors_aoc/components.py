from worlds.LauncherComponents import Component, Type, components, launch

from .data import GAME_NAME


def run_client(*args: str) -> None:
    # Imported lazily so the client (and its GUI dependencies) only load when launched.
    from .client.ap_client import launch as launch_client

    launch(launch_client, name="Age of Calamity Client", args=args)


components.append(Component("Age of Calamity Client", func=run_client, game_name=GAME_NAME, component_type=Type.CLIENT))
