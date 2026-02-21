# Shakuras - Manager de eSports de StarCraft: BroodWar

## Visión General

Shakuras es un juego de manager de eSports inspirado en Football Manager, donde el jugador humano gestiona un equipo de StarCraft: BroodWar. Los partidos son 1v1 entre bots, y el manager no controla las unidades directamente durante las partidas.

## Concepto del Juego

- **Tipo de juego**: Manager de eSports (como Football Manager)
- **Partidas**: 1v1 de StarCraft: BroodWar
- **Jugador humano**: Manager/Coach, no controla unidades durante los matches
- **Objetivo**: Gestionar equipo, tácticas, estrategias, y ganar torneos/ligas

## Elementos del Juego

### Equipos y Jugadores (Bots)

- Los equipos están formados por bots ("jugadores")
- Cada bot tiene stats individuales: macro, micro, multitasking, strategy
- Los bots tienen raza (Terran, Zerg, Protoss, Random)
- Los bots pueden mejorar tras los partidos
- Sistema de mercado de fichajes entre equipos

### Carreras/Razas Soportadas

1. **Terran**: SCV, Marine, Medic (MVP inicial: Terran vs Terran)
2. **Protoss**: Probe, Zealot, Dragoon
3. **Zerg**: Drone, Zergling, Hydralisk, Mutalisk

### Tácticas y Estrategias

- Estrategias predefinidas y configurables por el usuario
- Cada estrategia es un conjunto de reglas que afecta el comportamiento del bot
- El manager decide qué jugadores (bots) se adaptan mejor a cada estrategia

## Match Engine

Ver `docs/match-engine.md` para detalles técnicos.

## Arquitectura Propuesta

```
shakuras-api/          # Proyecto Django (API REST)
shakuras-engine/       # Paquete Python independiente (futuro)
```

El match engine debería ser un paquete Python independiente, sin dependencias de Django, para facilitar testing y reuse.

## Estado Actual

### Implementado
- Modelo de Player con stats: macro, micro, multitasking, strategy
- Modelo de Team
- Match engine con física, acciones y replay

### Por Hacer
- Lógica de mejoras de bots tras partidos
- Sistema de mercado de fichajes
- Sistema de tácticas/estrategias configurables
- Integración con el match engine
- Torneos y ligas
- Sistema de fatiga, lesiones, condición física
