# Cost Management

## 1. Objective

The project is designed to operate within the Azure Free
Account constraints during development.

## 2. Cost controls

- use the Azure Free Account spending protection
- avoid moving the subscription to PAYG
- minimize always-on compute
- use serverless/query-on-demand services where appropriate
- stop or delete temporary resources when no longer needed
- monitor Azure usage regularly
- avoid unnecessary data duplication

## 3. Development strategy

The project uses small samples during development and
testing.

Full historical datasets are processed only when required
for the relevant pipeline stage.

## 4. Important Limitation

Azure budget alerts are monitoring mechanisms and should
not be treated as automatic spending controls.

The Azure Free Account spending limit remains the primary
protection during the project.
