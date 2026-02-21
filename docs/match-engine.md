# Match Engine

Motor de simulación de partidas RTS estilo StarCraft: BroodWar.

## Estado Actual

**Implementado:**
- Sistema de física (movimiento, colisión, pathfinding)
- Sistema de acciones (Gather, Attack, Move, Hold)
- Sistema de producción de unidades (cola en buildings)
- Replay con deltas JSON
- Tests unitarios para cada sistema
- Ubicación: `src/matches/` dentro del proyecto Django

**Faltante (prioridad alta):**
- Sistema de rendición automática
- Lógica de victoria/derrota (todos los edificios destruidos)
- Guardar replay completo en DB
- Unidad Medic

**Faltante (prioridad media):**
- Más tipos de unidades (SCV, Probe, Drone, Dragoon, Hydra, Mutalisk)
- Sistema de highlights para replay
- Integración con API Django
- Botón "Guardar como Replay" en visualizador de escenarios

**Completado:**
- Sistema de física (movimiento, colisión, pathfinding)
- Sistema de acciones (Gather, Attack, Move, Hold)
- Sistema de producción de unidades (cola en buildings)
- Replay con deltas JSON
- Tests unitarios para cada sistema
- Ubicación: `src/matches/` dentro del proyecto Django
- Sistema de escenarios YAML (`src/matches/scenario.py`)
- Visualizador de escenarios (`scenarios/`)
- Endpoint para cargar y ejecutar escenarios

## Arquitectura

### Archivos Principales

| Archivo | Descripción |
|---------|-------------|
| `engine.py` | Core: Entity, MatchSimulator, SpatialGrid, NavigationGrid |
| `actions.py` | Acciones de unidades: GatherAction, AttackAction, MoveAction, HoldAction |
| `data.py` | Stats de unidades (hp, damage, range, speed, cost, etc.) |
| `utils.py` | Utilidades (Vector2D) |

### Componentes Principales

#### SpatialGrid
Optimiza proximidad para colisiones y targeting. Divide el mapa en celdas.

#### NavigationGrid
Grid de ocupación para pathfinding. Dos capas:
- Estática: edificios y minerales
- Dinámica: unidades

#### Entity
Representa una unidad o edificio. Contiene:
- Stats (hp, damage, range, cooldown, speed)
- Posición y estado
- Acción actual
- Cola de producción

#### MatchSimulator
Maneja la simulación:
- Inicializa entidades
- Loop de ticks
- Genera historial de replay

### Acciones

```python
# Gather - Cosechar minerales
GatherAction(target_patch_id)

# Attack - Atacar unidad
AttackAction(target_id)

# Move - Mover a posición
MoveAction(Vector2D(x, y))

# Hold - Mantener posición y atacar enemigos cercanos
HoldAction()
```

## Unidades Actuales (en data.py)

| Tipo | HP | Dmg | Range | Speed | Cost | Build Time |
|------|-----|-----|-------|-------|------|------------|
| base | 1500 | 0 | 0 | 0 | 400 | 120 |
| worker | 40 | 5 | 0.1 | 1.8 | 50 | 20 |
| marine | 40 | 6 | 4 | 1.8 | 50 | 24 |
| zealot | 160 | 16 | 1.5 | 1.8 | 100 | 40 |
| zergling | 35 | 5 | 1.5 | 2.6 | 25 | 28 |
| mineral_patch | 1500 | 0 | 0 | 0 | 0 | 0 |

**Unidades por implementar:** SCV, Medic, Probe, Drone, Dragoon, Hydra, Mutalisk

## Sistema de Replay

Guarda deltas JSON (no estados completos) para eficiencia.

```python
# Estructura del replay
{
    "tick": 0,
    "map": {"width": 128, "height": 128},
    "entities": [...],  # Estado inicial completo
    "resources": {"p1": 50.0, "p2": 50.0}
}
```

Ticks posteriores solo contienen cambios (deltas).

## Tests Existentes

- `test_combat.py` - Mecánicas de combate
- `test_harvesting.py` - Sistema de minería
- `test_movement.py` - Movimiento de unidades
- `test_navigation.py` - Pathfinding y colisiones
- `test_collision.py` - Detección de colisiones
- `test_production.py` - Producción de unidades
- `test_entity.py` - Entidades individuales
- `test_map_editor.py` - Editor de mapas

## Próximos Pasos para MVP Terran vs Terran

1. Agregar unidad Medic
2. Implementar IA básica funcional
3. Sistema de rendición automática
4. Lógica de victoria/derrota (todos los edificios destruidos)
5. Guardar replay completo

## Arquitectura Recomendada

El engine debería ser un paquete Python independiente (`shakuras-engine`) sin dependencias de Django, consumible desde el proyecto API.
