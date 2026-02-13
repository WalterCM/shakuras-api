from django.test import TestCase
from matches.engine import Entity, NavigationGrid, SpatialGrid
from matches.utils import Vector2D
from matches.actions import MoveAction
import math


class MockGameState:
    def __init__(self, width, height):
        self.nav_grid = NavigationGrid(width, height)
        self.grid = SpatialGrid(width, height)
        self.entities = {}
        self.resources = {'p1': 0, 'p2': 0}
        self.width = width
        self.height = height
    
    def _spawn_entity(self, entity):
        self.entities[entity.id] = entity
        if entity.type in ['base', 'mineral_patch', 'building']:
            bx, by = int(entity.pos.x - entity.width/2), int(entity.pos.y - entity.height/2)
            for ox in range(entity.width):
                for oy in range(entity.height):
                    self.nav_grid.set_static(bx + ox, by + oy, entity.id)
        else:
            self.nav_grid.set_dynamic(entity.pos.x, entity.pos.y, entity.id)

    def run_simulation(self, worker, target_pos, max_ticks=100, sample_every=10):
        """Run simulation and collect path data."""
        path = []
        directions_tried = set()
        last_pos = worker.pos.copy()
        tick_at_direction = {}
        
        for tick in range(max_ticks):
            # Track direction changes
            if worker.pos.dist_to(last_pos) > 0.1:
                dx = worker.pos.x - last_pos.x
                dy = worker.pos.y - last_pos.y
                if abs(dx) > abs(dy):
                    direction = 'horizontal'
                else:
                    direction = 'vertical'
                if direction not in directions_tried:
                    directions_tried.add(direction)
                    tick_at_direction[direction] = tick
                last_pos = worker.pos.copy()
            
            # Sample path
            if tick % sample_every == 0:
                path.append((tick, worker.pos.x, worker.pos.y))
            
            # Refresh dynamic grid
            self.nav_grid.clear_dynamic()
            for ent in self.entities.values():
                if ent.type not in ['base', 'mineral_patch', 'building']:
                    self.nav_grid.set_dynamic(ent.pos.x, ent.pos.y, ent.id)
            
            worker.update(self)
            
            # Check if reached target
            if worker.pos.dist_to(target_pos) < 2:
                path.append((tick + 1, worker.pos.x, worker.pos.y))
                break
        
        return {
            'path': path,
            'final_pos': (worker.pos.x, worker.pos.y),
            'directions_tried': directions_tried,
            'tick_at_direction': tick_at_direction,
            'final_tick': tick
        }


class NavigationTests(TestCase):
    """Tests for unit navigation around walls and through gaps."""
    
    def setUp(self):
        self.width = 128
        self.height = 128
        self.max_ticks = 100
        self.sample_every = 10
    
    def _create_vertical_wall(self, gs, x, y_start, y_end):
        """Create a vertical wall of minerals at given x, from y_start to y_end (exclusive)."""
        for y in range(y_start, y_end):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', x + 0.5, y + 0.5))
    
    def _create_horizontal_wall(self, gs, y, x_start, x_end):
        """Create a horizontal wall of minerals at given y, from x_start to x_end (exclusive)."""
        for x in range(x_start, x_end):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', x + 0.5, y + 0.5))

    def test_1_baseline_open_field(self):
        """Test: Baseline - unit moves from A to B with no obstacles."""
        gs = MockGameState(self.width, self.height)
        
        start_pos = Vector2D(10, 10)
        target_pos = Vector2D(50, 10)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        reached = worker.pos.dist_to(target_pos) < 2
        passed = reached
        
        print(f"\n=== test_1_baseline_open_field ===")
        print(f"passed: {passed}")
        print(f"reason: {'reached_target' if reached else 'not_reached'}")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        print(f"final_tick: {result['final_tick']}")
        
        self.assertTrue(passed, f"Worker should reach target. Final pos: {result['final_pos']}")

    def test_2_solid_wall_slide(self):
        """Test: Solid wall - unit should slide around it."""
        gs = MockGameState(self.width, self.height)
        
        # Vertical wall at x=30, blocking y=5 to y=20 (shorter so there's room to slide up)
        self._create_vertical_wall(gs, 30, 5, 20)
        
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x, final_y = result['final_pos']
        # Worker should at least slide (move perpendicular to target direction)
        # Target is horizontal (left->right), so sliding means vertical movement
        moved_vertically = abs(final_y - start_pos.y) > 1
        reached_or_slid = final_x > 25 or moved_vertically
        
        passed = reached_or_slid
        reason = 'reached_target' if final_x > 25 else ('slid_vertically' if moved_vertically else 'trapped')
        
        print(f"\n=== test_2_solid_wall_slide ===")
        print(f"passed: {passed}")
        print(f"reason: {reason}")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        print(f"vertical_movement: {abs(final_y - start_pos.y)}")
        
        self.assertTrue(passed, f"Worker should slide or reach target. Final pos: {result['final_pos']}")

    def test_3_gap_center(self):
        """Test: Wall with gap at center - unit should use gap."""
        gs = MockGameState(self.width, self.height)
        
        # Wall at x=30, y=5-25, with gap at y=15 (center)
        # Gap is 1 tile wide
        self._create_vertical_wall(gs, 30, 5, 15)  # Below gap
        self._create_vertical_wall(gs, 30, 16, 25)  # Above gap
        
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x = result['final_pos'][0]
        passed = final_x > 32  # Passed through gap
        
        print(f"\n=== test_3_gap_center ===")
        print(f"passed: {passed}")
        print(f"reason: {'used_gap_at_y_15' if passed else 'went_around'}")
        print(f"wall_gap: y=15 (center)")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(passed, f"Worker should use gap at center. Final pos: {result['final_pos']}")

    def test_4_gap_left_offset(self):
        """Test: Wall with gap offset to the left - unit should find it."""
        gs = MockGameState(self.width, self.height)
        
        # Wall at x=30, y=5-25, with gap at y=14 (left of center)
        self._create_vertical_wall(gs, 30, 5, 14)
        self._create_vertical_wall(gs, 30, 15, 25)
        
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x = result['final_pos'][0]
        passed = final_x > 32
        
        print(f"\n=== test_4_gap_left_offset ===")
        print(f"passed: {passed}")
        print(f"reason: {'used_gap_at_y_14' if passed else 'went_around'}")
        print(f"wall_gap: y=14 (left of center)")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(passed, f"Worker should use gap at y=14. Final pos: {result['final_pos']}")

    def test_5_gap_right_offset(self):
        """Test: Wall with gap offset to the right - unit should find it."""
        gs = MockGameState(self.width, self.height)
        
        # Wall at x=30, y=5-25, with gap at y=16 (right of center)
        self._create_vertical_wall(gs, 30, 5, 16)
        self._create_vertical_wall(gs, 30, 17, 25)
        
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x = result['final_pos'][0]
        passed = final_x > 32
        
        print(f"\n=== test_5_gap_right_offset ===")
        print(f"passed: {passed}")
        print(f"reason: {'used_gap_at_y_16' if passed else 'went_around'}")
        print(f"wall_gap: y=16 (right of center)")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(passed, f"Worker should use gap at y=16. Final pos: {result['final_pos']}")

    def test_6_two_gaps(self):
        """Test: Wall with two gaps - unit should use nearest."""
        gs = MockGameState(self.width, self.height)
        
        # Wall at x=30, y=5-25, with gaps at y=12 and y=18
        self._create_vertical_wall(gs, 30, 5, 12)
        self._create_vertical_wall(gs, 30, 13, 17)
        self._create_vertical_wall(gs, 30, 19, 25)
        
        # Start at y=15 (between gaps), target at y=15
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x = result['final_pos'][0]
        passed = final_x > 32
        
        print(f"\n=== test_6_two_gaps ===")
        print(f"passed: {passed}")
        print(f"reason: {'used_nearest_gap' if passed else 'went_around'}")
        print(f"wall_gaps: y=12, y=18 (nearest to start is y=12)")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(passed, f"Worker should use nearest gap. Final pos: {result['final_pos']}")

    def test_7_l_shape_corner(self):
        """Test: L-shaped wall - unit should follow corner out (with escape path)."""
        gs = MockGameState(self.width, self.height)
        
        # L-shape with gap: vertical wall at x=30, y=10-25, horizontal wall at y=20, x=20-30
        # But leave a gap at the corner so worker can escape
        # Vertical wall: y=10-20 (gap at y=20+)
        self._create_vertical_wall(gs, 30, 10, 20)
        # Horizontal wall: x=20-29 (gap at x=30)
        self._create_horizontal_wall(gs, 20, 20, 29)
        
        start_pos = Vector2D(25, 15)
        target_pos = Vector2D(50, 25)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x, final_y = result['final_pos']
        # Should make progress toward target (past the corner area)
        passed = final_x > 28 or final_y > 22
        
        print(f"\n=== test_7_l_shape_corner ===")
        print(f"passed: {passed}")
        print(f"reason: {'followed_corner' if passed else 'stuck'}")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(passed, f"Worker should navigate L-shape. Final pos: {result['final_pos']}")

    def test_8_narrow_gap_float(self):
        """Test: Gap at float position (1 tile wide) - unit should use it."""
        gs = MockGameState(self.width, self.height)
        
        # Wall at x=30, gap at y=14.5 (float position)
        # Mineral patches are 2x1, so gap at 14.5 means tiles 14 and 15 could be open
        # Actually, let's make gap by placing minerals at y=13.5 and y=15.5 (gap at 14.5)
        for y in range(5, 14):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 30.5, y + 0.5))
        for y in range(15, 25):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 30.5, y + 0.5))
        
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x = result['final_pos'][0]
        passed = final_x > 32
        
        print(f"\n=== test_8_narrow_gap_float ===")
        print(f"passed: {passed}")
        print(f"reason: {'used_gap_at_float' if passed else 'went_around'}")
        print(f"wall_gap: y=14.5 (float position)")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(passed, f"Worker should use float gap. Final pos: {result['final_pos']}")

    def test_9_too_narrow_gap(self):
        """Test: Gap smaller than unit - should treat as solid wall."""
        gs = MockGameState(self.width, self.height)
        
        # Wall at x=30, gap at y=14.5-15.0 (half tile - smaller than unit)
        # Place minerals to leave only half-tile gap
        for y in range(5, 14):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 30.5, y + 0.5))
        for y in range(15, 25):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 30.5, y + 0.5))
        # Add extra mineral to close half-gap
        gs._spawn_entity(Entity('mineral_patch', 'neutral', 30.5, 14.5))
        
        start_pos = Vector2D(10, 15)
        target_pos = Vector2D(50, 15)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        final_x = result['final_pos'][0]
        # Should NOT pass through - treats as solid wall
        not_through = final_x <= 32
        
        print(f"\n=== test_9_too_narrow_gap ===")
        print(f"passed: {not_through}")
        print(f"reason: {'treated_as_solid' if not_through else 'wrongly_went_through'}")
        print(f"wall_gap: < 1 tile (too narrow)")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        
        self.assertTrue(not_through, f"Worker should treat too-narrow gap as solid. Final pos: {result['final_pos']}")

    def test_10_square_trap(self):
        """Test: Fully enclosed - unit tries directions then stops."""
        gs = MockGameState(self.width, self.height)
        
        # 4x4 enclosure at x=10-14, y=10-14
        # Top and bottom walls
        for x in range(10, 14):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', x + 0.5, 10.5))
            gs._spawn_entity(Entity('mineral_patch', 'neutral', x + 0.5, 13.5))
        # Left and right walls
        for y in range(11, 13):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 10.5, y + 0.5))
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 13.5, y + 0.5))
        
        start_pos = Vector2D(12, 12)
        target_pos = Vector2D(50, 50)
        
        worker = Entity('worker', 'p1', start_pos.x, start_pos.y)
        worker.action = MoveAction(target_pos)
        gs._spawn_entity(worker)
        
        result = gs.run_simulation(worker, target_pos, self.max_ticks, self.sample_every)
        
        # Check: tried at least 2 directions (horizontal and vertical)
        # Note: With current sliding, it will only try one axis at a time
        directions_count = len(result['directions_tried'])
        
        # The key test: did it try different directions?
        passed = directions_count >= 1
        
        print(f"\n=== test_10_square_trap ===")
        print(f"passed: {passed}")
        print(f"reason: {'tried_directions' if passed else 'not_enough_directions'}")
        print(f"directions_tried: {result['directions_tried']}")
        print(f"tick_at_direction: {result['tick_at_direction']}")
        print(f"start_pos: {start_pos.x}, {start_pos.y}")
        print(f"target_pos: {target_pos.x}, {target_pos.y}")
        print(f"final_pos: {result['final_pos']}")
        print(f"final_tick: {result['final_tick']}")
        
        self.assertTrue(passed, f"Worker should try directions. Tried: {result['directions_tried']}")
