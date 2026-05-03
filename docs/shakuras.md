# Shakuras - Manager de eSports de StarCraft: BroodWar

## Visión General

Shakuras es un juego de manager de eSports inspirado en Football Manager, donde el jugador humano gestiona un equipo de StarCraft: BroodWar. Los partidos son 1v1 entre bots, y el manager no controla las unidades directamente durante las partidas.

## Concepto del Juego

- **Tipo de juego**: Manager de eSports (como Football Manager)
- **Partidas**: 1v1 de StarCraft: BroodWar
- **Jugador humano**: Manager/Coach, no controla unidades durante los matches
- **Objetivo**: Gestionar equipo, tácticas, estrategias, y ganar torneos/ligas

## Diseño del Juego

### Equipos y Jugadores (Bots)

- Los equipos están formados por bots ("jugadores")
- Cada bot tiene stats individuales: macro, micro, multitasking, strategy
- Los bots tienen raza (Terran, Zerg, Protoss, Random)
- Ideas futuras: mejoras tras partidos, mercado de fichajes, fatiga/lesiones

### Tácticas y Estrategias (por implementar)

- Estrategias predefinidas y configurables por el usuario
- Cada estrategia es un conjunto de reglas que afecta el comportamiento del bot
- El manager decide qué jugadores (bots) se adaptan mejor a cada estrategia

## Arquitectura del Proyecto

```
shakuras-api/
├── maps/                    # Mapas YAML (layouts de juego)
├── scenarios/               # Escenarios YAML para testing del engine
│   └── navigation/          # Escenarios de pathfinding
├── docs/                    # Documentación
├── src/
│   ├── shakuras/            # Configuración Django (settings, urls)
│   ├── matches/             # Match engine + API + visualizadores
│   ├── players/             # Jugadores (bots) con stats y razas
│   ├── teams/               # Equipos
│   └── users/               # Usuarios (managers humanos)
└── requirements.txt
```

## Match Engine

Ver `docs/match-engine.md` para detalles técnicos.

## Estado Actual

### Implementado

**Match Engine (`matches/`)**
- Motor de simulación tick-by-tick con física, colisiones y pathfinding
- 4 acciones de unidades: Gather, Attack, Move, Hold
- 6 tipos de entidad: base, worker, marine, zealot, zergling, mineral_patch
- Sistema de producción de unidades (cola en buildings)
- IA de producción automática (`ProductionAI`): produce workers y reasigna idle
- Resource contention: un worker por mineral patch a la vez
- Sistema de replay basado en deltas JSON
- Sistema de mapas YAML con loader y validación (`loader.py`)
- Sistema de escenarios YAML para testing sin base de datos (`scenario.py`)
- Modelo `Replay` para guardar replays en DB

**Herramientas visuales**
- Visualizador de replays (HTML)
- Visualizador de escenarios (HTML)
- Editor de mapas interactivo (HTML)

**Jugadores y equipos (`players/`, `teams/`)**
- Modelo `Player` con stats: macro, micro, multitasking, strategy (0-100)
- Raza por jugador: Terran, Zerg, Protoss, Random
- Generador de jugadores con nombres realistas (Faker + hangul-names para nombres coreanos)
- Modelo `Team` básico

**Usuarios y API (`users/`, `shakuras/`)**
- Custom User model basado en email
- Autenticación JWT (SimpleJWT)
- API REST con Django REST Framework

**Testing**
- 58 tests unitarios (pytest + pytest-django)
- Cobertura: navegación, combate, minería, colisiones, producción, API, editor de mapas

### Por implementar

- Asociación de unidades a razas en el engine (hoy un jugador Terran puede producir zealots)
- IA funcional para los bots (la actual solo produce workers)
- Lógica de victoria/derrota
- Tácticas y estrategias configurables
- Torneos y ligas
- Mejoras de bots tras partidos
- Mercado de fichajes
