import heapq
import math
from .utils import Vector2D

class AStarPathfinder:
    def __init__(self, nav_grid):
        self.grid = nav_grid
        self.width = nav_grid.width
        self.height = nav_grid.height

    def find_path(self, start_pos, end_pos, entity=None):
        """
        Finds a path from start_pos to end_pos using A* on the tile grid.
        Returns a list of Vector2D waypoints.
        """
        start_tile = (int(start_pos.x), int(start_pos.y))
        end_tile = (int(end_pos.x), int(end_pos.y))

        if start_tile == end_tile:
            return [end_pos]

        # Priority queue for A*: (priority, current_tile)
        # priority = g_score + heuristic
        open_set = []
        heapq.heappush(open_set, (0, start_tile))
        
        came_from = {}
        g_score = {start_tile: 0}
        
        # Heuristic: Euclidean distance
        def heuristic(a, b):
            return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end_tile:
                return self._reconstruct_path(came_from, current, end_pos)

            # Check 8 neighbors
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    neighbor = (current[0] + dx, current[1] + dy)
                    
                    if not (0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height):
                        continue
                    
                    # Check if neighbor is blocked
                    # We use is_area_blocked but only for the tile center to keep A* simple
                    if self.grid.static_grid[neighbor[0]][neighbor[1]]:
                        continue

                    # Diagonal movement check (prevent cutting corners of solid blocks)
                    if dx != 0 and dy != 0:
                        if self.grid.static_grid[current[0] + dx][current[1]] or \
                           self.grid.static_grid[current[0]][current[1] + dy]:
                            continue

                    # Tentative g_score
                    # Cost is 1.0 for orthogonal, 1.414 for diagonal
                    move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
                    tentative_g_score = g_score[current] + move_cost
                    
                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        f_score = tentative_g_score + heuristic(neighbor, end_tile)
                        heapq.heappush(open_set, (f_score, neighbor))

        # No path found
        return []

    def _reconstruct_path(self, came_from, current, final_pos):
        path = []
        # Start with the exact final position to ensure precision at the destination
        path.append(final_pos)
        
        while current in came_from:
            current = came_from[current]
            # Convert tile coords to tile centers
            path.append(Vector2D(current[0] + 0.5, current[1] + 0.5))
        
        path.reverse()
        # Remove the first waypoint if it's too close to the current start position
        # (This avoids the unit trying to walk backwards to a tile center)
        return path

    def smooth_path(self, path, entity, game_state):
        """
        Simplifies the path by removing redundant waypoints (String Pulling).
        If we can walk from A to C in a straight line without hitting obstacles, remove B.
        """
        if len(path) <= 2:
            return path
            
        smoothed = [path[0]]
        current_idx = 0
        
        while current_idx < len(path) - 1:
            # Try to find the furthest waypoint we can see
            furthest_visible = current_idx + 1
            for next_idx in range(current_idx + 2, len(path)):
                if self._is_line_clear(path[current_idx], path[next_idx], entity, game_state):
                    furthest_visible = next_idx
                else:
                    break
            
            smoothed.append(path[furthest_visible])
            current_idx = furthest_visible
            
        return smoothed

    def _is_line_clear(self, p1, p2, entity, game_state):
        """Checks if a straight line between two points is clear for the entity."""
        diff = p2 - p1
        dist = diff.length()
        if dist < 0.1:
            return True
            
        direction = diff.normalize()
        
        # Step along the line and check for collisions
        # Use a step size related to tile size to ensure no wall is missed
        step = 0.5
        d = step
        while d < dist:
            check_pos = p1 + direction * d
            if game_state.nav_grid.is_area_blocked(check_pos.x, check_pos.y, entity.width, entity.height, check_dynamic=False, entity=entity):
                return False
            d += step
            
        return True
