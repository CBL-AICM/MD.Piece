# DESIGN_DOC.md - MD.Piece

## SYNAPTIC Protocol v3.0 - Architecture Document

---

## 1. PROJECT OVERVIEW

### 1.1 Project Name
MD.Piece

### 1.2 Description
Project MD.Piece

### 1.3 Project Type
Capture and OCR workflow planning

### 1.4 Domain
General

### 1.5 Current Phase
Foundation with capture/OCR planning assets

---

## 2. ARCHITECTURE DECISIONS

### Decision Log

| ID | Decision | Option Selected | Date | Rationale |
|----|----------|-----------------|------|-----------|
| AD-001 | Primer entregable para OCR capture | Documentacion + esqueletos Web y Flutter + contrato API | 2026-04-15 | El proyecto aun no tiene stack definido, por lo que se prioriza una base transferible antes de elegir implementacion final |

*Decisions will be logged here as they are made through Decision Gates*

---

## 3. TECHNOLOGY STACK

### 3.1 Frontend
Candidate references include React + TypeScript and Flutter

### 3.2 Backend
OCR API contract defined, implementation pending

### 3.3 Infrastructure
To be defined

---

## 4. SYSTEM COMPONENTS

### Planned Components

- Capture UI module
- Capture quality evaluation
- Image preprocessing pipeline
- OCR recognition service
- Result confirmation flow

### Component Diagram
```text
[Capture UI] -> [Capture Evaluate API] -> [OCR Recognize API] -> [Result Review]
```

---

## 5. DATA FLOW

1. User opens capture screen
2. Frontend evaluates capture readiness
3. Approved capture is submitted for OCR
4. OCR response returns text and confidence
5. User confirms or retries

---

## 6. SECURITY CONSIDERATIONS

- [ ] Authentication method defined
- [ ] Authorization rules documented
- [ ] Data encryption requirements specified
- [ ] API security measures planned
- [ ] OCR image retention policy defined

---

## 7. PATTERNS & CONVENTIONS

### Patterns to Follow

- Shared capture state model across clients
- Separate evaluation and recognition API responsibilities
- Clear user-facing remediation messages for capture failures

### Anti-patterns to Avoid

- Tightly coupling camera UI to OCR vendor logic
- Returning vague errors to end users
- Mixing ephemeral build artifacts into source control

---

## 8. EVOLUTION HISTORY

| Cycle | Change | Impact | Synaptic Strength |
|-------|--------|--------|-------------------|
| 0 | Initial creation | Baseline | 0% |
| 1 | OCR planning docs and reference apps added | Foundation package ready for review | 18% |
| 2 | Web example build validated and repo prepared for push | Implementation baseline stabilized | 24% |

---

## 9. TECHNICAL NOTES

- Se agrego un paquete de referencia en `context/` y `examples/`
- El ejemplo Web usa React + TypeScript + Vite como referencia de interfaz
- El ejemplo Flutter define flujo de estados y puntos de integracion para camara y OCR
- El contrato API separa evaluacion de captura y reconocimiento OCR

---

*Created: 2026-03-18T03:56:00.016Z*
*Updated: 2026-04-15T06:30:00+08:00*
*SYNAPTIC Protocol v3.0 - Architecture Evolution Tracking*
