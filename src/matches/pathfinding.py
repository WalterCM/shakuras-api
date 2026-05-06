import heapq
import math
from .utils import Vector2D

class AStarPathfinder:
    def __init__(self, nav_grid):
        self.grid = nav_grid
        self.width = nav_grid.width
        self.height = nav_grid.height

    def find_path(self, start_pos, end_pos, entity=None, game_state=None):
        """
        Finds a path from start_pos to end_pos using A* on the tile grid.
        Returns a list of Vector2D waypoints.
        """
        # Use math.floor for more consistent tile mapping
        start_tile = (math.floor(start_pos.x), math.floor(start_pos.y))
        end_tile = (math.floor(end_pos.x), math.floor(end_pos.y))

        if start_tile == end_tile:
            return [end_pos]

        # Priority queue for A*: (f_score, h_score, current_tile)
        # We include h_score as a tie-breaker to favor nodes closer to the goal
        # when f_score is equal.
        open_set = []
        
        # Heuristic: Octile distance for 8-neighbor grid
        def heuristic(a, b):
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            # Cost of diagonal is sqrt(2) approx 1.414
            # Cost of straight is 1.0
            return (dx + dy) + (1.414 - 2) * min(dx, dy)

        h_start = heuristic(start_tile, end_tile)
        heapq.heappush(open_set, (h_start, h_start, start_tile))
        
        came_from = {}
        g_score = {start_tile: 0}
        
        # LOG: Incluimos el ID y un RADAR visual de 5x5 alrededor del inicio
        
        # AJUSTE: Si el destino está bloqueado, buscar la celda libre más cercana al DESTINO
        if self.grid.static_grid[end_tile[0]][end_tile[1]]:
            best_alt = None
            min_dist_sq = float('inf')
            
            # Buscamos en anillos concéntricos
            for r in range(1, 5):
                for dx in range(-r, r+1):
                    for dy in range(-r, r+1):
                        # Solo miramos el perímetro del cuadrado de radio r
                        if abs(dx) < r and abs(dy) < r: continue
                        
                        alt_tile = (end_tile[0] + dx, end_tile[1] + dy)
                        if 0 <= alt_tile[0] < self.width and 0 <= alt_tile[1] < self.height:
                            if not self.grid.static_grid[alt_tile[0]][alt_tile[1]]:
                                # Distancia al DESTINO ORIGINAL (estable, no depende del SCV)
                                dist_sq = (alt_tile[0] + 0.5 - end_pos.x)**2 + (alt_tile[1] + 0.5 - end_pos.y)**2
                                if dist_sq < min_dist_sq:
                                    min_dist_sq = dist_sq
                                    best_alt = alt_tile
                if best_alt: break # Si encontramos opciones en este radio, nos quedamos con la mejor
            
            if best_alt:
                end_tile = best_alt



        # Si ya estamos en la celda de destino, no hace falta calcular nada
        if start_tile == end_tile:
            return []

        while open_set:
            f, h, current = heapq.heappop(open_set)

            if current == end_tile:
                path = self._reconstruct_path(came_from, current, end_pos, start_pos)
                return path

            # Check 8 neighbors
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    neighbor = (current[0] + dx, current[1] + dy)
                    
                    if not (0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height):
                        continue
                    
                    # Check if neighbor is blocked
                    static_id = self.grid.static_grid[neighbor[0]][neighbor[1]]
                    if static_id:
                        # Pathfinding should generally AVOID minerals/buildings 
                        # but we need to allow the END tile to be reached.
                        # We only ignore if it's the target entity we are looking for.
                        if entity and static_id == entity.id:
                            pass
                        else:
                            continue # Blocked
                    
                    if dx != 0 and dy != 0:
                        # Diagonal movement check
                        if self.grid.static_grid[current[0] + dx][current[1]] or \
                           self.grid.static_grid[current[0]][current[1] + dy]:
                            continue

                    move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
                    tentative_g_score = g_score[current] + move_cost
                    
                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        h_neighbor = heuristic(neighbor, end_tile)
                        
                        # Weight h by 0.8 to make it more like Dijkstra (explores more)
                        f_score = tentative_g_score + (h_neighbor * 0.8)
                        heapq.heappush(open_set, (f_score, h_neighbor, neighbor))

        # No path found
        return []

    def _reconstruct_path(self, came_from, current, final_pos, start_pos):
        path = []
        # Start with the exact final position to ensure precision at the destination
        path.append(final_pos)
        
        while current in came_from:
            current = came_from[current]
            # Convert tile coords to tile centers
            path.append(Vector2D(current[0] + 0.5, current[1] + 0.5))
        
        path.reverse()
        
        # Override the first waypoint to be the EXACT starting position
        # This makes the path start under the unit and allows String Pulling
        # to skip the 'centering' waypoint if there's a clear line of sight.
        if len(path) > 0:
            path[0] = start_pos
                
        return path

    def smooth_path(self, path, entity, game_state, ignore_static_id=None):
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
                if self._is_line_clear(path[current_idx], path[next_idx], entity, game_state, ignore_static_id):
                    furthest_visible = next_idx
                else:
                    break
            
            smoothed.append(path[furthest_visible])
            current_idx = furthest_visible
            
        return smoothed

    def _is_line_clear(self, p1, p2, entity, game_state, ignore_static_id=None):
        """Checks if a straight line between two points is clear for the entity."""
        diff = p2 - p1
        dist = diff.length()
        if dist < 0.1:
            return True
            
        direction = diff.normalize()
        
        # Step along the line and check for collisions
        # Use a very small step size (0.1) to ensure no corners or narrow walls are skipped
        step = 0.1
        # Use slightly tighter leniency for smoothing (0.10) than for movement (0.15)
        # to prevent "skimming" through corner pixels of buildings.
        from .actions import GatherAction
        eps = 0.10 if isinstance(entity.action, GatherAction) else 0.05
        
        d = step
        while d < dist:
            check_pos = p1 + direction * d
            if game_state.nav_grid.is_area_blocked(check_pos.x, check_pos.y, entity.width, entity.height, check_dynamic=False, entity=entity, ignore_static_id=ignore_static_id, eps=eps):
                return False
            d += step
            
        return True
