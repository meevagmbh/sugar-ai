# Configuration Best Practices

Essential configuration patterns and best practices for Sugar.

## 🛡️ Global Directory Exclusions

### The Problem

By default, Sugar's discovery modules (`code_quality`, `test_coverage`) might scan directories that should be ignored:
- Virtual environments (`venv`, `.venv`, `env`)
- Build artifacts (`build`, `dist`, `coverage`)
- Development tools (`.tox`, `.nox`, `.pytest_cache`)
- Dependencies (`node_modules`)

### The Solution: Global Exclusions

Configure global exclusions that apply to ALL discovery modules:

```yaml
# .sugar/config.yaml
sugar:
  discovery:
    # Global exclusions for all discovery modules
    global_excluded_dirs: [
      "node_modules", ".git", "__pycache__", 
      "venv", ".venv", "env", ".env", "ENV", 
      "env.bak", "venv.bak", "virtualenv",
      "build", "dist", ".tox", ".nox",
      "coverage", "htmlcov", ".pytest_cache",
      ".sugar", ".claude"
    ]
    
    code_quality:
      enabled: true
      excluded_dirs: [
        "node_modules", ".git", "__pycache__", 
        "venv", ".venv", "env", ".env", "ENV", 
        "env.bak", "venv.bak", "virtualenv",
        "build", "dist", ".tox", ".nox",
        "coverage", "htmlcov", ".pytest_cache",
        ".sugar", ".claude"
      ]
      
    test_coverage:
      enabled: true
      source_dirs: ["src", "lib", "app"]
      test_dirs: ["tests", "test", "__tests__"]
      excluded_dirs: [
        "node_modules", ".git", "__pycache__", 
        "venv", ".venv", "env", ".env", "ENV", 
        "env.bak", "venv.bak", "virtualenv",
        "build", "dist", ".tox", ".nox",
        "coverage", "htmlcov", ".pytest_cache",
        ".sugar", ".claude"
      ]
```

### Why Each Discovery Module Needs Exclusions

**Current Architecture:** Each discovery module (`code_quality`, `test_coverage`) operates independently and needs its own exclusion configuration.

**Future Enhancement:** The `global_excluded_dirs` will be implemented to automatically apply to all modules.

## 🎯 Virtual Environment Patterns

### All Virtual Environment Variations

```yaml
excluded_dirs: [
  # Python virtual environments
  "venv",           # python -m venv venv
  ".venv",          # python -m venv .venv
  "env",            # python -m venv env
  ".env",           # python -m venv .env (not environment files)
  "ENV",            # python -m venv ENV
  "env.bak",        # backup environments
  "venv.bak",       # backup environments
  "virtualenv",     # older virtualenv tool
  
  # Node.js
  "node_modules",   # npm/yarn dependencies
  
  # Build and test artifacts
  "build",          # Build output
  "dist",           # Distribution files
  ".tox",           # Tox testing environments
  ".nox",           # Nox testing environments
  "coverage",       # Coverage reports
  "htmlcov",        # HTML coverage reports
  ".pytest_cache",  # Pytest cache
  
  # Development tools
  "__pycache__",    # Python bytecode cache
  ".mypy_cache",    # MyPy cache
  ".ruff_cache",    # Ruff cache
  
  # Version control and configs
  ".git",           # Git repository data
  ".sugar",         # Sugar configuration directory
  ".claude",        # Claude CLI session data
]
```

## 📂 Project-Specific Exclusions

### Web Application Project

```yaml
sugar:
  discovery:
    code_quality:
      excluded_dirs: [
        # Standard exclusions
        "node_modules", "venv", ".venv", "build", "dist",
        
        # Web-specific
        "static/vendor",     # Third-party CSS/JS
        "assets/libs",       # Library assets
        "public/uploads",    # User uploads
        "media",            # Media files
        "logs",             # Application logs
        
        # Framework-specific
        ".next",            # Next.js
        ".nuxt",            # Nuxt.js
        "dist",             # Vue/React builds
        "coverage",         # Test coverage
      ]
```

### Python Package Project

```yaml
sugar:
  discovery:
    code_quality:
      excluded_dirs: [
        # Standard exclusions
        "venv", ".venv", "build", "dist",
        
        # Python packaging
        "*.egg-info",       # Package metadata
        ".eggs",            # Setuptools eggs
        "wheelhouse",       # Wheel cache
        
        # Documentation
        "docs/_build",      # Sphinx builds
        "site",             # MkDocs builds
        
        # Testing
        ".tox",             # Tox environments
        ".nox",             # Nox environments
        ".pytest_cache",    # Pytest cache
        "htmlcov",          # Coverage HTML
      ]
```

### Monorepo Project

```yaml
sugar:
  discovery:
    code_quality:
      excluded_dirs: [
        # Standard exclusions
        "node_modules", "venv", ".venv",
        
        # Monorepo-specific
        "*/node_modules",   # Per-package dependencies
        "*/build",          # Per-package builds
        "*/dist",           # Per-package distributions
        "packages/*/coverage", # Per-package coverage
        
        # Workspace tools
        ".yarn",            # Yarn cache
        ".pnpm-store",      # PNPM store
        "lerna-debug.log",  # Lerna logs
      ]
```

## ⚡ Performance Optimization

### Large Project Configuration

```yaml
sugar:
  discovery:
    code_quality:
      max_files_per_scan: 25  # Reduce from default 50
      excluded_dirs: [
        # Add more aggressive exclusions
        "examples", "samples", "demo", "playground",
        "docs", "documentation", ".github",
        "scripts", "tools", "utilities",
        "vendor", "third_party", "external"
      ]
      
    test_coverage:
      # Focus on core source directories only
      source_dirs: ["src"]  # Remove "lib", "app", etc.
      excluded_dirs: [
        # Same as code_quality exclusions
        "examples", "samples", "demo", "playground",
        "docs", "documentation", ".github"
      ]
```

### High-Frequency Development

```yaml
sugar:
  loop_interval: 300  # 5 minutes - shorter cycles
  discovery:
    code_quality:
      max_files_per_scan: 15  # Quick scans
      excluded_dirs: [
        # Include standard exclusions + temporary directories
        "tmp", "temp", "cache", ".cache",
        "logs", "log", ".logs"
      ]
```

## 🧪 Testing Configuration

### Test Environment Setup

```yaml
# .sugar/config.yaml for testing
sugar:
  dry_run: true  # Safe for testing
  
  discovery:
    code_quality:
      enabled: true
      max_files_per_scan: 10  # Small batches for testing
      excluded_dirs: [
        # Minimal exclusions for testing
        "venv", ".venv", "node_modules", 
        ".git", "__pycache__", ".sugar"
      ]
      
    test_coverage:
      enabled: false  # Disable to focus on code_quality testing
```

## 🔍 Debugging Discovery Issues

### Enable Debug Logging

```yaml
sugar:
  logging:
    level: "DEBUG"
    file: ".sugar/sugar.log"
    
  discovery:
    code_quality:
      # Temporarily reduce scope for debugging
      max_files_per_scan: 5
      excluded_dirs: ["venv", ".venv", "node_modules"]
```

### Test Discovery Manually

```bash
# Create test structure
mkdir -p test-project/{src,venv/lib,node_modules}
touch test-project/src/main.py
touch test-project/venv/lib/package.py

# Initialize Sugar
cd test-project
sugar init

# Run discovery in debug mode
SUGAR_LOG_LEVEL=DEBUG sugar run --dry-run --once

# Check what files were discovered
grep -i "scanning\|discovered\|excluding" .sugar/sugar.log
```

## 📋 Checklist: Proper Exclusions

- [ ] **Virtual environments**: `venv`, `.venv`, `env`, `.env`
- [ ] **Dependencies**: `node_modules`, `vendor`
- [ ] **Build artifacts**: `build`, `dist`, `target`
- [ ] **Test artifacts**: `.tox`, `.nox`, `coverage`, `htmlcov`
- [ ] **Caches**: `__pycache__`, `.pytest_cache`, `.mypy_cache`
- [ ] **VCS**: `.git`, `.svn`, `.hg`
- [ ] **Sugar**: `.sugar`, `.claude`
- [ ] **Project-specific**: Add any custom build/temp directories

## 🚀 Quick Setup Script

```bash
#!/bin/bash
# setup-sugar-exclusions.sh

cat >> .sugar/config.yaml << 'EOF'
sugar:
  discovery:
    global_excluded_dirs: [
      "node_modules", ".git", "__pycache__", 
      "venv", ".venv", "env", ".env", "ENV", 
      "env.bak", "venv.bak", "virtualenv",
      "build", "dist", ".tox", ".nox",
      "coverage", "htmlcov", ".pytest_cache",
      ".sugar", ".claude"
    ]
    
    code_quality:
      excluded_dirs: [
        "node_modules", ".git", "__pycache__", 
        "venv", ".venv", "env", ".env", "ENV", 
        "env.bak", "venv.bak", "virtualenv",
        "build", "dist", ".tox", ".nox",
        "coverage", "htmlcov", ".pytest_cache",
        ".sugar", ".claude"
      ]
      
    test_coverage:
      excluded_dirs: [
        "node_modules", ".git", "__pycache__", 
        "venv", ".venv", "env", ".env", "ENV", 
        "env.bak", "venv.bak", "virtualenv",
        "build", "dist", ".tox", ".nox",
        "coverage", "htmlcov", ".pytest_cache",
        ".sugar", ".claude"
      ]
EOF

echo "✅ Sugar exclusions configured!"
```

## 🔧 External Tools Template Configuration

### Overview

Sugar can run external code quality tools (like eslint, ruff, bandit, etc.) and automatically interpret their output to create tasks. The template system gives you full control over how tool output is analyzed and presented to Claude.

### Template Configuration Options

#### Global Options (under `external_tools` section)

```yaml
sugar:
  discovery:
    external_tools:
      enabled: true
      
      # Custom templates directory (default: .sugar/templates)
      templates_dir: ".sugar/templates"
      
      # Default template for unknown tools
      # Options: default, security, lint, coverage, or custom template name
      default_template: "default"
      
      # Map tool names to template types (overrides auto-detection)
      tool_mappings:
        # Security tools
        bandit: "security"
        semgrep: "security"
        snyk: "security"
        
        # Linting tools
        eslint: "lint"
        pylint: "lint"
        ruff: "lint"
        mypy: "lint"
        
        # Coverage tools
        coverage: "coverage"
        pytest-cov: "coverage"
        nyc: "coverage"
```

#### Per-Tool Template Options

Each tool can specify template configuration in **one of two ways** (mutually exclusive):

**Option 1: Inline Template** (full control)
```yaml
external_tools:
  tools:
    - name: custom-tool
      command: "custom-tool --format json"
      prompt_template: |
        Analyze this ${tool_name} output and focus on:
        - Critical security issues
        - Performance bottlenecks
        - Code smells
        
        Command: ${command}
        Output file: ${output_file_path}
```

**Option 2: Template Type Reference** (use named template)
```yaml
external_tools:
  tools:
    - name: eslint
      command: "npx eslint . --format json"
      template_type: "lint"
```

**Important:** You can specify **either** `prompt_template` **or** `template_type`, but not both. If both are specified, Sugar will use `prompt_template` and ignore `template_type`.

### Built-in Template Types

Sugar includes four built-in template types:

#### 1. `default` - General Purpose Analysis
Best for: Generic tools, custom analyzers, mixed output

```yaml
tools:
  - name: custom-analyzer
    command: "custom-analyzer --output json"
    template_type: "default"
```

#### 2. `security` - Security-Focused Analysis
Best for: Security scanners, vulnerability detectors

```yaml
tools:
  - name: bandit
    command: "bandit -r src/ -f json"
    template_type: "security"
```

Focuses on:
- Vulnerability severity and impact
- Security best practices
- Exploitability assessment
- Remediation guidance

#### 3. `lint` - Code Quality & Style
Best for: Linters, formatters, type checkers

```yaml
tools:
  - name: ruff
    command: "ruff check . --output-format json"
    template_type: "lint"
```

Focuses on:
- Code style violations
- Best practice adherence
- Maintainability issues
- Consistency patterns

#### 4. `coverage` - Test Coverage Analysis
Best for: Coverage reporters, test analyzers

```yaml
tools:
  - name: pytest-cov
    command: "pytest --cov=src --cov-report=json"
    template_type: "coverage"
```

Focuses on:
- Coverage gaps and missing tests
- Critical untested code paths
- Test quality assessment
- Coverage improvement priorities

### Template Priority System

When Sugar analyzes tool output, it selects templates in this order (highest to lowest priority):

1. **Tool's `prompt_template`** (inline) - Full control, highest priority
2. **Tool's `template_type`** (named reference) - Explicit template selection
3. **Global `tool_mappings`** - Centralized tool-to-template mapping
4. **Auto-detection** - Based on tool name patterns (e.g., "bandit" → security)
5. **Global `default_template`** - Fallback for unknown tools
6. **Built-in "default"** - Final fallback if nothing else matches

### Custom Templates

Create custom templates in `.sugar/templates/` directory:

#### Directory Structure
```
.sugar/
└── templates/
    ├── custom-security.txt
    ├── performance.md
    └── accessibility.txt
```

#### Template Format

Templates can be `.txt` or `.md` files with variable substitution:

**Available Variables:**
- `${tool_name}` - Name of the tool (e.g., "eslint", "bandit")
- `${command}` - Full command that was executed
- `${output_file_path}` - Path to the tool's output file

**Example: `.sugar/templates/performance.txt`**
```
You are analyzing performance issues from ${tool_name}.

Command executed: ${command}
Results location: ${output_file_path}

Focus your analysis on:
1. **Critical Performance Bottlenecks**
   - Operations slower than 100ms
   - Database query inefficiencies
   - Memory leaks or excessive allocations

2. **Optimization Opportunities**
   - Algorithmic improvements (O(n²) → O(n log n))
   - Caching strategies
   - Batch operation opportunities

3. **Resource Usage**
   - CPU intensive operations
   - Memory consumption patterns
   - I/O blocking issues

Prioritize issues by:
- User-facing performance impact
- Frequency of execution
- Resource consumption severity

Create focused tasks for the top 3-5 most impactful issues.
```

#### Using Custom Templates

**Via tool_mappings:**
```yaml
external_tools:
  templates_dir: ".sugar/templates"
  tool_mappings:
    lighthouse: "performance"  # Uses .sugar/templates/performance.txt
    pa11y: "accessibility"     # Uses .sugar/templates/accessibility.txt
```

**Via template_type:**
```yaml
external_tools:
  tools:
    - name: lighthouse
      command: "lighthouse https://example.com --output json"
      template_type: "performance"  # References custom template
```

**Via inline prompt_template:**
```yaml
external_tools:
  tools:
    - name: lighthouse
      command: "lighthouse https://example.com --output json"
      prompt_template: |
        Analyze performance metrics from ${tool_name}.
        
        Output: ${output_file_path}
        
        Focus on Core Web Vitals and create tasks for metrics below target.
```

### Complete Configuration Example

```yaml
sugar:
  discovery:
    external_tools:
      enabled: true
      templates_dir: ".sugar/templates"
      default_template: "default"
      
      # Global tool-to-template mappings
      tool_mappings:
        bandit: "security"
        semgrep: "security"
        eslint: "lint"
        ruff: "lint"
        lighthouse: "performance"  # Custom template
        
      tools:
        # Tool with inline template (full control)
        - name: custom-scanner
          command: "scanner --format json"
          prompt_template: |
            Analyze ${tool_name} security scan results.
            Command: ${command}
            Focus on: authentication issues, XSS vulnerabilities, SQL injection
        
        # Tool with template type reference
        - name: bandit
          command: "bandit -r src/ -f json"
          template_type: "security"
        
        # Tool using global mapping (bandit → security)
        - name: semgrep
          command: "semgrep --config auto --json"
          # No template specified, uses tool_mappings
        
        # Tool with auto-detection (eslint → lint)
        - name: eslint
          command: "npx eslint . --format json"
          # Auto-detected as linting tool
          
      max_tasks_per_tool: 50
      
      grouping:
        default_strategy: "rule"
        min_issues_for_grouping: 5
```

### Best Practices

#### 1. **Start with Built-in Templates**
Use built-in templates (`default`, `security`, `lint`, `coverage`) before creating custom ones.

```yaml
# Good: Use built-in templates
tools:
  - name: ruff
    command: "ruff check ."
    template_type: "lint"
```

#### 2. **Use Global Mappings for Common Tools**
Centralize tool-to-template mappings instead of repeating `template_type` on each tool.

```yaml
# Good: Central mapping
tool_mappings:
  bandit: "security"
  snyk: "security"
  
tools:
  - name: bandit
    command: "bandit -r src/"
  - name: snyk
    command: "snyk test"
```

#### 3. **Custom Templates for Specialized Analysis**
Create custom templates when you need domain-specific analysis focus.

```yaml
# .sugar/templates/api-security.txt
Analyze ${tool_name} API security scan.

Focus on:
- Authentication/Authorization flaws
- API rate limiting issues
- Input validation gaps
- OWASP API Security Top 10

Prioritize exploitable vulnerabilities affecting production APIs.
```

#### 4. **Use Inline Templates Sparingly**
Reserve inline `prompt_template` for truly unique one-off cases.

```yaml
# Only when template is very specific to this tool instance
tools:
  - name: special-case
    command: "special-tool"
    prompt_template: "Very specific custom prompt..."
```

#### 5. **Provide Clear Context in Templates**
Help Claude understand the tool's purpose and what matters most.

```yaml
# Good template structure:
# 1. Tool context
# 2. Analysis focus areas
# 3. Prioritization criteria
# 4. Task creation guidance
```

### Troubleshooting Templates

#### Template Not Found
```
Error: Template 'custom' not found
```

**Solution:** Verify template file exists in `templates_dir`:
```bash
ls -la .sugar/templates/
# Should show: custom.txt or custom.md
```

#### Template Variables Not Substituting
```
Output shows: ${tool_name} instead of actual tool name
```

**Solution:** Use correct variable syntax: `${variable_name}` (not `$variable_name` or `{variable_name}`)

#### Wrong Template Being Used
```
Security tool using lint template
```

**Solution:** Check template priority:
1. Does tool have `prompt_template`? (highest priority)
2. Does tool have `template_type`?
3. Is tool in `tool_mappings`?
4. Check auto-detection patterns
5. Check `default_template` setting

#### Testing Templates

```bash
# Test with dry-run and single cycle
sugar run --dry-run --once

# Check which template was selected
grep -i "template" .sugar/sugar.log

# View the exact prompt sent to Claude
grep -A 20 "prompt_template" .sugar/sugar.log
```

---

**Remember:** Proper exclusions improve Sugar's performance and ensure it focuses on your actual project code, not dependencies or build artifacts.