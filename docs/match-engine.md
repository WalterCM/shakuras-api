# Match Engine

Motor de simulación de partidas RTS estilo StarCraft: BroodWar.

## Arquitectura

### Archivos

| Archivo | Descripción |
|---------|-------------|
| `engine.py` | Core: `Map`, `SpatialGrid`, `NavigationGrid`, `Entity`, `ProductionAI`, `MatchSimulator` |
| `actions.py` | Acciones de unidades: `GatherAction`, `AttackAction`, `MoveAction`, `HoldAction` |
| `data.py` | Stats de unidades (`UNIT_STATS`: hp, damage, range, speed, cost, etc.) |
| `utils.py` | Utilidades (`Vector2D`) |
| `scenario.py` | Cargador y ejecutor de escenarios YAML |
| `loader.py` | Cargador de mapas YAML desde `maps/`, con validación |
| `models.py` | Modelos Django: `Match`, `MatchParticipant`, `Replay`, `Tournament` |
| `views.py` | API endpoints y vistas HTML (visualizadores, editor) |
| `urls.py` | Rutas de la app |

### Componentes del Engine

#### Map
Almacena datos estáticos del mapa: dimensiones, spawn points, minerales y terreno.

#### SpatialGrid
Optimiza lookups de proximidad para colisiones y targeting. Divide el mapa en celdas de 8×8.

#### NavigationGrid
Grid de ocupación para pathfinding. Dos capas:
- **Estática**: edificios y minerales (no cambia durante la partida)
- **Dinámica**: unidades (se recalcula cada tick)

#### Entity
Representa una unidad o edificio. Contiene:
- Stats (hp, damage, range, cooldown, speed, radius, width, height)
- Posición (`Vector2D`) y estado
- Acción actual (`Action`)
- Cola de producción (para buildings)
- Sistema de movimiento con pathfinding (ver sección dedicada)

#### ProductionAI
IA simple automática por jugador:
- Produce workers cuando hay recursos disponibles (≥50 minerals)
- Reasigna workers idle al mineral patch más cercano

#### MatchSimulator
Orquesta la simulación. Separa configuración de ejecución:
- `setup_match()` — Inicializa entidades desde el mapa (minerals, bases, workers iniciales). Para partidas normales.
- `add_entity(entity)` — Agrega una entidad manualmente. Para escenarios y tests.
- `triggers` — Dict de `tick → acciones` que se ejecutan durante la simulación.
- `simulate()` — Loop de ticks: triggers → AI update → grids update → entity update → delta recording. Genera historial de replay como deltas JSON.

Tanto las partidas normales como los escenarios usan el mismo `simulate()`. La diferencia es cómo se configura el simulador antes de llamarlo.

### Acciones

```python
# Gather - Cosechar minerales (ciclo: ir al patch → minar → volver a base → repetir)
GatherAction(target_patch_id)

# Attack - Atacar unidad (se mueve hacia el target si está fuera de rango)
AttackAction(target_id)

# Move - Mover a posición
MoveAction(Vector2D(x, y))

# Hold - Mantener posición y atacar enemigos cercanos
HoldAction()
```

### Sistema de Movimiento y Pathfinding

El movimiento de entidades (`Entity.move_towards()`) tiene varias capas:

1. **Movimiento directo**: si no hay obstáculo adelante, avanza hacia el destino
2. **Gap detection** (`find_gap()`): ray casting hacia el destino + búsqueda en grid 20×20 para encontrar huecos en paredes
3. **Wall sliding** (`slide_logic()`): si no hay gap, la unidad se desliza a lo largo del obstáculo eligiendo la tangente con más espacio libre
4. **Ghost mode** (`is_stuck_check()`): si la unidad no se ha movido significativamente en 100 ticks, se activan 20 ticks sin colisión para escapar
5. **Soft repulsion** (`_apply_repulsion()`): empuje suave entre unidades cercanas para evitar superposición
6. **Worker ghosting**: workers cosechando ignoran colisión con buildings y otros gatherers para evitar gridlocks

## Unidades (en `data.py`)

| Tipo | HP | Dmg | Range | Speed | Cost | Build Time | Tamaño |
|------|-----|-----|-------|-------|------|------------|--------|
| `base` | 1500 | 0 | 0 | 0 | 400 | 120 | 4×3 |
| `worker` | 40 | 5 | 0.1 | 1.8 | 50 | 20 | 1×1 |
| `marine` | 40 | 6 | 4 | 1.8 | 50 | 24 | 1×1 |
| `zealot` | 160 | 16 | 1.5 | 1.8 | 100 | 40 | 1×1 |
| `zergling` | 35 | 5 | 1.5 | 2.6 | 25 | 28 | 1×1 |
| `mineral_patch` | 1500 | 0 | 0 | 0 | 0 | 0 | 2×1 |

Las unidades no están asociadas a razas en el engine. El modelo `Player` tiene raza, pero el engine no la usa para restringir qué unidades puede producir cada jugador.

## Sistema de Replay

Guarda deltas JSON (no estados completos) para eficiencia.

Tick 0 contiene el estado inicial completo:
```json
{
    "tick": 0,
    "map": {"width": 64, "height": 64},
    "entities": [...],
    "resources": {"p1": 50.0, "p2": 50.0}
}
```

Ticks posteriores solo contienen los campos que cambiaron:
```json
{
    "tick": 5,
    "entities": [{"id": "a1b2", "x": 12.5, "y": 10.3}],
    "resources": {"p1": 58.0}
}
```

## Sistema de Escenarios YAML

Permite crear escenarios de prueba para verificar el motor sin base de datos.

### Ubicación
- `scenarios/` — Archivos YAML de escenarios
- `src/matches/scenario.py` — Módulo loader y ejecutor
- `src/matches/templates/matches/scenario_visualizer.html` — Visualizador

### Formato YAML

```yaml
name: "Wall 1 gap center"
description: "Worker trying to cross mineral wall with 1 gap at center"

width: 64
height: 64

entities:
  - id: worker1
    type: worker
    owner: p1
    x: 10
    y: 15
  - id: m1
    type: mineral_patch
    owner: neutral
    x: 30
    y: 5

triggers:
  - tick: 0
    entity: worker1
    action:
      type: move
      target: {x: 50, y: 15}

config:
  max_ticks: 100
```

Los escenarios son self-contained: definen sus propias dimensiones y todas sus entidades. No referencian mapas externos.

`execute_scenario()` configura un `MatchSimulator` (entidades, triggers, sin AI) y delega a `sim.simulate()` — usa el mismo loop que las partidas normales.

### Escenarios Existentes
- `scenarios/navigation/wall_0_gaps.yaml` — Pared sólida (sin salida)
- `scenarios/navigation/wall_1_gap_center.yaml` — Pared con 1 gap al centro
- `scenarios/navigation/wall_1_gap_offset.yaml` — Pared con 1 gap desplazado
- `scenarios/navigation/wall_2_gaps.yaml` — Pared con 2 gaps
- `scenarios/navigation/l_shape.yaml` — Obstáculo en forma de L

## Sistema de Mapas YAML

Los mapas se almacenan como archivos YAML en `maps/`. Se cargan con `loader.py`.

### Formato
```yaml
name: "Blood Bath"
description: "Classic 2-player map with mineral patches"
width: 64
height: 64

spawn_points:
  p1: {x: 2, y: 6}
  p2: {x: 53, y: 55}

entities:
  - id: m1
    type: mineral_patch
    owner: neutral
    x: 0
    y: 2
```

### Diferencia entre Mapas y Escenarios
- **Mapas** (`maps/`): Definen layouts para partidas reales. Tienen `spawn_points` para las bases.
- **Escenarios** (`scenarios/`): Para testing del engine. Tienen `triggers` para asignar acciones a entidades en ticks específicos. No necesitan spawn_points.

## Tests

| Archivo | Descripción |
|---------|-------------|
| `test_navigation.py` | Pathfinding, obstáculos, gaps, walls (10 tests) |
| `test_api.py` | API REST, endpoints de mapas y escenarios |
| `test_harvesting.py` | Sistema de minería y resource contention |
| `test_collision.py` | Detección de colisiones y repulsión |
| `test_combat.py` | Mecánicas de combate |
| `test_movement.py` | Movimiento de unidades |
| `test_map_editor.py` | Editor de mapas |
| `test_production.py` | Producción de unidades |
| `test_entity.py` | Entidades individuales |
