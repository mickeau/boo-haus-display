import json
import os
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = 'boo_haus_config.json'
DEFAULT_ENV_FILE = '.env'
ENV_CONFIG_OVERRIDES = {
    'OPENWEATHER_API_KEY': 'api_keys.openweather',
    'ANTHROPIC_API_KEY': 'api_keys.anthropic',
}
CONFIG_ENV_OVERRIDES = {
    config_key: env_var for env_var, config_key in ENV_CONFIG_OVERRIDES.items()
}
PLACEHOLDER_PREFIXES = (
    'YOUR_',
    'REPLACE_WITH_',
)
PLACEHOLDER_VALUES = {
    '',
    'changeme',
    'change_me',
    'replace_me',
}


def deep_merge(base, override):
    """Return base recursively updated with override values."""
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_env_file(project_root, env_file=DEFAULT_ENV_FILE):
    """Load simple KEY=value pairs into os.environ without overriding existing values."""
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = Path(project_root) / env_path

    if not env_path.exists():
        return None

    with open(env_path, 'r') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue

            if (
                (value.startswith('"') and value.endswith('"')) or
                (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]

            os.environ.setdefault(key, value)

    return env_path


class Config:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file=None, project_root=None, env_file=DEFAULT_ENV_FILE):
        project_root = Path(project_root) if project_root else PROJECT_ROOT
        loaded_env_file = load_env_file(project_root, env_file)
        config_file = config_file or os.environ.get('BOO_HAUS_CONFIG_FILE', DEFAULT_CONFIG_FILE)

        if (
            not hasattr(self, 'initialized') or
            self.config_file != config_file or
            self.project_root != project_root or
            self.env_file != env_file
        ):
            self.config_file = config_file
            self.project_root = project_root
            self.env_file = env_file
            self.config = {}
            self.loaded_files = []
            if loaded_env_file:
                self.loaded_files.append(str(loaded_env_file))
            self.using_example_only = False
            self.load_config()
            self.initialized = True

    def load_config(self):
        """Load example defaults, then overlay local configuration if present."""
        config_path = self.resolve_path(self.config_file)
        example_config_path = self.project_root / 'boo_haus_config.example.json'

        defaults = {}
        if example_config_path.exists():
            with open(example_config_path, 'r') as f:
                defaults = json.load(f)
            if not isinstance(defaults, dict):
                raise ValueError(f"Example config must contain a JSON object: {example_config_path}")
            self.loaded_files.append(str(example_config_path))

        if config_path.exists():
            with open(config_path, 'r') as f:
                local_config = json.load(f)
            if not isinstance(local_config, dict):
                raise ValueError(f"Config must contain a JSON object: {config_path}")
            self.loaded_files.append(str(config_path))
            self.config = deep_merge(defaults, local_config) if defaults else local_config
            self.using_example_only = False
            return

        if defaults:
            self.config = defaults
            self.using_example_only = True
            return

        raise FileNotFoundError(f"Neither '{self.config_file}' nor 'boo_haus_config.example.json' were found.")

    def save_config(self):
        """Saves the current configuration to the JSON file."""
        config_path = self.resolve_path(self.config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
        self.using_example_only = False
        if str(config_path) not in self.loaded_files:
            self.loaded_files.append(str(config_path))

    def resolve_path(self, path):
        """Resolve a configured path relative to the project root."""
        path = Path(path)
        return path if path.is_absolute() else self.project_root / path

    def runtime_path(self, key, default):
        """Resolve a config value path by dot-key, or a default path."""
        return str(self.resolve_path(self.get(key, default)))

    @staticmethod
    def is_placeholder(value):
        """Return True for blank/example placeholder config values."""
        if value is None:
            return True
        if not isinstance(value, str):
            return False

        normalized = value.strip()
        if normalized.lower() in PLACEHOLDER_VALUES:
            return True
        return any(normalized.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)

    def has_real_value(self, key):
        """Return True when a config key is present and not a placeholder."""
        return not self.is_placeholder(self.get(key))

    def get(self, key, default=None):
        """
        Retrieves a value from the configuration.
        Uses dot notation for nested keys (e.g., 'weather.api_key').
        """
        env_var = CONFIG_ENV_OVERRIDES.get(key)
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value is not None and not self.is_placeholder(env_value):
                return env_value

        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def _set_in_memory(self, key, value):
        keys = key.split('.')
        d = self.config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    def set(self, key, value):
        """
        Sets a value in the configuration.
        Uses dot notation for nested keys.
        """
        self._set_in_memory(key, value)
        self.save_config()

# Global instance to be imported by other modules
config = Config()
