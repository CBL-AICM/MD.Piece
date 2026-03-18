# RULES.md - md.piece

## SYNAPTIC Protocol v3.0 - Project Rules

---

## 1. CODE QUALITY RULES

### 1.1 General Standards
- All code must follow consistent formatting
- No commented-out code in production
- Clear, descriptive variable and function names
- Maximum function length: 50 lines
- Maximum file length: 300 lines

### 1.2 Documentation
- All public functions must have JSDoc/docstrings
- README.md must be updated with each major feature
- CHANGELOG must be maintained

### 1.3 Error Handling
- All async operations must have error handling
- User-facing errors must be clear and actionable
- Log all errors with context

---

## 2. ARCHITECTURE RULES

### 2.1 Structure
- Separation of concerns is mandatory
- No circular dependencies allowed
- Clear module boundaries

### 2.2 Dependencies
- All dependencies must be justified
- No duplicate functionality
- Regular security audits required

---

## 3. SYNAPTIC PROTOCOL RULES

### 3.1 Decision Gates
- ALL architectural decisions require a Decision Gate
- MINIMUM 3 options must be presented
- NO implementation before user approval

### 3.2 Documentation Requirements
- Every cycle must update BITACORA.md
- Every decision must be recorded
- All trade-offs must be documented

### 3.3 Validation
- Code must pass all existing tests before submission
- New features require new tests
- Compliance score must stay above 70%

---

## 4. PROJECT-SPECIFIC RULES

### Project: md.piece
### Description: Project md.piece


---

## 5. ENFORCEMENT

- Mode: STRICT
- Auto-rejection: Enabled
- Compliance threshold: 70%

---

*Last Updated: 2026-03-18T03:56:00.016Z*
*SYNAPTIC Protocol v3.0*
