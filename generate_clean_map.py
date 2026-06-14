#!/usr/bin/env python3
"""
Generate a merged occupancy grid map:
- Clean walls from Gazebo world file geometry
- Interior obstacles from original SLAM map data

Building: 12m x 10m (X: -6 to 6, Y: -5 to 5)
Map resolution: 0.05 m/pixel
Map origin: (-6.49, -6.49)
"""
import numpy as np

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

# Wall thickness buffer in pixels (for masking wall regions)
WALL_BUFFER_PX = 4  # ~20cm buffer around walls

def world_to_pixel(x, y):
    """Convert world coordinates to pixel (col, row)."""
    col = int(round((x - ORIGIN_X) / RESOLUTION))
    row = (HEIGHT - 1) - int(round((y - ORIGIN_Y) / RESOLUTION))
    return col, row

def draw_rect(grid, cx, cy, sx, sy, value=OCCUPIED):
    """Draw a rectangle given center (cx,cy) and size (sx,sy) in world coords."""
    x_min = cx - sx / 2.0
    x_max = cx + sx / 2.0
    y_min = cy - sy / 2.0
    y_max = cy + sy / 2.0

    col_min, row_max = world_to_pixel(x_min, y_min)
    col_max, row_min = world_to_pixel(x_max, y_max)

    col_min = max(0, col_min)
    col_max = min(WIDTH - 1, col_max)
    row_min = max(0, row_min)
    row_max = min(HEIGHT - 1, row_max)

    grid[row_min:row_max + 1, col_min:col_max + 1] = value

def draw_wall(grid, wall_mask, cx, cy, sx, sy):
    """Draw a wall and mark wall region in mask (with buffer)."""
    draw_rect(grid, cx, cy, sx, sy, OCCUPIED)
    # Mark wall buffer zone in mask
    buf = WALL_BUFFER_PX * RESOLUTION
    draw_rect(wall_mask, cx, cy, sx + 2*buf, sy + 2*buf, 1)

def load_pgm(path):
    """Load a PGM P5 file as numpy array."""
    with open(path, 'rb') as f:
        magic = f.readline().strip()
        assert magic == b'P5', f"Expected P5, got {magic}"
        line = f.readline().strip()
        while line.startswith(b'#'):
            line = f.readline().strip()
        w, h = map(int, line.split())
        maxval = int(f.readline().strip())
        data = f.read()
        img = np.frombuffer(data, dtype=np.uint8).reshape((h, w))
    return img

def main():
    # --- Load original SLAM map for obstacle data ---
    slam_map = load_pgm("/tmp/original_slam_map.pgm")
    print(f"Loaded SLAM map: {slam_map.shape}")

    # --- Create clean base map ---
    grid = np.full((HEIGHT, WIDTH), UNKNOWN, dtype=np.uint8)
    wall_mask = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)  # 1 = wall zone

    # --- Mark free space ---
    # Inside the building: X=-6 to 6, Y=-5 to 5
    c1, r1 = world_to_pixel(-5.9, -4.9)
    c2, r2 = world_to_pixel(5.9, 4.9)
    r_min, r_max = min(r1, r2), max(r1, r2)
    c_min, c_max = min(c1, c2), max(c1, c2)
    grid[r_min:r_max + 1, c_min:c_max + 1] = FREE

    # Entrance approach area
    c1, r1 = world_to_pixel(-1.5, -6.4)
    c2, r2 = world_to_pixel(1.5, -4.9)
    r_min, r_max = min(r1, r2), max(r1, r2)
    c_min, c_max = min(c1, c2), max(c1, c2)
    grid[r_min:r_max + 1, c_min:c_max + 1] = FREE

    # === OUTER WALLS ===
    draw_wall(grid, wall_mask, -3.5, -5.0, 5.0, 0.15)   # South wall left
    draw_wall(grid, wall_mask, 3.5, -5.0, 5.0, 0.15)     # South wall right
    draw_wall(grid, wall_mask, 0.0, 5.0, 12.0, 0.15)     # North wall
    draw_wall(grid, wall_mask, -6.0, 0.0, 0.15, 10.0)    # West wall
    draw_wall(grid, wall_mask, 6.0, 0.0, 0.15, 10.0)     # East wall

    # === INNER WALLS ===
    draw_wall(grid, wall_mask, -2.0, -3.9, 0.15, 2.0)    # Office A west wall lower
    draw_wall(grid, wall_mask, -2.0, -0.2, 0.15, 2.2)    # Office A west wall upper
    draw_wall(grid, wall_mask, -4.0, 1.0, 4.0, 0.15)     # Office A north wall
    draw_wall(grid, wall_mask, -0.7, 1.0, 2.4, 0.15)     # Corridor bend left
    draw_wall(grid, wall_mask, 2.0, 1.0, 0.6, 0.15)      # Corridor bend right
    draw_wall(grid, wall_mask, 2.3, 2.25, 0.15, 2.5)     # Server room east wall
    draw_wall(grid, wall_mask, 1.3, 3.5, 2.0, 0.15)      # Server room north wall
    draw_wall(grid, wall_mask, 2.9, 1.0, 1.0, 0.15)      # Office B south left
    draw_wall(grid, wall_mask, 5.35, 1.0, 1.1, 0.15)     # Office B south right

    # === MERGE: overlay SLAM obstacles in non-wall interior areas ===
    # SLAM map: dark pixels (< 80) = occupied, light pixels (> 200) = free
    slam_occupied = slam_map < 80

    # Only apply SLAM obstacles where:
    # 1. Not in wall buffer zone (keep clean walls)
    # 2. The clean map says it's free space (inside building)
    # 3. The SLAM map shows an obstacle
    interior_slam_obstacles = slam_occupied & (wall_mask == 0) & (grid == FREE)

    grid[interior_slam_obstacles] = OCCUPIED
    num_slam_obstacles = np.count_nonzero(interior_slam_obstacles)
    print(f"Merged {num_slam_obstacles} obstacle pixels from SLAM map")

    # === Write PGM (P5 binary format) ===
    output_path = "src/talos_bringup/maps/disaster_map.pgm"
    with open(output_path, 'wb') as f:
        header = f"P5\n{WIDTH} {HEIGHT}\n255\n"
        f.write(header.encode('ascii'))
        f.write(grid.tobytes())

    print(f"Merged map written to {output_path}")
    print(f"  Size: {WIDTH}x{HEIGHT} pixels")
    print(f"  Resolution: {RESOLUTION} m/pixel")
    print(f"  Origin: ({ORIGIN_X}, {ORIGIN_Y})")

    # Also copy to map/ directory
    import shutil
    shutil.copy(output_path, "map/disaster_map.pgm")
    print(f"  Also copied to map/disaster_map.pgm")

if __name__ == "__main__":
    main()
