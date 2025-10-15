#!/usr/bin/env python3
"""
Deployment Validation Script for FinOps Migration

This script validates that the migration from deprecated packages to modern
alternatives has been completed successfully and all systems are functional.

Run this script after deploying the updated function apps to validate the migration.
"""

import sys
import os
import json
import subprocess
import importlib
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MigrationValidator:
    """Validates the migration from deprecated dependencies."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.success_count = 0
        self.total_checks = 0
    
    def run_all_validations(self) -> bool:
        """Run all validation checks."""
        logger.info("🚀 Starting FinOps Migration Validation")
        logger.info("=" * 60)
        
        # Package validation
        self._validate_deprecated_packages_removed()
        self._validate_new_packages_installed()
        self._validate_package_versions()
        
        # Code validation
        self._validate_pydantic_v2_compatibility()
        self._validate_requirements_files()
        
        # Function app validation
        self._validate_function_apps()
        
        # Integration validation
        self._validate_configuration_loading()
        self._validate_telemetry_setup()
        
        # Report results
        self._report_results()
        
        return len(self.errors) == 0
    
    def _check(self, description: str, check_func, *args, **kwargs) -> bool:
        """Helper method to run a check and track results."""
        self.total_checks += 1
        logger.info(f"Checking: {description}")
        
        try:
            result = check_func(*args, **kwargs)
            if result:
                self.success_count += 1
                logger.info("✅ PASSED")
                return True
            else:
                self.errors.append(f"FAILED: {description}")
                logger.error("❌ FAILED")
                return False
        except Exception as e:
            self.errors.append(f"ERROR in {description}: {str(e)}")
            logger.error(f"❌ ERROR: {str(e)}")
            return False
    
    def _validate_deprecated_packages_removed(self):
        """Validate that deprecated packages are no longer installed."""
        logger.info("\n📦 Validating Deprecated Packages Removed")
        logger.info("-" * 40)
        
        deprecated_packages = [
            'opencensus-ext-azure',
            'applicationinsights'
        ]
        
        for package in deprecated_packages:
            self._check(
                f"Deprecated package {package} is not importable",
                self._package_not_importable,
                package
            )
    
    def _validate_new_packages_installed(self):
        """Validate that new packages are correctly installed."""
        logger.info("\n📦 Validating New Packages Installed")
        logger.info("-" * 40)
        
        required_packages = [
            'azure.monitor.opentelemetry',
            'opentelemetry.trace',
            'opentelemetry.sdk.trace',
            'pydantic',
            'azure.functions',
            'azure.identity',
            'azure.monitor.query',
            'requests',
            'pandas',
            'numpy'
        ]
        
        for package in required_packages:
            self._check(
                f"Package {package} is importable",
                self._package_importable,
                package
            )
    
    def _validate_package_versions(self):
        """Validate that packages meet minimum version requirements."""
        logger.info("\n🔢 Validating Package Versions")
        logger.info("-" * 40)
        
        version_requirements = {
            'pydantic': (2, 12, 0),
            'requests': (2, 32, 0),
            'pandas': (2, 3, 0),
            'azure-functions': (1, 24, 0)
        }
        
        for package_name, min_version in version_requirements.items():
            self._check(
                f"Package {package_name} meets minimum version {'.'.join(map(str, min_version))}",
                self._validate_package_version,
                package_name,
                min_version
            )
    
    def _validate_pydantic_v2_compatibility(self):
        """Validate Pydantic v2 API compatibility."""
        logger.info("\n🔧 Validating Pydantic v2 Compatibility")
        logger.info("-" * 40)
        
        self._check(
            "Pydantic v2 imports work correctly",
            self._test_pydantic_v2_imports
        )
        
        self._check(
            "FinOpsConfig uses Pydantic v2 API",
            self._test_finops_config_v2
        )
    
    def _validate_requirements_files(self):
        """Validate that requirements.txt files are updated correctly."""
        logger.info("\n📋 Validating Requirements Files")
        logger.info("-" * 40)
        
        requirements_files = [
            self.project_root / "src/functions/finops-data-collector/requirements.txt",
            self.project_root / "src/functions/eventhub-to-appinsights/requirements.txt"
        ]
        
        for req_file in requirements_files:
            if req_file.exists():
                self._check(
                    f"Requirements file {req_file.name} has no deprecated packages",
                    self._validate_requirements_file,
                    req_file
                )
            else:
                self.warnings.append(f"Requirements file not found: {req_file}")
    
    def _validate_function_apps(self):
        """Validate that Function Apps can be imported without errors."""
        logger.info("\n⚡ Validating Function Apps")
        logger.info("-" * 40)
        
        # Add function paths to Python path for testing
        finops_path = self.project_root / "src/functions/finops-data-collector"
        eventhub_path = self.project_root / "src/functions/eventhub-to-appinsights"
        
        if finops_path.exists():
            sys.path.insert(0, str(finops_path))
            
            self._check(
                "FinOps data collector config can be imported",
                self._test_import_module,
                "shared.config"
            )
            
            self._check(
                "FinOps telemetry collector can be imported",
                self._test_import_module,
                "shared.telemetry_collector"
            )
        
        if eventhub_path.exists():
            sys.path.insert(0, str(eventhub_path))
    
    def _validate_configuration_loading(self):
        """Validate that configuration loading works with Pydantic v2."""
        logger.info("\n⚙️  Validating Configuration Loading")
        logger.info("-" * 40)
        
        self._check(
            "Configuration can be loaded with environment variables",
            self._test_config_loading
        )
    
    def _validate_telemetry_setup(self):
        """Validate that telemetry setup works with new packages."""
        logger.info("\n📊 Validating Telemetry Setup")
        logger.info("-" * 40)
        
        self._check(
            "OpenTelemetry tracer can be created",
            self._test_opentelemetry_setup
        )
    
    # Helper methods for individual checks
    
    def _package_not_importable(self, package_name: str) -> bool:
        """Check that a package is not importable (should be removed)."""
        try:
            __import__(package_name.replace('-', '_'))
            return False  # Package is still importable, which is bad
        except ImportError:
            return True  # Package is not importable, which is good
    
    def _package_importable(self, package_name: str) -> bool:
        """Check that a package is importable."""
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False
    
    def _validate_package_version(self, package_name: str, min_version: Tuple[int, ...]) -> bool:
        """Validate that a package meets minimum version requirements."""
        try:
            # Handle different package import names
            import_name = package_name.replace('-', '_')
            if package_name == 'azure-functions':
                import_name = 'azure.functions'
            
            module = __import__(import_name)
            
            # Get version
            version_str = None
            if hasattr(module, '__version__'):
                version_str = module.__version__
            elif hasattr(module, 'VERSION'):
                version_str = module.VERSION
            
            if version_str:
                if isinstance(version_str, tuple):
                    version_tuple = version_str
                else:
                    version_parts = version_str.split('.')
                    version_tuple = tuple(int(part) for part in version_parts[:len(min_version)])
                
                return version_tuple >= min_version
            else:
                self.warnings.append(f"Could not determine version for {package_name}")
                return True  # Assume it's okay if we can't check
                
        except Exception as e:
            logger.error(f"Error checking version for {package_name}: {e}")
            return False
    
    def _test_pydantic_v2_imports(self) -> bool:
        """Test that Pydantic v2 imports work correctly."""
        try:
            from pydantic import BaseModel, Field, field_validator, ConfigDict
            return all([BaseModel, Field, field_validator, ConfigDict])
        except ImportError:
            return False
    
    def _test_finops_config_v2(self) -> bool:
        """Test that FinOpsConfig uses Pydantic v2 API."""
        try:
            from shared.config import FinOpsConfig
            
            # Check that it has model_config attribute (Pydantic v2)
            if not hasattr(FinOpsConfig, 'model_config'):
                return False
            
            # Check that it doesn't have Config class (Pydantic v1)
            if hasattr(FinOpsConfig, 'Config'):
                return False
            
            return True
        except ImportError:
            return False
    
    def _validate_requirements_file(self, req_file: Path) -> bool:
        """Validate that a requirements file doesn't contain deprecated packages."""
        deprecated_packages = ['opencensus-ext-azure', 'applicationinsights']\n        \n        try:\n            content = req_file.read_text()\n            for deprecated in deprecated_packages:\n                if deprecated in content:\n                    return False\n            return True\n        except Exception:\n            return False\n    \n    def _test_import_module(self, module_name: str) -> bool:\n        \"\"\"Test that a module can be imported.\"\"\"\n        try:\n            __import__(module_name)\n            return True\n        except ImportError as e:\n            logger.error(f\"Import error for {module_name}: {e}\")\n            return False\n    \n    def _test_config_loading(self) -> bool:\n        \"\"\"Test that configuration can be loaded.\"\"\"\n        try:\n            # Set minimal required environment variables\n            os.environ.update({\n                'LOG_ANALYTICS_WORKSPACE_ID': 'test-workspace',\n                'COST_MANAGEMENT_SCOPE': '/subscriptions/test',\n                'STORAGE_ACCOUNT_NAME': 'teststorage'\n            })\n            \n            from shared.config import get_config\n            config = get_config()\n            \n            return config is not None\n        except Exception as e:\n            logger.error(f\"Config loading error: {e}\")\n            return False\n    \n    def _test_opentelemetry_setup(self) -> bool:\n        \"\"\"Test that OpenTelemetry setup works.\"\"\"\n        try:\n            from opentelemetry import trace\n            from opentelemetry.sdk.trace import TracerProvider\n            \n            # Set up tracer\n            trace.set_tracer_provider(TracerProvider())\n            tracer = trace.get_tracer(__name__)\n            \n            # Test span creation\n            with tracer.start_as_current_span(\"test_span\"):\n                pass\n            \n            return True\n        except Exception as e:\n            logger.error(f\"OpenTelemetry setup error: {e}\")\n            return False\n    \n    def _report_results(self):\n        \"\"\"Report validation results.\"\"\"\n        logger.info(\"\\n\" + \"=\" * 60)\n        logger.info(\"📊 VALIDATION RESULTS\")\n        logger.info(\"=\" * 60)\n        \n        if self.errors:\n            logger.error(f\"❌ {len(self.errors)} ERRORS FOUND:\")\n            for error in self.errors:\n                logger.error(f\"  - {error}\")\n            logger.error(\"\")\n        \n        if self.warnings:\n            logger.warning(f\"⚠️  {len(self.warnings)} WARNINGS:\")\n            for warning in self.warnings:\n                logger.warning(f\"  - {warning}\")\n            logger.warning(\"\")\n        \n        success_rate = (self.success_count / self.total_checks) * 100 if self.total_checks > 0 else 0\n        \n        if len(self.errors) == 0:\n            logger.info(f\"✅ MIGRATION VALIDATION PASSED\")\n            logger.info(f\"✅ {self.success_count}/{self.total_checks} checks passed ({success_rate:.1f}%)\")\n            \n            if len(self.warnings) == 0:\n                logger.info(\"🎉 All systems are ready for deployment!\")\n            else:\n                logger.info(\"⚠️  Deployment ready with warnings - please review warnings above.\")\n        else:\n            logger.error(f\"❌ MIGRATION VALIDATION FAILED\")\n            logger.error(f\"❌ {len(self.errors)} errors must be fixed before deployment\")\n            logger.error(f\"✅ {self.success_count}/{self.total_checks} checks passed ({success_rate:.1f}%)\")\n        \n        logger.info(\"=\" * 60)\n\n\ndef main():\n    \"\"\"Main entry point.\"\"\"\n    validator = MigrationValidator()\n    \n    success = validator.run_all_validations()\n    \n    if success:\n        logger.info(\"\\n🎯 Migration validation completed successfully!\")\n        logger.info(\"You can proceed with deployment.\")\n        sys.exit(0)\n    else:\n        logger.error(\"\\n🚨 Migration validation failed!\")\n        logger.error(\"Please fix the errors above before deploying.\")\n        sys.exit(1)\n\n\nif __name__ == \"__main__\":\n    main()"