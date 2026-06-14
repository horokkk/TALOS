#!/usr/bin/env python3
"""
Generate a clean occupancy grid map from the Gazebo world file geometry.
Based on disaster_building.world wall positions.

Building: 12m x 10m (X: -6 to 6, Y: -5 to 5)
Map resolution: 0.05 m/pixel
Map origin: (-6.49, -6.49)
"""
import numpy as np
import struct

# Map parameters (match existing disaster_map.yaml)
RESOLUTION = 0.05  # m/pixel
ORIGIN_X = -6.49
ORIGIN_Y = -6.49
WIDTH = 267   # pixels (13.35m)
HEIGHT = 230  # pixels (11.5m)

# Pixel values
FREE = 254
OCCUPIED = 0
UNKNOWN = 205

def world_to_pixel(x, y):
    """Convert world coordinates to pixel (col, row)."""
    col = int(round((x - ORIGIN_X) / RESOLUTION))
    row = (HEIGHT - 1) - int(round((y - ORIGIN_Y) / RESOLUTION))
    return col, row

def draw_wall(grid, cx, cy, sx, sy):
    """Draw a wall given center (cx,cy) and size (sx,sy) in world coords."""
    x_min = cx - sx / 2.0
    x_max = cx + sx / 2.0
    y_min = cy - sy / 2.0
    y_max = cy + sy / 2.0

    col_min, row_max = world_to_pixel(x_min, y_min)
    col_max, row_min = world_to_pixel(x_max, y_max)

    # Clamp
    col_min = max(0, col_min)
    col_max = min(WIDTH - 1, col_max)
    row_min = max(0, row_min)
    row_max = min(HEIGHT - 1, row_max)

    grid[row_min:row_max + 1, col_min:col_max + 1] = OCCUPIED

def draw_obstacle(grid, cx, cy, sx, sy):
    """Draw a static obstacle (same as wall but semantically different)."""
    draw_wall(grid, cx, cy, sx, sy)

def main():
    # Initialize: everything unknown
    grid = np.full((HEIGHT, WIDTH), UNKNOWN, dtype=np.uint8)

    # --- Mark free space ---
    # Inside the building: X=-6 to 6, Y=-5 to 5
    c1, r1 = world_to_pixel(-5.9, -4.9)
    c2, r2 = world_to_pixel(5.9, 4.9)
    r_min, r_max = min(r1, r2), max(r1, r2)
    c_min, c_max = min(c1, c2), max(c1, c2)
    grid[r_min:r_max + 1, c_min:c_max + 1] = FREE

    # Entrance approach area: X=-1.5 to 1.5, Y=-6.4 to -5.0
    c1, r1 = world_to_pixel(-1.5, -6.4)
    c2, r2 = world_to_pixel(1.5, -4.9)
    r_min, r_max = min(r1, r2), max(r1, r2)
    c_min, c_max = min(c1, c2), max(c1, c2)
    grid[r_min:r_max + 1, c_min:c_max + 1] = FREE

    # === OUTER WALLS ===
    # South wall left: center (-3.5, -5.0), size (5.0, 0.15)
    draw_wall(grid, -3.5, -5.0, 5.0, 0.15)
    # South wall right: center (3.5, -5.0), size (5.0, 0.15)
    draw_wall(grid, 3.5, -5.0, 5.0, 0.15)
    # Entrance gap: X = -1.0 to 1.0 (2m gap)

    # North wall: center (0.0, 5.0), size (12.0, 0.15)
    draw_wall(grid, 0.0, 5.0, 12.0, 0.15)
    # West wall: center (-6.0, 0.0), size (0.15, 10.0)
    draw_wall(grid, -6.0, 0.0, 0.15, 10.0)
    # East wall: center (6.0, 0.0), size (0.15, 10.0)
    draw_wall(grid, 6.0, 0.0, 0.15, 10.0)

    # === INNER WALLS ===
    # Office A west wall lower: center (-2.0, -3.9), size (0.15, 2.0)
    draw_wall(grid, -2.0, -3.9, 0.15, 2.0)
    # Office A west wall upper: center (-2.0, -0.2), size (0.15, 2.2)
    draw_wall(grid, -2.0, -0.2, 0.15, 2.2)
    # Door gap: Y = -2.9 to -1.3

    # Office A north wall: center (-4.0, 1.0), size (4.0, 0.15)
    draw_wall(grid, -4.0, 1.0, 4.0, 0.15)

    # Corridor bend left: center (-0.7, 1.0), size (2.4, 0.15)
    draw_wall(grid, -0.7, 1.0, 2.4, 0.15)
    # Corridor bend right: center (2.0, 1.0), size (0.6, 0.15)
    draw_wall(grid, 2.0, 1.0, 0.6, 0.15)
    # Server room door gap: X = 0.5 to 1.7

    # Server room east wall: center (2.3, 2.25), size (0.15, 2.5)
    draw_wall(grid, 2.3, 2.25, 0.15, 2.5)
    # Server room north wall: center (1.3, 3.5), size (2.0, 0.15)
    draw_wall(grid, 1.3, 3.5, 2.0, 0.15)

    # Office B south left: center (2.9, 1.0), size (1.0, 0.15)
    draw_wall(grid, 2.9, 1.0, 1.0, 0.15)
    # Office B south right: center (5.35, 1.0), size (1.1, 0.15)
    draw_wall(grid, 5.35, 1.0, 1.1, 0.15)
    # Office B door gap: X = 3.4 to 4.8

    # === STATIC OBSTACLES (debris) ===
    # Ceiling collapse in corridor
    draw_obstacle(grid, 0.0, -3.5, 1.0, 0.8)
    # Fallen pipe (simplified as axis-aligned)
    draw_obstacle(grid, 1.5, -1.5, 1.5, 0.15)
    # Collapsed desk in Office A
    draw_obstacle(grid, -4.0, -1.5, 1.2, 0.6)
    # Fallen chair in Office A
    draw_obstacle(grid, -3.0, -3.0, 0.5, 0.5)
    # Wall debris in Office A
    draw_obstacle(grid, -5.0, -4.0, 0.7, 0.5)
    # Fallen cabinet in Office B
    draw_obstacle(grid, 5.0, 3.0, 0.4, 1.2)
    # Floor debris in Office B
    draw_obstacle(grid, 3.5, 3.5, 0.5, 0.3)
    # Fallen server rack
    draw_obstacle(grid, 1.3, 2.5, 0.5, 0.8)

    # === Write PGM (P5 binary format) ===
    output_path = "src/talos_bringup/maps/disaster_map.pgm"
    with open(output_path, 'wb') as f:
        header = f"P5\n{WIDTH} {HEIGHT}\n255\n"
        f.write(header.encode('ascii'))
        f.write(grid.tobytes())

    print(f"Clean map written to {output_path}")
    print(f"  Size: {WIDTH}x{HEIGHT} pixels")
    print(f"  Resolution: {RESOLUTION} m/pixel")
    print(f"  Origin: ({ORIGIN_X}, {ORIGIN_Y})")

    # Also copy to map/ directory
    import shutil
    shutil.copy(output_path, "map/disaster_map.pgm")
    print(f"  Also copied to map/disaster_map.pgm")

if __name__ == "__main__":
    main()
