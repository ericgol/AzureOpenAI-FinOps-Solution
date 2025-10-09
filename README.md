# Azure OpenAI FinOps Solution

A comprehensive FinOps (Financial Operations) solution for tracking and analyzing costs of Azure OpenAI services accessed through Azure API Management (APIM) gateway.

## Overview

This solution provides cost allocation and usage tracking for Azure OpenAI services consumed through an enterprise APIM gateway facade. It correlates API telemetry with cost data to enable per-device and per-store cost analysis and reporting.

## Architecture

The solution consists of 7 main steps:

1. **Sink APIM Telemetry to Log Analytics** - Configure APIM diagnostic settings to capture gateway logs
2. **Timer-triggered Azure Function** - Python function running every 6 minutes to orchestrate data collection
3. **Fetch Telemetry from Log Analytics** - Query Log Analytics workspace for APIM call records
4. **Fetch Cost Data via Cost Management API** - Retrieve cost records for the same time period
5. **Correlate Telemetry with Cost Data** - Join datasets and allocate costs proportionally
6. **Write Correlated Data to Storage** - Store cost-per-user/store data for persistence
7. **Power BI Reporting** - Leverage stored data for business intelligence and visualization

## Solution Components

### Azure Services
- **Azure API Management** (Developer/Premium SKU with private networking)
- **Azure Log Analytics Workspace**
- **Application Insights**
- **Azure Functions** (Python runtime)
- **Azure Storage Account**
- **Azure Cost Management**

### Key Features
- Automated cost allocation based on API usage patterns
- Custom attribute tracking (user ID, store ID) via APIM policies
- Secure credential management using Managed Identity
- Configurable time intervals for data collection
- Scalable storage solution for historical data
- Power BI ready data schemas

## Project Structure

```
AzureOpenAI_FinOps_Solution/
├── infrastructure/              # Infrastructure as Code
│   ├── bicep/                   # Azure Bicep templates
│   │   ├── modules/             # Reusable Bicep modules
│   │   ├── parameters/          # Parameter files for environments
│   │   └── scripts/             # Deployment helper scripts
│   └── powershell/              # PowerShell deployment scripts
│       ├── dev/                 # Development environment scripts
│       └── prod/                # Production environment scripts
├── src/                         # Source code
│   ├── functions/               # Azure Functions
│   │   ├── finops-data-collector/ # Main data collection function
│   │   └── shared/              # Shared utilities and libraries
│   ├── apim-policies/           # APIM policy XML files
│   └── configs/                 # Configuration templates
├── docs/                        # Documentation
│   ├── architecture/            # Solution architecture documentation
│   ├── deployment/              # Deployment guides
│   └── api/                     # API documentation
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
├── storage-schemas/             # Data schemas and storage structure
├── powerbi-templates/           # Power BI report templates
└── .github/workflows/           # CI/CD workflows
```

## Prerequisites

- Azure Subscription with appropriate permissions
- Azure CLI or PowerShell Az module
- Python 3.9+
- Azure Functions Core Tools
- Power BI Desktop (for reporting)

## Quick Start

### Development Environment

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd AzureOpenAI_FinOps_Solution
   ```

2. **Deploy infrastructure**
   ```powershell
   cd infrastructure/powershell/dev
   ./Deploy-DevEnvironment.ps1 -SubscriptionId "<your-subscription-id>"
   ```

3. **Configure APIM policies**
   ```bash
   # Apply APIM policies for telemetry collection
   # Instructions in docs/deployment/apim-setup.md
   ```

4. **Deploy Azure Functions**
   ```bash
   cd src/functions/finops-data-collector
   func azure functionapp publish <your-function-app-name>
   ```

### Production Environment

See [Production Deployment Guide](docs/deployment/production-setup.md) for comprehensive production deployment instructions.

## Configuration

### Environment Variables

The solution uses the following key configuration parameters:

- `LOG_ANALYTICS_WORKSPACE_ID` - Log Analytics workspace identifier
- `COST_MANAGEMENT_SCOPE` - Scope for cost data retrieval
- `STORAGE_ACCOUNT_NAME` - Storage account for correlated data
- `DATA_COLLECTION_INTERVAL` - Timer trigger interval (default: 6 minutes)

### Custom Attributes

Configure the following custom attributes in APIM policies:
- `device-id` - Unique identifier for API consumers
- `store-number` - Store/location identifier for cost allocation
- `api-category` - API categorization for reporting

## Data Flow

1. **API Calls** → APIM Gateway (with custom headers/parameters)
2. **APIM Logs** → Log Analytics Workspace
3. **Timer Function** → Queries Log Analytics + Cost Management API
4. **Data Correlation** → Joins telemetry with cost data
5. **Storage** → Persists correlated data
6. **Power BI** → Visualizes cost allocation and usage patterns

## Security Considerations

- Managed Identity for Azure service authentication
- Private networking for APIM connectivity
- Secure storage of configuration parameters
- RBAC-based access control
- Data encryption at rest and in transit

## Cost Optimization

- **Development**: Minimal resources for proof-of-concept
- **Production**: Optimized for performance and scale
- Resource sizing recommendations in [Cost Optimization Guide](docs/architecture/cost-optimization.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Support

For issues and questions:
- Check the [documentation](docs/)
- Review [troubleshooting guide](docs/deployment/troubleshooting.md)
- Open an issue in the repository

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.
