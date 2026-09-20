"""Headless rendering of a Position to PNG."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
from catanatron import Game
from catanatron.gym.envs.pygame_renderer import PygameRenderer


def write_position_png(game: Game, path: Path) -> Path:
    rgb = PygameRenderer(render_scale=1.0).render(game)
    surface = pygame.surfarray.make_surface(np.swapaxes(rgb, 0, 1))
    pygame.image.save(surface, str(path))
    return path
