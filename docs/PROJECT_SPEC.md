# Project Specification: Equity Financial Optimizer

# Equity Compensation Planning System - Project Specification

## Executive Summary

Building a comprehensive financial planning toolkit to optimize equity management for employees, with particular emphasis on overarching financial optimization including considerations that the employee may have around maximizing charitable impact through company donation matching programs, managing complex tax implications, and timing exercise and sale decisions given some range of possible assumed financial outlooks, such as what may be offered by a professional financial advisor or tax planning professional.

## Problem Statement

Employees with significant equity face complex decisions involving:
- **Immediate**: Tender offer participation
- **Near-term**: Exercise timing before anticipated 409A increase
- **Long-term**: Multi-year donation and tax optimization strategy

The interaction between ISOs, NSOs, AMT, charitable deductions, and donation matching creates a high-dimensional optimization problem requiring sophisticated modeling.

## User Goals (with priority to be able to be user specified)

1. **Maximize charitable impact** - Leverage match (3:1 or 1:1) effectively
2. **Ensure sufficient liquidity** - Maintain cash flow for living expenses and exercise and tax expenses
3. **Preserve upside potential** - Retain equity for future growth depending on employee's risk tolerance and diversification goals
4. **Minimize tax burden** - Optimize across multiple years including consideration of tax credits, AMT, capital gains, charitable deductions, and tax planning strategies
5. **Manage downside risk** - Protect against adverse scenarios

## System Requirements

### Functional Requirements

1. **Donation Impact Analysis**
   - Calculate true multipliers (2x-6x) for different strategies
   - Model tax deduction limitations and carryforwards
   - Compare share donation vs. cash donation after sale

2. **Tender Participation Optimization**
   - Evaluate which shares to tender (LTCG vs. STCG vs. cashless)
   - Consider opportunity cost of future donations
   - Account for carryforward provisions

3. **Exercise Timing Strategy**
   - Model cost/benefit of early exercise before 409A increase
   - Calculate AMT implications and credit utilization
   - Determine optimal ISO vs. NSO exercise mix

4. **Multi-Year Tax Planning**
   - Project AMT credits and utilization
   - Optimize charitable deduction timing
   - Plan for cost basis elections

5. **Scenario Comparison**
   - Evaluate strategies across market scenarios (bear/base/bull)
   - Calculate risk-adjusted outcomes
   - Provide sensitivity analysis

### Technical Requirements

- **Architecture**: Stateless calculators with MCP integration
- **Language**: Python with type hints
- **Dependencies**: Standard library + numpy/pandas only
- **Performance**: <100ms per calculation
- **Validation**: Match reference implementations exactly for existing calculators where provided

## Key Constraints

### Timeline
- Tender offer deadline: May 29, 2025 (Decision Completed: Tendered 1 lot of NSOs)
- 409a likely increase mid June 2025
- Exercise window: Post-tender to ~September 2025
- Donation window: 3 years from liquidity event in which a sale is made
- Deduction carryforward: 5 years maximum

### Financial
- User can specify financial situation and applicable program rules in a dedicated docs file

## Technical Architecture

### Calculator Suite
0. **Scenario Planning Engine** - Strategy evaluation which calls other calculators
1. **Pledge Calculator** - Computes donation Impact
2. **AMT Calculator** - Calculates both regular and AMT tax code to allow estimation of AMT breakeven point or AMT tax liability
3. And other calculators related to Tax, Tender, Exercise and cash flow planning as needed to address the required suite of various scenarios

### Data Flow
```
User Profile + Market Scenarios → Calculators → Scenario Engine → Recommendations
```

### Integration Approach
- Each calculator exposed as MCP tool
- Standardized input/output interfaces
- Composable for complex scenarios

## Success Criteria

1. **Immediate**: Clear tender participation recommendation with rationale
2. **Short-term**: Exercise strategy maximizing donation value
3. **Long-term**: Multi-year plan optimizing all objectives
4. **Validation**: Results match reference calculations within 1%
5. **Usability**: Other employees can adapt for their situation

## Risk Factors
In Scope:
- 409A increase timing uncertainty
- Market volatility affecting valuations
Out of Scope:
- Tax law changes
- Company Program modifications
- Personal circumstance changes

### Calculator Interface
Each calculator must implement: #consider reworking this section
```
interface Calculator {
  name: string
  description: string
  version: string

  validate(inputs: CalculatorInputs): ValidationResult
  calculate(inputs: CalculatorInputs): CalculatorResult
  getSchema(): InputSchema
}
```

### MCP Integration
- Each calculator exposed as an MCP tool
- Standardized input/output schemas
- Error handling and validation
- Usage examples and documentation

## Technical Architecture
[Detailed architecture to be developed]

## Development Phases
1. **Phase 1**: Core calculator framework
2. **Phase 2**: Initial calculator implementations
3. **Phase 3**: Complete initial recommendations for immediate tender decision
4. **Phase 4**: Testing and documentation for publishing
5. **Phase 5**: MCP implementation
