# Core-Start-Runner

Report feedback from compile events.

## Directory structure

* **lib/** - Third-party libraries
* **tests/** - Directory containing various test data files
* **main.py** - Lambda entry point (handler method). A good place to start.

## Description

This is the "TOP" level library.

From the SCK Command line "core" modules is executed which determines targets and loads
the appropriate target libraries.  The target libraries will then use this core
framework library with helper functions.

This library has been extended to use "Simple Python Utils" which contains helper
functions for the entire CI/CD pipeline infrastructure deployment framework.

## Configuration

If you include this module in your project, you are REQUIRED to produce a configuration
file called "config.py" and put that configration file in the root of your project.

### Core-Automation Configuration Variables

| Variable Name        | Type    | Default Value | Description                                                  | Example                |
|----------------------|---------|---------------|--------------------------------------------------------------|------------------------|
| `ENVIRONMENT`        | String  | None          | Core Automation Operating Environment: prod, nonprod, or dev | `prod`                 |
| `LCOAL_MODE`         | Boolean | None          | Enable local operation mode for the app.                     | `True` or `False`      |
| `API_LAMBDA_ARN`     | String  | None          | Secret API key for authentication.                           | `API_KEY=your-api-key` |
| `OUTPUT_PATH`        | String  | None          |                                                              |                        |
| `PLATFORM_PATH`      | String  | None          |                                                              |                        |
| `ENFORCE_VALIDATION` | String  | None          |                                                              |                        |
| `DYNAMODB_HOST`      | String  | None          |                                                              |                        |
| `DYNAMODB_REAGION`   | String  | None          |                                                              |                        |
| `EVENT_TABLE_NAME`   | String  | None          |                                                              |                        |
| `BASE_DIR`           | String  | None          | The folder where the sub-folder 'compiler' is located        |                        |

These above values are required by various modules.  Please generate this config.py file and put in the ROOT of your application
during your application deployment.
