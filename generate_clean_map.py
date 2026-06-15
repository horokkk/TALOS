#!/usr/bin/env python3
"""
Generate a clean occupancy grid map from Gazebo world file geometry.
Walls are axis-aligned, obstacles use Gazebo yaw rotation values.

Building: 12m x 10m (X: -6 to 6, Y: -5 to 5)
Map resolution: 0.05 m/pixel
Map origin: (-6.49, -6.49)
"""
import numpy as np
import math
import shutil

# Map parameters (match disaster_map.yaml)
RESOLUTION = 0.05  # m/pixel
ORIGIN_X = -6.49
ORIGIN_Y = -6.49
WIDTH = 267   # pixels
HEIGHT = 230  # pixels

FREE = 254
OCCUPIED = 0
UNKNOWN = 205


def world_to_pixel(x, y):
    col = int(round((x - ORIGIN_X) / RESOLUTION))
    row = (HEIGHT - 1) - int(round((y - ORIGIN_Y) / RESOLUTION))
    return col, row


def draw_wall(grid, cx, cy, sx, sy):
    x_min, x_max = cx - sx/2, cx + sx/2
    y_min, y_max = cy - sy/2, cy + sy/2
    col_min, row_max = world_to_pixel(x_min, y_min)
    col_max, row_min = world_to_pixel(x_max, y_max)
    col_min, col_max = max(0, col_min), min(WIDTH-1, col_max)
    row_min, row_max = max(0, row_min), min(HEIGHT-1, row_max)
    grid[row_min:row_max+1, col_min:col_max+1] = OCCUPIED


def draw_rotated_obstacle(grid, cx, cy, sx, sy, yaw):
    hw, hh = sx/2, sy/2
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    cos_a, sin_a = math.cos(yaw), math.sin(yaw)
    world_corners = []
    for lx, ly in corners:
        wx = cx + lx * cos_a - ly * sin_a
        wy = cy + lx * sin_a + ly * cos_a
        world_corners.append((wx, wy))
    pix_corners = [world_to_pixel(wx, wy) for wx, wy in world_corners]
    cols = [p[0] for p in pix_corners]
    rows = [p[1] for p in pix_corners]
    c_min, c_max = max(0, min(cols)-1), min(WIDTH-1, max(cols)+1)
    r_min, r_max = max(0, min(rows)-1), min(HEIGHT-1, max(rows)+1)
    for r in range(r_min, r_max+1):
        for c in range(c_min, c_max+1):
            px = ORIGIN_X + c * RESOLUTION
            py = ORIGIN_Y + (HEIGHT - 1 - r) * RESOLUTION
            dx, dy = px - cx, py - cy
            lx = dx * cos_a + dy * sin_a
            ly = -dx * sin_a + dy * cos_a
            if abs(lx) <= hw and abs(ly) <= hh:
                grid[r, c] = OCCUPIED


def main():
    grid = np.full((HEIGHT, WIDTH), UNKNOWN, dtype=np.uint8)

    # Free space inside building
    c1, r1 = world_to_pixel(-5.9, -4.9)
    c2, r2 = world_to_pixel(5.9, 4.9)
    grid[min(r1,r2):max(r1,r2)+1, min(c1,c2):max(c1,c2)+1] = FREE

    # Entrance approach area
    c1, r1 = world_to_pixel(-1.5, -6.4)
    c2, r2 = world_to_pixel(1.5, -4.9)
    grid[min(r1,r2):max(r1,r2)+1, min(c1,c2):max(c1,c2)+1] = FREE

    # === OUTER WALLS ===
    draw_wall(grid, -3.5, -5.0, 5.0, 0.15)
    draw_wall(grid, 3.5, -5.0, 5.0, 0.15)
    draw_wall(grid, 0.0, 5.0, 12.0, 0.15)
    draw_wall(grid, -6.0, 0.0, 0.15, 10.0)
    draw_wall(grid, 6.0, 0.0, 0.15, 10.0)

    # === INNER WALLS ===
    draw_wall(grid, -2.0, -3.9, 0.15, 2.0)
    draw_wall(grid, -2.0, -0.2, 0.15, 2.2)
    draw_wall(grid, -4.0, 1.0, 4.0, 0.15)
    draw_wall(grid, -0.7, 1.0, 2.4, 0.15)
    draw_wall(grid, 2.0, 1.0, 0.6, 0.15)
    draw_wall(grid, 2.3, 2.25, 0.15, 2.5)
    draw_wall(grid, 1.3, 3.5, 2.0, 0.15)
    draw_wall(grid, 2.9, 1.0, 1.0, 0.15)
    draw_wall(grid, 5.35, 1.0, 1.1, 0.15)

    # === OBSTACLES (Gazebo world positions + yaw) ===
    draw_rotated_obstacle(grid, 0.0, -3.5, 1.0, 0.8, 0.3)
    draw_rotated_obstacle(grid, 1.5, -1.5, 2.0, 0.12, 0.8)
    draw_rotated_obstacle(grid, -4.0, -1.5, 1.2, 0.6, 0.3)
    draw_rotated_obstacle(grid, -3.0, -3.0, 0.5, 0.5, -0.4)
    draw_rotated_obstacle(grid, -5.0, -4.0, 0.7, 0.5, 0.6)
    draw_rotated_obstacle(grid, 5.0, 3.0, 0.4, 1.2, 0.1)
    draw_rotated_obstacle(grid, 3.5, 3.5, 0.5, 0.3, 1.2)
    draw_rotated_obstacle(grid, 1.3, 2.5, 0.5, 0.8, 0.0)

    # Write PGM
    output_path = "src/talos_bringup/maps/disaster_map.pgm"
    with open(output_path, 'wb') as f:
        f.write(f"P5\n{WIDTH} {HEIGHT}\n255\n".encode('ascii'))
        f.write(grid.tobytes())

    shutil.copy(output_path, "map/disaster_map.pgm")
    print(f"Clean map generated: {WIDTH}x{HEIGHT} px, {RESOLUTION} m/px")


if __name__ == "__main__":
    main()
