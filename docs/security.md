# Security

## 1. Data Classification

The project uses publicly available datasets.

No PHI or personally identifiable healthcare information is
intentionally ingested.

## 2. Identity

Azure resources should use least-privilege access where
practical.

## 3. Secrets

Secrets and credentials must not be committed to GitHub.

Sensitive configuration is supplied through environment
variables, Azure configuration or secret-management
mechanisms where required.

## 4. Storage

ADLS containers are separated into logical data zones:

- raw
- bronze
- silver
- gold
- quarantine

## 5. Public Portfolio Limitation

The project is a learning/portfolio implementation and
does not claim production healthcare security or regulatory
compliance certification.
